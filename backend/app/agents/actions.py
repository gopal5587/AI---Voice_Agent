"""Business actions (mock CRM, callback scheduling, escalation webhook). Appends to data/runtime/crm.jsonl and,
if ESCALATION_WEBHOOK_URL is set, POSTs the event so a real CRM/ticketing system can consume it."""
import json
import logging
import os
from datetime import datetime, timezone

import httpx

from ..config import settings

log = logging.getLogger("actions")


def record(session, action_type: str, payload: dict) -> dict:
    event = {"action": action_type, "session_id": session.id, "agent": session.agent_key,
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "payload": payload}
    session.actions.append(event)
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    with (settings.runtime_dir / "crm.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    url = os.getenv("ESCALATION_WEBHOOK_URL")
    if url and action_type in ("escalation", "callback_scheduled"):
        try:
            httpx.post(url, json=event, timeout=3)
        except httpx.HTTPError as exc:
            log.warning("webhook delivery failed: %s", exc)
    return event
