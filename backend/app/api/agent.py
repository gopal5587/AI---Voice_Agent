import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agents.engine import get_session
from ..agents.registry import AGENT_CLASSES, continue_session, load_config, start_session
from ..config import settings

router = APIRouter(prefix="/api/agent", tags=["voice-agent"])


class StartRequest(BaseModel):
    lang: str | None = None
    today: str | None = None


class MessageRequest(BaseModel):
    text: str


@router.get("/list")
def list_agents():
    out = []
    for key in AGENT_CLASSES:
        cfg = load_config(key)
        out.append({"key": key, "name": cfg["name"], "description": cfg["description"], "languages": cfg["script"]["languages"],
                    "voice_lang": cfg["script"].get("voice_lang", {}), "market": cfg["script"]["market"],
                    "vapi_assistant_id": settings.vapi_assistants.get(key) or None})
    return out


@router.post("/{key}/start")
def start(key: str, req: StartRequest):
    if key not in AGENT_CLASSES:
        raise HTTPException(404, "unknown agent")
    _, reply = start_session(key, today=req.today, lang=req.lang)
    return reply


@router.post("/session/{session_id}/message")
def message(session_id: str, req: MessageRequest):
    try:
        return continue_session(session_id, req.text)
    except KeyError:
        raise HTTPException(404, "session not found or expired")


@router.get("/session/{session_id}")
def session_detail(session_id: str):
    s = get_session(session_id)
    if not s:
        path = settings.runtime_dir / "sessions" / f"{session_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        raise HTTPException(404, "session not found")
    return asdict(s)


@router.get("/crm")
def crm(limit: int = 50):
    path = settings.runtime_dir / "crm.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in reversed(lines)]
