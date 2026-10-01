"""Script-driven conversation engine shared by all voice agents.

The script (configs/assistants/<agent>.json -> "script") holds the call flow, wording per language/register,
and business rules. Facts (FAQs, objections, policies) are never in the script: they are retrieved from the
knowledge base at answer time and cited. Turn priority: human request > opt-out > pending conflict >
slot extraction > objection/question (KB) > reprompt."""
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from ..config import settings
from ..ingestion.pii import redact
from ..retrieval.answer import answer as kb_answer
from ..retrieval.text import terms
from . import actions, nlu

CLAUSE_SPLIT = re.compile(r"[;!?]|,(?!\d)|\.(?!\d)|\s(?:and|but|also|plus|tapos|pero|at saka|dan|tapi|terus|sama)\s(?!a half)")


@dataclass
class Session:
    agent_key: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    lang: str = ""
    slots: dict[str, Any] = field(default_factory=dict)
    queue: list[str] = field(default_factory=list)
    pending: str | None = None
    conflict: dict | None = None
    stage: str = "new"
    counters: dict[str, int] = field(default_factory=lambda: {"reprompt": 0, "fallback": 0, "objections": 0, "questions": 0})
    outcome: dict | None = None
    dialects: list[str] = field(default_factory=list)
    turns: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    today: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def today_date(self) -> date:
        return date.fromisoformat(self.today)


class FlowAgent:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.script = config["script"]
        self.key = config["key"]
        self.market = self.script["market"]
        self.languages = self.script["languages"]
        self.slots = {s["name"]: s for s in self.script["slots"]}
        self.intents = {k: [re.compile(p, re.I) for p in v] for k, v in self.script["intents"].items()}

    # ---------- public API ----------
    def start(self, session: Session) -> dict:
        session.lang = session.lang or self.languages[0]
        session.queue = [s["name"] for s in self.script["slots"] if not s.get("phase")]
        session.stage = "collecting"
        self.on_start(session)
        text = self.line("greeting", session)
        nxt = self._next_slot(session)
        text = f"{text} {self._ask(session, nxt)}" if nxt else text
        return self._reply(session, text, intent="greeting")

    def handle(self, session: Session, user_text: str) -> dict:
        t0 = time.perf_counter()
        if session.stage in ("ended", "escalated"):
            return self._reply(session, self.line("already_ended", session), intent="ended", end=True)
        self._log(session, "user", user_text)
        norm = nlu.normalize_regional(user_text) if self.market == "ID" else user_text.lower()
        self._update_language(session, user_text)

        if self._match("human", norm):
            return self._escalate(session, "customer_requested_human", t0)
        if self._match("optout", norm):
            return self._end(session, "optout", "customer_opted_out", t0)

        parts: list[str] = session.context.pop("queued_lines", [])
        citations: list[str] = []
        intent = "slot"
        resolved_conflict = False

        if session.conflict:
            resolved = self._resolve_conflict(session, user_text, norm)
            if resolved is None:
                return self._reply(session, self._conflict_prompt(session), intent="conflict_unresolved", t0=t0)
            parts.append(self.line("conflict_resolved", session, value=self._fmt(session.conflict["slot"], resolved)))
            session.slots[session.conflict["slot"]] = resolved
            session.conflict = None
            resolved_conflict = True

        hardship = self._match("hardship", norm)
        objection = hardship or self._match("objection", norm)
        question = self._is_question(user_text, norm)

        filled, conflict = self._extract(session, user_text, norm, is_question=question, is_objection=bool(objection))
        if conflict:
            session.conflict = conflict
            return self._reply(session, self._conflict_prompt(session), intent="conflict_detected", t0=t0)
        for name in filled:
            if (msg := self.on_filled(session, name)):
                parts.append(msg)
            if session.stage in ("ended", "escalated"):
                return self._reply(session, " ".join(parts), intent="slot_end", end=True, t0=t0)

        if objection or question:
            intent = "objection" if objection else "question"
            session.counters["objections" if objection else "questions"] += 1
            ans = self._kb(session, user_text, norm, intent)
            if ans["status"] == "OK":
                parts.append(f"{self.line('answer_prefix', session)} {ans['answer']}".strip())
                citations = ans["citations"]
                if hardship and (msg := self.on_hardship(session)):
                    parts.append(msg)
            elif filled and len(terms(user_text)) < 4 and not objection:
                intent = "slot"  # vague aside ("why?", "kenapa ya?") alongside an answer; the next prompt explains
            else:
                session.counters["fallback"] += 1
                intent = "fallback"
                parts.append(ans["answer"])
                parts.append(self.line("fallback_offer_human" if session.counters["fallback"] >= 2 else "fallback", session))
                session.context.setdefault("unanswered_questions", []).append(redact(user_text)[0])
        elif not filled and session.pending and not session.conflict and not resolved_conflict:
            session.counters["reprompt"] += 1
            if session.counters["reprompt"] >= 3:
                return self._escalate(session, "repeated_misunderstanding", t0)
            parts.append(self.line("reprompt", session))
            intent = "reprompt"
        if filled:
            session.counters["reprompt"] = 0

        nxt = self._next_slot(session)
        if nxt:
            parts.append(self._ask(session, nxt))
        elif session.stage == "collecting":
            parts.append(self._complete(session))
        end = session.stage in ("ended", "escalated")
        return self._reply(session, " ".join(p for p in parts if p), intent=intent, citations=citations, end=end, t0=t0)

    # ---------- hooks for concrete agents ----------
    def on_start(self, session: Session) -> None: ...

    def on_filled(self, session: Session, slot: str) -> str | None:
        spec = self.slots[slot]
        if spec["type"] == "yesno" and spec.get("required_yes") and session.slots[slot] is False:
            return self._end_text(session, spec["required_yes"], f"{slot}_declined")
        return None

    def on_hardship(self, session: Session) -> str | None:
        return None

    def evaluate(self, session: Session) -> str:
        return ""

    # ---------- internals ----------
    def line(self, name: str, session: Session, **kw) -> str:
        variants = self.script["lines"].get(name, {})
        text = variants[session.lang] if session.lang in variants else variants.get(self.languages[0], "")
        return text.format(**{**session.context, **kw}) if text else ""

    def _ask(self, session: Session, slot: str) -> str:
        session.pending = slot
        spec = self.slots[slot]
        cond = spec.get("ask_if")
        if cond and session.slots.get(cond["slot"]) == cond["equals"]:
            ask = cond["ask"]
        elif session.context.get("hardship_flagged") and "ask_soft" in spec:
            ask = spec["ask_soft"]
        else:
            ask = spec["ask"]
        return (ask.get(session.lang) or ask[self.languages[0]]).format(**session.context)

    def _next_slot(self, session: Session) -> str | None:
        for name in session.queue:
            if name in session.slots:
                continue
            cond = self.slots[name].get("only_if")
            if cond and session.slots.get(cond["slot"]) != cond["equals"]:
                continue
            return name
        session.pending = None
        return None

    def _complete(self, session: Session) -> str:
        text = "" if session.context.get("post_queued") else self.evaluate(session)
        follow = [s["name"] for s in self.script["slots"] if s.get("phase") == "post"]
        if follow and not session.context.get("post_queued"):
            session.context["post_queued"] = True
            session.queue.extend(follow)
            nxt = self._next_slot(session)
            if nxt:
                return f"{text} {self._ask(session, nxt)}"
        closing = self.line("closing", session)
        session.stage = "ended"
        actions.record(session, "crm_summary", self.crm_summary(session))
        return f"{text} {closing}".strip()

    def crm_summary(self, session: Session) -> dict:
        return {"agent": self.key, "outcome": session.outcome, "slots": session.slots, "language": session.lang,
                "dialect_markers": session.dialects, "counters": session.counters,
                "unanswered_questions": session.context.get("unanswered_questions", []),
                "citations_used": sorted({c for t in session.turns for c in t.get("meta", {}).get("citations", [])})}

    def _extract(self, session: Session, raw: str, norm: str, is_question: bool = False,
                 is_objection: bool = False) -> tuple[list[str], dict | None]:
        """Fill the pending slot plus any other slot whose keywords appear. Each slot reads only the clauses that
        mention it (or, for the pending slot, clauses not claimed by another slot), so "turnover 40 lakh and I
        need 10 lakh" yields two different values."""
        filled: list[str] = []
        clauses = [c.strip() for c in CLAUSE_SPLIT.split(norm) if c and c.strip()]
        targets = [session.pending] if session.pending else []
        targets += [n for n in session.queue if n != session.pending and self._mentions(n, norm)]
        for name in targets:
            spec = self.slots[name]
            if is_question and spec["type"] in ("yesno", "free"):
                # "hindi"/"no" inside a question is not an answer; "Yes. Is this from the bank?" still is
                statements = [s for s in re.split(r"(?<=[.!?])\s+", norm) if s and not s.rstrip().endswith("?")
                              and not self._match("question", s.strip())]
                if not statements:
                    continue
                value = self._value(spec, raw, " ".join(statements), session, explicit=name == session.pending)
                if value is not None and name not in session.slots:
                    session.slots[name] = value
                    filled.append(name)
                continue
            own = [c for c in clauses if self._mentions(name, c)]
            if not own and name == session.pending:
                own = [c for c in clauses if not any(self._mentions(o, c) for o in targets if o != name)]
            scope = " , ".join(own) if own else norm
            value = self._value(spec, raw if spec["type"] == "free" else scope, scope, session, explicit=name == session.pending)
            if value == "other" and (is_question or is_objection):
                continue
            if value is None:
                continue
            if name in session.slots and session.slots[name] != value and self._differs(session.slots[name], value):
                return filled, {"slot": name, "old": session.slots[name], "new": value}
            if name not in session.slots:
                session.slots[name] = value
                filled.append(name)
        return filled, None

    def _mentions(self, slot: str, norm: str) -> bool:
        kws = self.slots[slot].get("keywords")
        return bool(kws) and re.search(kws, norm, re.I) is not None

    def _value(self, spec: dict, raw: str, norm: str, session: Session, explicit: bool) -> Any:
        kind = spec["type"]
        if spec.get("allow_unknown") and nlu.UNKNOWN.search(norm):
            return "unknown"
        if kind == "yesno":
            return nlu.parse_yes_no(norm) if explicit else None
        if kind == "years":
            return nlu.parse_years(norm, session.today_date)
        if kind == "money":
            val = nlu.parse_money(norm)
            if val is not None and spec.get("annualize") and nlu.is_monthly(norm):
                session.context.setdefault("notes", []).append(f"{spec['name']} given monthly; annualized x12")
                session.context["annualized_slot"] = spec["name"]
                val *= 12
            if val is not None and spec.get("min_plausible") and val < spec["min_plausible"]:
                return None
            return val
        if kind == "number":
            lo, hi = spec.get("range", [0, 1e12])
            return nlu.parse_number(norm, lo, hi) if (explicit or self._mentions(spec["name"], norm)) else None
        if kind == "choice":
            for value, pattern in spec["choices"].items():
                if re.search(pattern, norm, re.I):
                    return value
            return None
        if kind == "date":
            d = nlu.parse_date(norm, session.today_date)
            return d.isoformat() if d else None
        if kind == "time":
            day = nlu.parse_date(norm, session.today_date)
            tod = nlu.parse_time_of_day(norm)
            if not (day or tod):
                return None
            return f"{(day or session.today_date).isoformat()} {tod or '11:00'}"
        if kind == "free":
            return redact(raw.strip())[0] if explicit and len(raw.split()) >= 1 else None
        return None

    @staticmethod
    def _differs(old: Any, new: Any) -> bool:
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            return abs(old - new) > 0.1 * max(abs(old), abs(new), 1)
        return old != new

    def _conflict_prompt(self, session: Session) -> str:
        c = session.conflict
        return self.line("conflict", session, old=self._fmt(c["slot"], c["old"]), new=self._fmt(c["slot"], c["new"]),
                         field=self.slots[c["slot"]].get("label", c["slot"]))

    def _resolve_conflict(self, session: Session, raw: str, norm: str) -> Any:
        c = session.conflict
        spec = self.slots[c["slot"]]
        value = self._value(spec, raw, norm, session, explicit=True)
        if value is not None and not self._differs(value, c["old"]):
            return c["old"]
        if value is not None and not self._differs(value, c["new"]):
            return c["new"]
        if re.search(r"first|earlier|before|original|una|kanina|pertama|tadi|sebelumnya", norm):
            return c["old"]
        if re.search(r"second|latest|new|now|last|pangalawa|ngayon|kedua|terakhir|yang baru", norm):
            return c["new"]
        return value

    def _fmt(self, slot: str, value: Any) -> str:
        spec = self.slots[slot]
        if value == "unknown":
            return "not known"
        if spec["type"] == "money" and isinstance(value, (int, float)):
            return self.format_money(value)
        if spec["type"] == "years" and isinstance(value, (int, float)):
            return f"{value:g} year" if value == 1 else f"{value:g} years"
        return str(value)

    def format_money(self, value: float) -> str:
        return f"{value:,.0f}"

    def _is_question(self, raw: str, norm: str) -> bool:
        return "?" in raw or self._match("question", norm)

    def _kb(self, session: Session, raw: str, norm: str, intent: str) -> dict:
        query = raw
        for rule in self.script.get("kb_query_map", []):
            if re.search(rule["pattern"], norm, re.I):
                query = rule["query"]  # canonical phrasing; raw slang/filler words only dilute retrieval
                break
        res = kb_answer(query, market=self.market, lang=self.script.get("answer_lang", {}).get(session.lang, "en"))
        session.context.setdefault("retrievals", []).append({
            "query": redact(query)[0], "status": res["status"], "record_ids": res.get("record_ids", []),
            "top_confidence": res["retrieval"]["hits"][0]["confidence"] if res["retrieval"]["hits"] else None,
        })
        return res

    def kb_fact(self, session: Session, query: str) -> str:
        """Speak a supporting fact only if the KB has it, and keep its citation on the turn."""
        res = self._kb(session, query, query.lower(), "fact")
        if res["status"] != "OK":
            return ""
        session.context.setdefault("pending_citations", []).extend(res["citations"])
        sentences = [s for s in res["answer"].split(". ") if any(w in s.lower() for w in query.lower().split()[:3])]
        return (sentences[0].rstrip(".") + ".") if sentences else res["answer"]

    def _match(self, intent: str, text: str) -> bool:
        return any(p.search(text) for p in self.intents.get(intent, []))

    def _update_language(self, session: Session, text: str) -> None:
        detector = self.script.get("language_detection")
        if detector:
            scores = {lang: len(re.findall(p, text, re.I)) for lang, p in detector.items()}
            best = max(scores, key=scores.get)
            if best != session.lang and scores[best] > scores.get(session.lang, 0):
                session.context.setdefault("language_switches", []).append({"turn": len(session.turns), "to": best})
                session.lang = best
        for d in nlu.regional_markers(text) if self.market == "ID" else []:
            if d not in session.dialects:
                session.dialects.append(d)

    def _escalate(self, session: Session, reason: str, t0: float | None = None) -> dict:
        session.stage = "escalated"
        session.outcome = {**(session.outcome or {}), "escalated": True, "escalation_reason": reason}
        actions.record(session, "escalation", {"reason": reason, "summary": self.crm_summary(session)})
        return self._reply(session, self.line("escalate", session), intent="escalation", end=True, t0=t0)

    def _end_text(self, session: Session, line: str, reason: str) -> str:
        session.stage = "ended"
        session.outcome = {**(session.outcome or {}), "ended_reason": reason}
        actions.record(session, "crm_summary", self.crm_summary(session))
        return self.line(line, session)

    def _end(self, session: Session, line: str, reason: str, t0: float) -> dict:
        return self._reply(session, self._end_text(session, line, reason), intent=reason, end=True, t0=t0)

    def _log(self, session: Session, role: str, text: str, meta: dict | None = None) -> None:
        session.turns.append({"role": role, "text": redact(text)[0] if role == "user" else text,
                              "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "meta": meta or {}})

    def _reply(self, session: Session, text: str, intent: str, citations: list[str] | None = None,
               end: bool = False, t0: float | None = None) -> dict:
        citations = (citations or []) + session.context.pop("pending_citations", [])
        meta = {"intent": intent, "citations": citations, "lang": session.lang, "pending": session.pending,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2) if t0 else None}
        self._log(session, "assistant", text, meta)
        save(session)
        return {"session_id": session.id, "text": text, "end_call": end or session.stage in ("ended", "escalated"),
                "state": {"stage": session.stage, "slots": session.slots, "pending": session.pending,
                          "outcome": session.outcome, "lang": session.lang, "dialects": session.dialects},
                "voice_lang": self.script.get("voice_lang", {}).get(session.lang, "en-US"), **meta}


_SESSIONS: dict[str, Session] = {}


def save(session: Session) -> None:
    _SESSIONS[session.id] = session
    folder = settings.runtime_dir / "sessions"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{session.id}.json").write_text(json.dumps(asdict(session), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def get_session(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)
