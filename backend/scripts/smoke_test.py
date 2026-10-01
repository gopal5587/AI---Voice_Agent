"""End-to-end smoke test against a running backend (default http://localhost:8000).

  python scripts/smoke_test.py [--base http://localhost:8000]

Exercises the endpoints the web UI and Vapi use: health/config, KB search and answer (grounded and refused),
a short agent conversation, a Vapi tool-calls webhook, the real-time scenario list, and a WebSocket text session."""
import argparse
import asyncio
import json
import sys

import httpx
import websockets


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  - ' + detail) if detail else ''}")
    return ok


async def ws_check(base: str) -> bool:
    url = base.replace("http", "ws", 1) + "/ws/realtime"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "start", "mode": "browser_asr"}))
        await ws.send(json.dumps({"type": "text", "speaker": "agent", "text": "do not worry your approval is guaranteed", "final": True}))
        got = None
        for _ in range(20):
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if ev["type"] == "nudge":
                got = ev
                await ws.send(json.dumps({"type": "ack", "id": ev["id"], "displayed_at_ms": 0}))
                break
        await ws.send(json.dumps({"type": "stop"}))
        return check("websocket nudge", bool(got and got["kind"] == "compliance"), got and got["title"] or "no nudge")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    base = ap.parse_args().base.rstrip("/")
    c = httpx.Client(base_url=base, timeout=20)
    results = [check("health", c.get("/api/health").status_code == 200)]

    hit = c.get("/api/kb/search", params={"q": "What is the foreclosure charge?", "market": "IN"}).json()
    results.append(check("kb search", hit["status"] == "OK" and "4%" in hit["hits"][0]["content"], hit["hits"][0]["record_id"]))
    refused = c.post("/api/kb/answer", json={"query": "Do you offer home loans?", "market": "IN"}).json()
    results.append(check("kb refusal", refused["status"] == "INSUFFICIENT_EVIDENCE", refused["answer"][:60]))

    start = c.post("/api/agent/business_loan/start", json={}).json()
    sid = start["session_id"]
    turn = c.post(f"/api/agent/session/{sid}/message", json={"text": "Yes, but your interest rate is too high."}).json()
    results.append(check("agent objection grounded", turn["intent"] == "objection" and bool(turn["citations"]), turn["text"][:70]))
    human = c.post(f"/api/agent/session/{sid}/message", json={"text": "Can I talk to a real person?"}).json()
    results.append(check("agent escalation", human["intent"] == "escalation" and human["end_call"]))

    payload = {"message": {"type": "tool-calls", "toolCallList": [
        {"id": "t1", "function": {"name": "kb_search", "arguments": {"query": "hidden charges"}}},
        {"id": "t2", "function": {"name": "check_eligibility", "arguments": {
            "business_vintage_years": 4, "annual_turnover_inr": 3000000, "loan_amount_inr": 1000000, "credit_score": 760,
            "recent_default": False, "business_registered": True, "loan_purpose": "working capital"}}}]}}
    r = c.post("/api/vapi/tools", json=payload)
    body = r.json() if r.status_code == 200 else {}
    out = {x["toolCallId"]: x["result"] for x in body.get("results", [])}
    results.append(check("vapi tool-calls", r.status_code == 200 and "t1" in out and "pre_qualified" in str(out.get("t2")),
                         f"status {r.status_code}"))

    scen = c.get("/api/realtime/scenarios").json()
    results.append(check("realtime scenarios", len(scen) >= 5 and all(s["audio_available"] for s in scen), f"{len(scen)} scenarios"))
    results.append(asyncio.run(ws_check(base)))
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
