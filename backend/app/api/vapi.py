"""Vapi integration: function tools, custom knowledge base, and server events (end-of-call reports)."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from ..agents.business_loan import evaluate_eligibility
from ..config import settings
from ..ingestion.pii import redact
from ..retrieval.answer import answer
from ..retrieval.index import get_index

router = APIRouter(prefix="/api/vapi", tags=["vapi"])
log = logging.getLogger("vapi")
LANG = {"IN": "en", "PH": "tl", "ID": "id"}


def _authorize(secret: str | None) -> None:
    if settings.webhook_secret and secret != settings.webhook_secret:
        raise HTTPException(401, "invalid webhook secret")


def _record(kind: str, payload: dict) -> None:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    with (settings.runtime_dir / "crm.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"action": kind, "agent": "vapi", "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "payload": payload}, ensure_ascii=False) + "\n")


def run_tool(name: str, args: dict, market: str) -> str:
    if name == "kb_search":
        res = answer(args.get("query", ""), market=market, lang=LANG.get(market, "en"))
        if res["status"] != "OK":
            return json.dumps({"status": "INSUFFICIENT_EVIDENCE", "instruction": "Say the information is not available in approved material and offer a human."})
        return json.dumps({"status": "OK", "answer": res["answer"], "records": [
            {"record_id": h["record_id"], "content": h["content"], "citation": h["citation"]} for h in res["retrieval"]["hits"][:2]]},
            ensure_ascii=False)
    if name == "check_eligibility":
        return json.dumps(evaluate_eligibility(args))
    if name in ("schedule_callback", "record_promise_to_pay"):
        _record(name, {k: redact(str(v))[0] for k, v in args.items()})
        return json.dumps({"status": "recorded", **args}, ensure_ascii=False)
    if name == "transfer_to_human":
        _record("escalation", {k: redact(str(v))[0] for k, v in args.items()})
        return json.dumps({"status": "escalated", "message": "Handoff summary sent to the human team."})
    return json.dumps({"error": f"unknown tool {name}"})


@router.post("/tools")
async def tools(request: Request, market: str = "IN", x_vapi_secret: str | None = Header(None)):
    _authorize(x_vapi_secret)
    message = (await request.json()).get("message", {})
    results = []
    for call in message.get("toolCallList") or message.get("toolCalls") or []:
        fn = call.get("function", {})
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            args = json.loads(args or "{}")
        results.append({"toolCallId": call.get("id"), "result": run_tool(fn.get("name", ""), args, market)})
    return {"results": results}


@router.post("/kb")
async def custom_kb(request: Request, market: str = "IN", x_vapi_secret: str | None = Header(None)):
    """Vapi custom-knowledge-base provider endpoint (message.type == 'knowledge-base-request')."""
    _authorize(x_vapi_secret)
    message = (await request.json()).get("message", {})
    user_turns = [m.get("content", "") for m in message.get("messages", []) if m.get("role") == "user"]
    query = user_turns[-1] if user_turns else ""
    res = get_index().search(query, market=market, top_k=3)
    if res.status != "OK":
        return {"documents": [], "message": {"role": "assistant", "content":
                {"IN": "I don't have verified information about that. I can connect you to a relationship manager.",
                 "PH": "Pasensya na po, wala akong verified na impormasyon diyan. Pwede ko kayong ikonekta sa advisor.",
                 "ID": "Mohon maaf, informasi tersebut tidak tersedia. Saya dapat menyambungkan ke petugas."}.get(market)}}
    return {"documents": [{"content": f"{h.record['content']} (source: {h.citation})", "similarity": round(h.confidence, 3),
                           "uuid": h.record["record_id"]} for h in res.hits]}


@router.post("/events")
async def events(request: Request, x_vapi_secret: str | None = Header(None)):
    _authorize(x_vapi_secret)
    message = (await request.json()).get("message", {})
    if message.get("type") == "end-of-call-report":
        call = message.get("call", {})
        artifact = message.get("artifact", {})
        out = settings.evidence_dir / "vapi_calls"
        out.mkdir(parents=True, exist_ok=True)
        record = {"call_id": call.get("id"), "assistant_id": call.get("assistantId"), "ended_reason": message.get("endedReason"),
                  "recording_url": artifact.get("recordingUrl") or message.get("recordingUrl"),
                  "transcript": redact(artifact.get("transcript") or message.get("transcript") or "")[0],
                  "summary": message.get("summary") or message.get("analysis", {}).get("summary"),
                  "cost": message.get("cost"), "duration_seconds": message.get("durationSeconds")}
        (out / f"{call.get('id', 'unknown')}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("saved end-of-call report %s", call.get("id"))
    return {"ok": True}
