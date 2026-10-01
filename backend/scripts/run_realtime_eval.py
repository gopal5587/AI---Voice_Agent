"""Q4 evaluation: stream every scenario over the real WebSocket at 1x speed (concurrently), ack nudges like the
dashboard does, and report latency percentiles, nudge precision/recall vs labels, and suppression stats.

usage: python backend/scripts/run_realtime_eval.py [--rounds 3] [--port 8765]"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402
import websockets  # noqa: E402

from app.config import settings  # noqa: E402
from app.realtime.signals import percentile  # noqa: E402


def serve(port: int) -> uvicorn.Server:
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)
    return server


async def stream(port: int, scenario: str) -> dict:
    events = []
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws/realtime", max_size=None) as ws:
        await ws.send(json.dumps({"type": "start", "mode": "replay", "scenario": scenario, "speed": 1}))
        t_start = time.time()
        async for raw in ws:
            ev = json.loads(raw)
            ev["_recv_wall"] = time.time()
            events.append(ev)
            if ev["type"] == "nudge":
                await ws.send(json.dumps({"type": "ack", "id": ev["id"], "displayed_at_ms": ev["_recv_wall"] * 1000}))
            if ev["type"] == "end":
                return {"scenario": scenario, "summary": ev["summary"], "events": events, "wall_s": time.time() - t_start}
    raise RuntimeError("stream ended without summary")


def score(run: dict, expected: dict) -> dict:
    kinds = [n["kind"] for n in run["summary"]["nudges"]]
    required, allowed = set(expected["required"]), set(expected["allowed"])
    tp = sorted(set(kinds) & required)
    fp = [k for k in kinds if k not in required | allowed]
    return {"emitted": kinds, "true_positive_kinds": tp, "missed_kinds": sorted(required - set(kinds)),
            "false_positives": fp, "allowed_extras": [k for k in kinds if k in allowed]}


async def main_async(rounds: int, port: int, concurrent: bool = True) -> dict:
    scenarios = json.loads((settings.scenarios_dir / "realtime" / "scenarios.json").read_text(encoding="utf-8"))
    runs = []
    for r in range(rounds):
        print(f"round {r + 1}/{rounds}: streaming {len(scenarios)} calls {'concurrently' if concurrent else 'one at a time'} at 1x ...",
              flush=True)
        if concurrent:
            results = await asyncio.gather(*(stream(port, s["id"]) for s in scenarios))
        else:
            results = [await stream(port, s["id"]) for s in scenarios]
        for s, res in zip(scenarios, results):
            res["round"] = r + 1
            res["score"] = score(res, s["expected"])
            runs.append(res)
            print(f"  {s['id']}: nudges={res['score']['emitted']} fp={res['score']['false_positives']} missed={res['score']['missed_kinds']}")
    return {"scenarios": scenarios, "runs": runs}


def aggregate(data: dict) -> dict:
    lat = {k: [] for k in ("end_to_end", "asr_finalization_lag", "asr_compute_per_chunk", "signal_extraction", "nudge_control", "delivery")}
    for run in data["runs"]:
        s = run["summary"]
        for n in s["nudges"]:
            if "e2e_ms" in n:
                lat["end_to_end"].append(n["e2e_ms"])
                lat["delivery"].append(n["delivery_ms"])
        for ev in run["events"]:
            if ev["type"] == "transcript" and ev["final"] and ev["asr_lag_ms"] is not None:
                lat["asr_finalization_lag"].append(ev["asr_lag_ms"])
            if ev["type"] == "nudge":
                lat["signal_extraction"].append(ev["latency"]["signal_ms"])
                lat["nudge_control"].append(ev["latency"]["nudge_ms"])
    chunk = [run["summary"]["latency_ms"]["asr_compute_per_chunk"] for run in data["runs"]]
    stats = {k: {"n": len(v), "p50": percentile(v, 50), "p95": percentile(v, 95)} for k, v in lat.items() if k != "asr_compute_per_chunk"}
    stats["asr_compute_per_chunk"] = {"n": sum(c["n"] for c in chunk), "p50": round(statistics.median(c["p50"] for c in chunk), 2),
                                      "p95": round(max(c["p95"] for c in chunk), 2), "note": "max of per-run P95"}
    emitted = sum(len(r["score"]["emitted"]) for r in data["runs"])
    fps = sum(len(r["score"]["false_positives"]) for r in data["runs"])
    required = sum(len(set(s["expected"]["required"])) for s in data["scenarios"]) * (len(data["runs"]) // len(data["scenarios"]))
    tps = sum(len(r["score"]["true_positive_kinds"]) for r in data["runs"])
    suppressed = {}
    for r in data["runs"]:
        for reason, n in r["summary"]["suppressed_by_reason"].items():
            suppressed[reason] = suppressed.get(reason, 0) + n
    return {"latency_ms": stats, "nudges_emitted": emitted, "false_positives": fps,
            "precision": round((emitted - fps) / emitted, 3) if emitted else None,
            "recall_required_kinds": round(tps / required, 3) if required else None, "suppressed_by_reason": suppressed}


def write(data: dict, agg: dict, single: dict | None = None) -> None:
    out = settings.evidence_dir / "q4"
    out.mkdir(parents=True, exist_ok=True)
    slim = [{k: v for k, v in r.items() if k != "events"} for r in data["runs"]]
    (out / "realtime_eval.json").write_text(json.dumps({"aggregate": agg, "aggregate_single_call": single, "runs": slim}, indent=2),
                                            encoding="utf-8")
    first = {r["scenario"]: r for r in data["runs"] if r["round"] == 1}
    for sid, r in first.items():
        log = [{k: v for k, v in e.items() if k != "_recv_wall"} | {"t_wall_rel_s": round(e["_recv_wall"] - r["events"][0]["_recv_wall"], 2)}
               for e in r["events"] if e["type"] != "end"]
        (out / "event_logs").mkdir(exist_ok=True)
        (out / "event_logs" / f"{sid}.jsonl").write_text("\n".join(json.dumps(e) for e in log), encoding="utf-8")

    L = agg["latency_ms"]
    lines = ["# Q4 Real-time nudges: latency and quality report", "",
             "Generated by `python backend/scripts/run_realtime_eval.py`. Each scenario's dual-channel call audio is streamed over the "
             f"production WebSocket in 100 ms chunks paced at 1x real time. Load test: all {len(data['scenarios'])} calls run concurrently "
             f"on one laptop CPU ({os.cpu_count()} logical cores). Baseline: one call at a time. The client acknowledges each nudge on "
             "receipt (display time). The latency reference is when the audio of the trigger word's last syllable was due to arrive "
             "(its real-time schedule), so ASR backlog under load counts as latency.", "",
             f"- ASR: `{data['runs'][0]['summary']['asr']}` (offline, CPU) | LLM classifier: "
             f"`{'enabled' if data['runs'][0]['summary']['llm_enabled'] else 'disabled (rules only; no API key)'}`",
             f"- Runs: {len(data['runs'])} ({len(data['runs']) // len(data['scenarios'])} rounds x {len(data['scenarios'])} scenarios)", "",
             "## Latency (milliseconds)", "",
             "| Stage | n | P50 | P95 | Single call P50 | Single call P95 |", "|---|---|---|---|---|---|"]
    names = {"end_to_end": "End-to-end: audio of trigger word received -> nudge displayed",
             "asr_finalization_lag": "ASR finalization lag (last word audio received -> final transcript)",
             "asr_compute_per_chunk": "ASR compute per 100 ms chunk per channel",
             "signal_extraction": "Signal extraction (rules)", "nudge_control": "Nudge control (gates, dedupe, cooldown)",
             "delivery": "Delivery (server send -> client display)"}
    S = (single or {}).get("latency_ms", {})
    for k, label in names.items():
        s = S.get(k, {})
        lines.append(f"| {label} | {L[k]['n']} | {L[k]['p50']} | {L[k]['p95']} | {s.get('p50', '-')} | {s.get('p95', '-')} |")
    lines.append("| LLM classification | 0 | n/a | n/a | n/a | n/a |" if not data["runs"][0]["summary"]["llm_enabled"] else "")
    lines += ["", "## Nudge quality vs labels", "",
              f"- Nudges emitted: {agg['nudges_emitted']} | false positives: {agg['false_positives']} | precision: {agg['precision']} | "
              f"recall of required nudge kinds: {agg['recall_required_kinds']}",
              f"- Suppressed candidates by reason: {agg['suppressed_by_reason']}", "",
              "| Round | Scenario | Emitted nudges | Missed required | False positives | Lead time before call end (s) |", "|---|---|---|---|---|---|"]
    for r in data["runs"]:
        dur = r["summary"]["audio_seconds"]
        leads = [round(dur - n["t_stream"], 1) for n in r["summary"]["nudges"]]
        lines.append(f"| {r['round']} | {r['scenario']} | {', '.join(f'{n['kind']}/{n['topic']}' for n in r['summary']['nudges']) or 'none'} | "
                     f"{', '.join(r['score']['missed_kinds']) or '-'} | {', '.join(r['score']['false_positives']) or '-'} | {leads} |")
    lines += ["", "## Round 1 nudge detail", ""]
    for sid, r in first.items():
        lines.append(f"### {sid}")
        for n in r["summary"]["nudges"]:
            lines.append(f"- t={n['t_stream']}s **{n['kind']} / {n['topic']}** (conf {n['confidence']}, e2e {n.get('e2e_ms')} ms, "
                         f"status {n['status']}): {n['message']} Evidence: {n['evidence']}")
        for s in r["summary"]["suppressed"]:
            lines.append(f"- suppressed t={s['t_stream']}s {s['kind']}/{s['topic']} reason=`{s['reason']}` conf={s['confidence']} "
                         f"asr_conf={s['asr_conf']} evidence={s['evidence']!r}")
        lines.append("")
    (out / "latency_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-baseline", action="store_true", help="skip the one-call-at-a-time baseline round")
    args = ap.parse_args()
    serve(args.port)
    data = asyncio.run(main_async(args.rounds, args.port))
    agg = aggregate(data)
    single = None
    if not args.no_baseline:
        single = aggregate(asyncio.run(main_async(1, args.port, concurrent=False)))
    write(data, agg, single)
    print(json.dumps({"concurrent": agg, "single_call": single}, indent=2))


if __name__ == "__main__":
    main()
