"""Nudge control: confidence and ASR-quality gates, duplicate suppression, per-kind cooldowns, topic grouping,
priority-bounded active set, expiry, and resolution when the agent acts on the nudge."""
import re
import time
import uuid
from dataclasses import dataclass, field

from .signals import Candidate


@dataclass
class Nudge:
    id: str
    kind: str
    topic: str
    priority: int
    title: str
    message: str
    confidence: float
    evidence: list[str]
    t_stream: float
    created_wall: float
    expires_wall: float
    source: str
    latency: dict = field(default_factory=dict)
    status: str = "active"

    def to_event(self) -> dict:
        return {"type": "nudge", "id": self.id, "kind": self.kind, "topic": self.topic, "priority": self.priority, "title": self.title,
                "message": self.message, "confidence": self.confidence, "evidence": self.evidence, "t_stream": round(self.t_stream, 2),
                "expires_in_s": round(self.expires_wall - time.time(), 1), "source": self.source, "latency": self.latency}


class NudgeManager:
    def __init__(self, rules: dict) -> None:
        self.defaults = rules["defaults"]
        self.specs = {s["kind"]: s for s in rules["signals"]}
        self.resolve = {k: re.compile(s["resolve_agent"], re.I) for k, s in self.specs.items() if s.get("resolve_agent")}
        self.active: dict[str, Nudge] = {}
        self.history: list[Nudge] = []
        self.last_emit: dict[str, float] = {}
        self.suppressed: list[dict] = []

    def _get(self, kind: str, key: str):
        return self.specs[kind].get(key, self.defaults.get(key))

    def offer(self, c: Candidate, words: int, now: float | None = None) -> list[dict]:
        now = now or time.time()
        reason = None
        if c.confidence < self._get(c.kind, "min_confidence"):
            reason = "low_confidence"
        elif c.source != "rule-partial" and c.asr_conf < self.defaults["min_asr_confidence"]:
            reason = "low_asr_confidence"
        elif c.source != "rule-partial" and 0 < words < self.defaults["min_words"]:
            reason = "too_short"
        if reason:
            return [self._suppress(c, reason)]

        same = next((n for n in self.active.values() if n.kind == c.kind and n.topic == c.topic), None)
        if same:
            if c.evidence not in same.evidence:
                same.evidence.append(c.evidence)
            return [self._suppress(c, "duplicate", grouped_into=same.id)]
        if c.topic in {n.topic for n in self.history if n.kind == c.kind}:
            return [self._suppress(c, "already_delivered")]

        sibling = next((n for n in self.active.values() if n.kind == c.kind), None)
        if now - self.last_emit.get(c.kind, -1e9) < self._get(c.kind, "cooldown_s"):
            if sibling:  # topic grouping: fold a new topic of the same kind into the visible card
                if c.message in sibling.message:
                    return [self._suppress(c, "duplicate", grouped_into=sibling.id)]
                sibling.evidence.append(c.evidence)
                sibling.message += f" Also: {c.message}"
                self._suppress(c, "cooldown_grouped", grouped_into=sibling.id)
                return [{"type": "nudge_updated", "id": sibling.id, "message": sibling.message, "evidence": sibling.evidence}]
            return [self._suppress(c, "cooldown")]

        events = []
        if len(self.active) >= self.defaults["max_active"]:
            weakest = max(self.active.values(), key=lambda n: (n.priority, -n.created_wall))
            if weakest.priority <= c.priority:
                return [self._suppress(c, "max_active")]
            events.append(self._close(weakest, "evicted"))

        n = Nudge(uuid.uuid4().hex[:8], c.kind, c.topic, c.priority, c.title, c.message, c.confidence, [c.evidence], c.t_stream,
                  now, now + self._get(c.kind, "ttl_s"), c.source)
        stamps = c.stamps
        n.latency = {k: v for k, v in {
            "asr_ms": round((stamps["t_asr"] - c.t_ref_wall) * 1000, 1) if "t_asr" in stamps else None,
            "signal_ms": round((stamps["t_signal"] - stamps.get("t_asr", stamps["t_signal"])) * 1000, 2),
            "llm_ms": round((stamps["t_llm"] - stamps["t_signal"]) * 1000, 1) if "t_llm" in stamps else None,
            "nudge_ms": round((now - stamps.get("t_llm", stamps["t_signal"])) * 1000, 2),
            "t_ref_wall": c.t_ref_wall, "t_sent_wall": now,
        }.items()}
        self.active[n.id] = n
        self.history.append(n)
        self.last_emit[c.kind] = now
        events.append(n.to_event())
        return events

    def agent_said(self, text: str) -> list[dict]:
        return [self._close(n, "resolved_by_agent") for n in list(self.active.values())
                if n.kind in self.resolve and self.resolve[n.kind].search(text)]

    def tick(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        return [self._close(n, "expired_unactioned" if n.kind == "cross_sell" else "expired")
                for n in list(self.active.values()) if now >= n.expires_wall]

    def _close(self, n: Nudge, status: str) -> dict:
        n.status = status
        self.active.pop(n.id, None)
        return {"type": "nudge_closed", "id": n.id, "status": status}

    def _suppress(self, c: Candidate, reason: str, **extra) -> dict:
        ev = {"type": "suppressed", "kind": c.kind, "topic": c.topic, "reason": reason, "confidence": c.confidence,
              "asr_conf": c.asr_conf, "evidence": c.evidence, "t_stream": round(c.t_stream, 2), **extra}
        self.suppressed.append(ev)
        return ev
