"""Signal extraction over the live transcript. Deterministic rules first (cheap, explainable, ~0.1 ms);
an optional LLM classifier adds semantic signals for customer utterances the rules did not match."""
import json
import math
import re
import time
from dataclasses import dataclass, field

from .. import llm
from ..config import settings


@dataclass
class Utterance:
    speaker: str          # agent | customer | mixed
    text: str
    final: bool
    t_stream: float       # stream time (s) of the end of the utterance
    t_ref_wall: float     # wall time the audio carrying the last word was received (latency reference)
    asr_conf: float = 1.0
    words: int = 0


@dataclass
class Candidate:
    kind: str
    topic: str
    priority: int
    title: str
    message: str
    confidence: float
    asr_conf: float
    evidence: str
    speaker: str
    t_stream: float
    t_ref_wall: float
    source: str = "rule"
    stamps: dict = field(default_factory=dict)


def load_rules() -> dict:
    return json.loads((settings.configs_dir / "nudges" / "rules.json").read_text(encoding="utf-8"))


class SignalEngine:
    def __init__(self, rules: dict | None = None) -> None:
        self.rules = rules or load_rules()
        self.defaults = self.rules["defaults"]
        self.signals = {s["kind"]: s for s in self.rules["signals"]}
        self._compiled = {s["kind"]: [(p, re.compile(p["re"], re.I)) for p in s.get("patterns", [])] for s in self.rules["signals"]}
        self.topics = {k: re.compile(v, re.I) for k, v in self.rules["topics"].items()}
        self.frustration = 0.0
        self._frustration_t = 0.0
        self.agent_said_recording = False
        self.agent_said_assessment = False
        self.agent_spoke = False
        self.agent_conf: list[float] = []
        self.fired_state_checks: set[str] = set()
        self.current_topic: str | None = None
        self._partial_hits: dict[tuple, int] = {}
        self.llm_ms: list[float] = []

    def _speaker_ok(self, spec: dict, speaker: str) -> bool:
        return speaker == "mixed" or spec["speaker"] == speaker

    def topic_of(self, text: str) -> str | None:
        scores = {k: len(p.findall(text)) for k, p in self.topics.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] else None

    def process(self, u: Utterance) -> tuple[list[Candidate], dict | None]:
        """Returns candidates and an optional topic-shift event."""
        out: list[Candidate] = []
        low = u.text.lower()
        if not u.final:
            return self._partial(u, low), None

        if u.speaker in ("agent", "mixed"):
            self.agent_spoke = True
            self.agent_conf.append(u.asr_conf)
            comp = self.signals["compliance"]["state_checks"]
            if re.search(comp["recording_disclosure"]["said_re"], low):
                self.agent_said_recording = True
            if re.search(comp["pricing_before_disclosure"]["disclosure_re"], low):
                self.agent_said_assessment = True
            pricing = comp["pricing_before_disclosure"]
            if re.search(pricing["pricing_re"], low) and not self.agent_said_assessment and "pricing" not in self.fired_state_checks:
                self.fired_state_checks.add("pricing")
                out.append(self._cand("compliance", "pricing_before_disclosure", pricing["nudge"], 0.85, u, low))

        for kind, patterns in self._compiled.items():
            spec = self.signals[kind]
            if not self._speaker_ok(spec, u.speaker):
                continue
            for p, rx in patterns:
                m = rx.search(low)
                if m:
                    out.append(self._cand(kind, p["topic"], p["nudge"], p["weight"], u, m.group(0)))
                    break

        spec = self.signals["frustration"]
        if self._speaker_ok(spec, u.speaker):
            decay = 0.5 ** ((u.t_stream - self._frustration_t) / spec["half_life_s"]) if self._frustration_t else 1.0
            hits = [(w, cue) for cue, w in spec["lexicon"].items() if cue in low]
            self.frustration = self.frustration * decay + sum(w for w, _ in hits)
            self._frustration_t = u.t_stream
            if hits and self.frustration >= spec["threshold"]:
                conf = min(1.0, self.frustration / (spec["threshold"] * 1.3))
                out.append(self._cand("frustration", "rising", spec["nudge"], conf, u, ", ".join(c for _, c in hits)))

        if not out and u.speaker in ("customer", "mixed") and settings.llm_enabled and u.words >= 5:
            out += self._llm(u)

        topic = self.topic_of(low)
        shift = None
        if topic and topic != self.current_topic:
            shift = {"from": self.current_topic, "to": topic, "t_stream": round(u.t_stream, 2), "speaker": u.speaker}
            self.current_topic = topic
        return out, shift

    def tick(self, t_stream: float, t_wall: float) -> list[Candidate]:
        chk = self.signals["compliance"]["state_checks"]["recording_disclosure"]
        if (t_stream >= chk["deadline_s"] and self.agent_spoke and not self.agent_said_recording
                and "recording" not in self.fired_state_checks):
            self.fired_state_checks.add("recording")
            # absence of a phrase is only evidence if the agent channel is transcribed reliably
            channel_conf = sum(self.agent_conf) / len(self.agent_conf)
            u = Utterance("agent", "", True, t_stream, t_wall, 1.0, 0)
            cand = self._cand("compliance", "recording_disclosure", chk["nudge"], 0.9, u,
                              f"no recording disclosure by {chk['deadline_s']}s (agent ASR conf {channel_conf:.2f})")
            if channel_conf < chk["min_channel_asr_conf"]:
                cand.confidence = round(0.9 * channel_conf * 0.6, 3)
            cand.asr_conf = round(channel_conf, 3)
            return [cand]
        return []

    def _partial(self, u: Utterance, low: str) -> list[Candidate]:
        """Early trigger for rules with partial_trigger; requires the match in two consecutive partials because
        partial hypotheses get revised (Vosk partials carry no usable word confidence)."""
        out = []
        for kind, spec in self.signals.items():
            if not spec.get("partial_trigger") or not self._speaker_ok(spec, u.speaker):
                continue
            for p, rx in self._compiled[kind]:
                m = rx.search(low)
                key = (kind, p["topic"])
                if m:
                    self._partial_hits[key] = self._partial_hits.get(key, 0) + 1
                    if self._partial_hits[key] == 2:
                        out.append(self._cand(kind, p["topic"], p["nudge"], p["weight"], u, m.group(0), source="rule-partial"))
                else:
                    self._partial_hits.pop(key, None)
        return out

    def _cand(self, kind: str, topic: str, message: str, weight: float, u: Utterance, evidence: str, source: str = "rule") -> Candidate:
        spec = self.signals[kind]
        conf = weight * (u.asr_conf if u.final else 0.9)
        return Candidate(kind, topic, spec["priority"], spec["title"], message, round(conf, 3), round(u.asr_conf, 3), evidence,
                         u.speaker, u.t_stream, u.t_ref_wall, source, {"t_signal": time.time()})

    def _llm(self, u: Utterance) -> list[Candidate]:
        t0 = time.perf_counter()
        res = llm.chat_json([
            {"role": "system", "content": "Classify a customer utterance from a live sales/collections call. Return JSON "
             "{\"signals\":[{\"kind\":one of [cross_sell,frustration,payment_difficulty,callback,buying_signal],\"confidence\":0-1,\"evidence\":short quote}]}. "
             "Only include signals clearly supported by the utterance; return an empty list otherwise."},
            {"role": "user", "content": u.text}], max_tokens=120, timeout=3)
        self.llm_ms.append((time.perf_counter() - t0) * 1000)
        out = []
        for s in (res or {}).get("signals", []):
            kind = s.get("kind")
            if kind in self.signals and kind != "compliance":
                spec = self.signals[kind]
                msg = spec.get("nudge") or spec["patterns"][0]["nudge"]
                c = self._cand(kind, "llm", msg, float(s.get("confidence", 0)), u, s.get("evidence", ""), source="llm")
                c.stamps["t_llm"] = time.time()
                out.append(c)
        return out


def asr_confidence(words: list[dict]) -> float:
    confs = [w.get("conf", 1.0) for w in words]
    return sum(confs) / len(confs) if confs else 0.0


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)
