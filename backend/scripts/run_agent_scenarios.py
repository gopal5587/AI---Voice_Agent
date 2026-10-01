"""Replay scripted customer turns through the production agent engine and verify expected behavior.

Writes transcripts and a results table to evidence/q1 (business loan) and evidence/q3 (PH / ID).
These are text-level conversation tests; real voice recordings are captured from the web call UI
(frontend 'Voice Agent' tab) or Vapi and stored next to them."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.registry import continue_session, get_agent, start_session  # noqa: E402
from app.config import settings  # noqa: E402

EVIDENCE = {"business_loan": "q1", "ph_life_insurance": "q3", "id_consumer_finance": "q3"}


def check(expect: dict, reply: dict) -> list[str]:
    errors = []
    if "intent" in expect and reply["intent"] != expect["intent"]:
        errors.append(f"intent {reply['intent']!r} != {expect['intent']!r}")
    if expect.get("citations") and not reply["citations"]:
        errors.append("expected KB citations, got none")
    if "contains" in expect and expect["contains"].lower() not in reply["text"].lower():
        errors.append(f"reply missing {expect['contains']!r}")
    if "not_contains" in expect and expect["not_contains"].lower() in reply["text"].lower():
        errors.append(f"reply must not contain {expect['not_contains']!r}")
    if "lang" in expect and reply["lang"] != expect["lang"]:
        errors.append(f"lang {reply['lang']!r} != {expect['lang']!r}")
    if "slot" in expect:
        name, value = expect["slot"]
        got = reply["state"]["slots"].get(name)
        if not (got == value or (isinstance(value, (int, float)) and isinstance(got, (int, float)) and abs(got - value) < 1e-6)):
            errors.append(f"slot {name}={got!r} != {value!r}")
    return errors


def run(scenario: dict) -> dict:
    session, reply = start_session(scenario["agent"], today=scenario.get("today"))
    transcript = [("BOT", reply["text"], reply)]
    failures = []
    for i, turn in enumerate(scenario["turns"], start=1):
        reply = continue_session(session.id, turn["user"])
        transcript += [("CUSTOMER", turn["user"], None), ("BOT", reply["text"], reply)]
        failures += [f"turn {i}: {e}" for e in check(turn.get("expect", {}), reply)]
    final = scenario.get("expect_final", {})
    if "stage" in final and session.stage != final["stage"]:
        failures.append(f"final stage {session.stage!r} != {final['stage']!r}")
    status = (session.outcome or {}).get("status")
    if "outcome_status" in final and status != final["outcome_status"]:
        failures.append(f"outcome {status!r} != {final['outcome_status']!r}")
    done = [a["action"] for a in session.actions]
    for a in final.get("actions", []):
        if a not in done:
            failures.append(f"missing action {a!r}")
    return {"id": scenario["id"], "title": scenario["title"], "agent": scenario["agent"], "passed": not failures,
            "failures": failures, "stage": session.stage, "outcome": session.outcome, "actions": done,
            "slots": session.slots, "dialects": session.dialects, "lang_final": session.lang,
            "counters": session.counters, "retrievals": session.context.get("retrievals", []),
            "transcript": [{"speaker": s, "text": t, **({"intent": r["intent"], "citations": r["citations"], "lang": r["lang"],
                                                        "latency_ms": r["latency_ms"]} if r else {})} for s, t, r in transcript]}


def to_markdown(res: dict) -> str:
    lines = [f"# {res['id']}: {res['title']}", "",
             f"- Agent: `{res['agent']}` | Result: **{'PASS' if res['passed'] else 'FAIL'}** | Final stage: `{res['stage']}`",
             f"- Outcome: `{json.dumps(res['outcome'], ensure_ascii=False, default=str)}`",
             f"- Actions: {', '.join(res['actions']) or 'none'} | Final language/register: `{res['lang_final']}`"
             + (f" | Regional markers: {', '.join(res['dialects'])}" if res["dialects"] else ""),
             "- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).", ""]
    if res["failures"]:
        lines += ["**Failures:**", *[f"- {f}" for f in res["failures"]], ""]
    lines += ["| # | Speaker | Utterance | Intent | Lang | KB citations |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(res["transcript"]):
        cites = "<br>".join(t.get("citations", [])) if t.get("citations") else ""
        lines.append(f"| {i} | {t['speaker']} | {t['text'].replace('|', '/')} | {t.get('intent', '')} | {t.get('lang', '')} | {cites} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    results = []
    for path in sorted((settings.scenarios_dir / "agents").glob("*.json")):
        for scenario in json.loads(path.read_text(encoding="utf-8")):
            get_agent(scenario["agent"])
            res = run(scenario)
            results.append(res)
            out = settings.evidence_dir / EVIDENCE[scenario["agent"]] / "transcripts"
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{res['id']}.md").write_text(to_markdown(res), encoding="utf-8")
            print(("PASS " if res["passed"] else "FAIL ") + res["id"], *res["failures"], sep="\n   ")
    for q in ("q1", "q3"):
        subset = [r for r in results if EVIDENCE[r["agent"]] == q]
        rows = ["| Scenario | Agent | Result | Outcome | Actions |", "|---|---|---|---|---|"]
        rows += [f"| [{r['id']}](transcripts/{r['id']}.md) | {r['agent']} | {'PASS' if r['passed'] else 'FAIL'} | "
                 f"{(r['outcome'] or {}).get('status', r['stage'])} | {', '.join(r['actions'])} |" for r in subset]
        (settings.evidence_dir / q / "scenario_results.md").write_text(
            f"# {q.upper()} scripted conversation results\n\nGenerated by `python backend/scripts/run_agent_scenarios.py`. "
            f"{sum(r['passed'] for r in subset)}/{len(subset)} passed.\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
        (settings.evidence_dir / q / "scenario_results.json").write_text(json.dumps(subset, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    passed = sum(r["passed"] for r in results)
    print(f"{passed}/{len(results)} scenarios passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
