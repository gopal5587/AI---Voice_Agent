"""Streaming ASR backends with a common callback interface.

on_result(channel, text, is_final, words, info) where words = [{"word", "start", "end", "conf"}] in stream seconds
and info carries latency measurements. Channel 0 = agent, 1 = customer (dual-channel call recording)."""
import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache

import numpy as np

from ..config import settings

log = logging.getLogger("asr")
ResultCallback = Callable[[int, str, bool, list[dict], dict], Awaitable[None]]


@lru_cache
def _vosk_model():
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    if not settings.vosk_model_path.exists():
        raise RuntimeError(f"Vosk model missing at {settings.vosk_model_path}; see README 'Offline ASR model'")
    return Model(str(settings.vosk_model_path))


class VoskStreamer:
    """Offline streaming ASR. One recognizer per channel; CPU work runs in a thread so the event loop stays free."""
    name = "vosk-small-en-us-0.15"

    def __init__(self, channels: int, sample_rate: int, on_result: ResultCallback) -> None:
        from vosk import KaldiRecognizer
        model = _vosk_model()
        self.recognizers = []
        for _ in range(channels):
            rec = KaldiRecognizer(model, sample_rate)
            rec.SetWords(True)
            rec.SetPartialWords(True)
            self.recognizers.append(rec)
        self.on_result = on_result
        self.channels = channels
        self.chunk_ms: list[float] = []
        self._last_partial = [""] * channels

    def _process(self, ch: int, pcm: bytes) -> tuple[bool, dict]:
        rec = self.recognizers[ch]
        final = rec.AcceptWaveform(pcm)
        return final, json.loads(rec.Result() if final else rec.PartialResult())

    async def feed(self, interleaved: bytes) -> None:
        frames = np.frombuffer(interleaved, dtype=np.int16).reshape(-1, self.channels)
        loop = asyncio.get_running_loop()

        async def decode(ch: int):
            t0 = time.perf_counter()
            out = await loop.run_in_executor(None, self._process, ch, frames[:, ch].tobytes())
            return out, (time.perf_counter() - t0) * 1000

        results = await asyncio.gather(*(decode(ch) for ch in range(self.channels)))
        for ch, ((final, res), compute_ms) in enumerate(results):
            self.chunk_ms.append(compute_ms)
            info = {"compute_ms": compute_ms}
            if final:
                text = res.get("text", "").strip()
                self._last_partial[ch] = ""
                if text:
                    await self.on_result(ch, text, True, res.get("result", []), info)
            else:
                text = res.get("partial", "").strip()
                if text and text != self._last_partial[ch]:
                    self._last_partial[ch] = text
                    await self.on_result(ch, text, False, res.get("partial_result", []), info)

    async def close(self) -> None:
        for ch, rec in enumerate(self.recognizers):
            res = json.loads(rec.FinalResult())
            if res.get("text"):
                await self.on_result(ch, res["text"], True, res.get("result", []), {"compute_ms": 0.0, "flush": True})


class DeepgramStreamer:
    """Deepgram Nova-3 live streaming with multichannel audio (one socket, channel_index per result)."""
    name = "deepgram-nova-3"

    def __init__(self, channels: int, sample_rate: int, on_result: ResultCallback, language: str = "en") -> None:
        self.channels, self.rate, self.on_result, self.language = channels, sample_rate, on_result, language
        self.ws = None
        self.reader: asyncio.Task | None = None
        self.chunk_ms: list[float] = []

    async def start(self) -> None:
        import websockets
        url = (f"wss://api.deepgram.com/v1/listen?model=nova-3&language={self.language}&encoding=linear16"
               f"&sample_rate={self.rate}&channels={self.channels}&multichannel={'true' if self.channels > 1 else 'false'}"
               "&interim_results=true&endpointing=300&smart_format=true&punctuate=true")
        self.ws = await websockets.connect(url, additional_headers={"Authorization": f"Token {settings.deepgram_api_key}"})
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        async for raw in self.ws:
            msg = json.loads(raw)
            if msg.get("type") != "Results":
                continue
            alt = msg["channel"]["alternatives"][0]
            text = alt.get("transcript", "").strip()
            if not text:
                continue
            ch = (msg.get("channel_index") or [0])[0]
            words = [{"word": w["word"], "start": w["start"], "end": w["end"], "conf": w.get("confidence", 1.0)} for w in alt.get("words", [])]
            await self.on_result(ch, text, bool(msg.get("is_final")), words, {"compute_ms": None})

    async def feed(self, interleaved: bytes) -> None:
        if self.ws is None:
            await self.start()
        t0 = time.perf_counter()
        await self.ws.send(interleaved)
        self.chunk_ms.append((time.perf_counter() - t0) * 1000)

    async def close(self) -> None:
        if self.ws:
            await self.ws.send(json.dumps({"type": "CloseStream"}))
            try:
                await asyncio.wait_for(self.reader, timeout=5)
            except asyncio.TimeoutError:
                pass
            await self.ws.close()


def make_streamer(channels: int, sample_rate: int, on_result: ResultCallback):
    if settings.asr_provider == "deepgram" and settings.deepgram_api_key:
        return DeepgramStreamer(channels, sample_rate, on_result)
    return VoskStreamer(channels, sample_rate, on_result)
