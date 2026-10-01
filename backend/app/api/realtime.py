"""WebSocket protocol (/ws/realtime):
client -> {"type":"start","mode":"replay","scenario":"rt_cross_sell","speed":1}
          {"type":"start","mode":"mic","sample_rate":16000} then binary PCM16 mono frames
          {"type":"start","mode":"browser_asr"} then {"type":"text","speaker":"customer","text":"...","final":true}
          {"type":"ack","id":"<nudge id>","displayed_at_ms":<epoch ms>}   {"type":"stop"}
server -> transcript | topic | nudge | nudge_updated | nudge_closed | suppressed | replay_started | end"""
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from ..config import settings
from ..realtime.session import RealtimeSession

router = APIRouter(tags=["realtime"])
log = logging.getLogger("realtime")
AUDIO = settings.scenarios_dir / "realtime" / "audio"


def _scenarios() -> list[dict]:
    meta = {s["id"]: s for s in json.loads((settings.scenarios_dir / "realtime" / "scenarios.json").read_text(encoding="utf-8"))}
    out = []
    for sid, s in meta.items():
        tl = AUDIO / f"{sid}.timeline.json"
        out.append({"id": sid, "title": s["title"], "expected": s["expected"], "noise_snr_db": s.get("noise_snr_db"),
                    "audio_available": (AUDIO / f"{sid}.wav").exists(),
                    "duration_s": json.loads(tl.read_text())["duration_s"] if tl.exists() else None})
    return out


@router.get("/api/realtime/scenarios")
def scenarios():
    return _scenarios()


@router.get("/api/realtime/audio/{scenario_id}")
def audio(scenario_id: str):
    path = AUDIO / f"{scenario_id}.wav"
    if not path.exists() or path.parent != AUDIO:
        raise HTTPException(404, "audio not found; run backend/scripts/generate_call_audio.py")
    return FileResponse(path, media_type="audio/wav")


@router.get("/api/realtime/runs")
def runs(limit: int = 10):
    folder = settings.runtime_dir / "realtime_runs"
    files = sorted(folder.glob("*.json"), reverse=True)[:limit] if folder.exists() else []
    return [json.loads(f.read_text()) | {"file": f.name} for f in files]


@router.websocket("/ws/realtime")
async def realtime_ws(ws: WebSocket):
    await ws.accept()
    lock = asyncio.Lock()

    async def send(event: dict) -> None:
        async with lock:
            try:
                await ws.send_json(event)
            except (RuntimeError, WebSocketDisconnect):
                pass

    session: RealtimeSession | None = None
    task: asyncio.Task | None = None
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if session and session.mode == "mic":
                    await session.feed_audio(msg["bytes"])
                continue
            data = json.loads(msg.get("text") or "{}")
            kind = data.get("type")
            if kind == "start" and session is None:
                mode = data.get("mode", "replay")
                if mode == "replay":
                    sid = data.get("scenario", "")
                    path = AUDIO / f"{sid}.wav"
                    if not path.exists():
                        await send({"type": "error", "message": f"unknown scenario {sid}"})
                        continue
                    session = RealtimeSession(send, "replay", channels=2, label=sid)
                    task = asyncio.create_task(session.replay(path, float(data.get("speed", 1.0))))
                elif mode == "mic":
                    session = RealtimeSession(send, "mic", channels=1, sample_rate=int(data.get("sample_rate", 16000)), label="mic")
                else:
                    session = RealtimeSession(send, "browser_asr", channels=1, label="browser_asr")
                await send({"type": "started", "mode": mode, "asr": getattr(session.asr, "name", "browser-web-speech")})
            elif kind == "text" and session and session.mode == "browser_asr":
                await session.feed_text(data.get("speaker", "mixed"), data.get("text", ""), bool(data.get("final", True)))
            elif kind == "ack" and session:
                session.ack(data.get("id", ""), float(data.get("displayed_at_ms", 0)))
            elif kind == "stop" and session:
                if task:
                    session.stopping = True
                    await task
                else:
                    await session.finish()
                break
    except WebSocketDisconnect:
        pass
    finally:
        if session and not session.closed:
            session.stopping = True
            if task:
                task.cancel()
