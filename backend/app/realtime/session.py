"""One live analysis session: audio (replayed at real-time speed, or live mic) -> streaming ASR -> signals -> nudges.

Latency reference for a nudge = wall time at which the audio containing the end of the trigger (evidence) word
was received by the server, using ASR word timings (final and partial). Without word timings (browser ASR) it falls
back to the latest received chunk, which is a lower bound. End-to-end = browser display time (client ack) - reference."""
import asyncio
import bisect
import json
import re
import time
import wave
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .asr import make_streamer
from .nudges import NudgeManager
from .signals import SignalEngine, Utterance, asr_confidence, load_rules, percentile

Send = Callable[[dict], Awaitable[None]]
CHUNK_MS = 100


class RealtimeSession:
    def __init__(self, send: Send, mode: str, channels: int = 2, sample_rate: int = 16000, label: str = "live") -> None:
        self.send, self.mode, self.channels, self.rate, self.label = send, mode, channels, sample_rate, label
        rules = load_rules()
        self.engine = SignalEngine(rules)
        self.nudges = NudgeManager(rules)
        self.asr = make_streamer(channels, sample_rate, self._on_asr) if mode != "browser_asr" else None
        self.start_wall: float | None = None
        self._chunk_end_s: list[float] = []
        self._chunk_wall: list[float] = []
        self.audio_s = 0.0
        self.transcript: list[dict] = []
        self.m: dict[str, list[float]] = {k: [] for k in ("asr_final_lag_ms", "e2e_ms", "delivery_ms", "signal_ms", "nudge_ms", "asr_component_ms")}
        self._sent: dict[str, dict] = {}
        self.topics: list[dict] = []
        self.stopping = False
        self.closed = False

    # ---------- inputs ----------
    async def feed_audio(self, pcm: bytes, arrived_wall: float | None = None) -> None:
        """arrived_wall: when the chunk arrived (replay: its real-time schedule), so ASR backlog counts as latency."""
        now = time.time()
        if self.start_wall is None:
            self.start_wall = now
        self.audio_s += len(pcm) / (2 * self.channels * self.rate)
        self._chunk_end_s.append(self.audio_s)
        self._chunk_wall.append(min(now, arrived_wall) if arrived_wall else now)
        await self.asr.feed(pcm)
        await self._emit(self.engine.tick(self.audio_s, now), words=0)
        for ev in self.nudges.tick():
            await self.send(ev)

    async def feed_text(self, speaker: str, text: str, final: bool) -> None:
        now = time.time()
        if self.start_wall is None:
            self.start_wall = now
        self.audio_s = now - self.start_wall
        await self._handle(speaker, text, final, now, now, 1.0 if final else 0.9, len(text.split()), asr_ms=None)
        for ev in self.nudges.tick():
            await self.send(ev)

    async def replay(self, wav_path: Path, speed: float = 1.0) -> None:
        with wave.open(str(wav_path)) as w:
            assert w.getframerate() == self.rate and w.getnchannels() == self.channels, "audio format mismatch"
            frames_per_chunk = int(self.rate * CHUNK_MS / 1000)
            await self.send({"type": "replay_started", "duration_s": round(w.getnframes() / self.rate, 2), "speed": speed})
            t0 = time.time()
            sent = 0
            while not self.stopping:
                data = w.readframes(frames_per_chunk)
                if not data:
                    break
                sent += len(data) // (2 * self.channels)
                due = t0 + sent / self.rate / speed
                if (delay := due - time.time()) > 0:
                    await asyncio.sleep(delay)  # pace to real time: the chunk is only "received" once it has been spoken
                await self.feed_audio(data, arrived_wall=due)
        await self.finish()

    def ack(self, nudge_id: str, displayed_ms: float) -> None:
        sent = self._sent.get(nudge_id)
        if not sent or "e2e_ms" in sent:
            return
        displayed = displayed_ms / 1000
        sent["e2e_ms"] = round((displayed - sent["t_ref_wall"]) * 1000, 1)
        sent["delivery_ms"] = round((displayed - sent["t_sent_wall"]) * 1000, 1)
        self.m["e2e_ms"].append(sent["e2e_ms"])
        self.m["delivery_ms"].append(sent["delivery_ms"])

    # ---------- ASR callback ----------
    def _ref_wall(self, t_stream: float) -> float:
        i = bisect.bisect_left(self._chunk_end_s, t_stream)
        return self._chunk_wall[min(i, len(self._chunk_wall) - 1)]

    async def _on_asr(self, ch: int, text: str, final: bool, words: list[dict], info: dict) -> None:
        if info.get("compute_ms") is not None:
            self.m["asr_component_ms"].append(info["compute_ms"])
        speaker = "mixed" if self.channels == 1 else ("agent" if ch == 0 else "customer")
        now = time.time()
        if final and words:
            t_stream = words[-1]["end"]
            ref = self._ref_wall(t_stream)
        else:
            t_stream, ref = self.audio_s, self._chunk_wall[-1] if self._chunk_wall else now
        conf = asr_confidence(words) if final else 0.9
        await self._handle(speaker, text, final, ref, now, conf, len(words) if words else len(text.split()),
                           asr_ms=(now - ref) * 1000 if final else None, t_stream=t_stream, words=words)

    def _evidence_ref(self, words: list[dict], evidence: str) -> float | None:
        """Wall time the audio ending the first occurrence of the evidence's last word was received."""
        tokens = re.findall(r"[a-z']+", evidence.lower())
        if not words or not tokens or not self._chunk_wall:
            return None
        stem = tokens[-1][:5]
        for w in words:
            if w.get("word", "").lower().startswith(stem):
                return self._ref_wall(w["end"])
        return None

    async def _handle(self, speaker: str, text: str, final: bool, ref: float, now: float, conf: float, nwords: int,
                      asr_ms: float | None, t_stream: float | None = None, words: list[dict] | None = None) -> None:
        t_stream = self.audio_s if t_stream is None else t_stream
        if final:
            if asr_ms is not None:
                self.m["asr_final_lag_ms"].append(round(asr_ms, 1))
            self.transcript.append({"speaker": speaker, "text": text, "t_stream": round(t_stream, 2), "asr_conf": round(conf, 3)})
        await self.send({"type": "transcript", "speaker": speaker, "text": text, "final": final, "t_stream": round(t_stream, 2),
                         "asr_conf": round(conf, 3), "asr_lag_ms": round(asr_ms, 1) if asr_ms is not None else None})
        u = Utterance(speaker, text, final, t_stream, ref, conf, nwords)
        candidates, shift = self.engine.process(u)
        if shift:
            self.topics.append(shift)
            await self.send({"type": "topic", **shift})
        if final and speaker in ("agent", "mixed"):
            for ev in self.nudges.agent_said(text.lower()):
                await self.send(ev)
        for c in candidates:
            c.stamps["t_asr"] = now
            trigger_ref = self._evidence_ref(words or [], c.evidence)
            if trigger_ref is not None:
                c.t_ref_wall = min(c.t_ref_wall, trigger_ref)
        await self._emit(candidates, nwords)

    async def _emit(self, candidates, words: int) -> None:
        for c in candidates:
            c.stamps.setdefault("t_asr", c.stamps["t_signal"])
            for ev in self.nudges.offer(c, words):
                if ev["type"] == "nudge":
                    lat = ev["latency"]
                    self._sent[ev["id"]] = {"t_ref_wall": lat["t_ref_wall"], "t_sent_wall": lat["t_sent_wall"]}
                    self.m["signal_ms"].append(lat["signal_ms"])
                    self.m["nudge_ms"].append(lat["nudge_ms"])
                await self.send(ev)

    # ---------- end ----------
    async def finish(self) -> dict:
        if self.closed:
            return {}
        self.closed = True
        if self.asr:
            await self.asr.close()
        await asyncio.sleep(0.3)  # allow last acks to arrive
        for n in list(self.nudges.active.values()):
            await self.send(self.nudges._close(n, "missed_opportunity" if n.kind == "cross_sell" else "open_at_call_end"))
        summary = self.summary()
        await self.send({"type": "end", "summary": summary})
        out = settings.runtime_dir / "realtime_runs"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        (out / f"{self.label}_{stamp}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    def summary(self) -> dict:
        def stats(values):
            return {"n": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95), "max": round(max(values), 1) if values else None}
        nudges = [{"id": n.id, "kind": n.kind, "topic": n.topic, "priority": n.priority, "status": n.status, "confidence": n.confidence,
                   "t_stream": round(n.t_stream, 2), "evidence": n.evidence, "message": n.message, "source": n.source,
                   **{k: v for k, v in self._sent.get(n.id, {}).items() if k in ("e2e_ms", "delivery_ms")}} for n in self.nudges.history]
        return {
            "label": self.label, "mode": self.mode, "asr": getattr(self.asr, "name", "browser-web-speech"),
            "audio_seconds": round(self.audio_s, 2), "llm_enabled": settings.llm_enabled,
            "latency_ms": {"end_to_end": stats(self.m["e2e_ms"]), "asr_finalization_lag": stats(self.m["asr_final_lag_ms"]),
                           "asr_compute_per_chunk": stats(self.m["asr_component_ms"]), "signal_extraction": stats(self.m["signal_ms"]),
                           "llm": stats(self.engine.llm_ms), "nudge_control": stats(self.m["nudge_ms"]), "delivery": stats(self.m["delivery_ms"])},
            "nudges": nudges,
            "suppressed": self.nudges.suppressed,
            "suppressed_by_reason": dict(Counter(s["reason"] for s in self.nudges.suppressed)),
            "topics": self.topics,
            "transcript": self.transcript,
        }
