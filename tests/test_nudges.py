import time

from app.realtime.nudges import NudgeManager
from app.realtime.signals import Candidate, SignalEngine, Utterance, load_rules

RULES = load_rules()


def cand(kind="cross_sell", topic="multi_vehicle", conf=0.9, asr=0.95, priority=3, evidence="second car", source="rule"):
    return Candidate(kind, topic, priority, "t", f"advice for {topic}", conf, asr, evidence, "customer", 1.0, time.time(), source,
                     {"t_signal": time.time()})


def kinds(events, t="nudge"):
    return [e for e in events if e["type"] == t]


def test_low_confidence_and_low_asr_are_suppressed():
    m = NudgeManager(RULES)
    assert m.offer(cand(conf=0.2), 8)[0]["reason"] == "low_confidence"
    assert m.offer(cand(asr=0.3), 8)[0]["reason"] == "low_asr_confidence"
    assert m.offer(cand(), 2)[0]["reason"] == "too_short"


def test_duplicate_is_grouped_not_repeated():
    m = NudgeManager(RULES)
    assert kinds(m.offer(cand(), 8))
    ev = m.offer(cand(evidence="another vehicle"), 8)
    assert ev[0]["reason"] == "duplicate" and not kinds(ev)


def test_cooldown_groups_new_topic_into_visible_card():
    m = NudgeManager(RULES)
    m.offer(cand(), 8)
    ev = m.offer(cand(topic="add_driver", evidence="new driver"), 8)
    assert ev[0]["type"] == "nudge_updated" and "advice for add_driver" in ev[0]["message"]
    again = m.offer(cand(topic="add_driver", evidence="new driver"), 8)
    assert again[0]["type"] == "suppressed"


def test_max_active_evicts_lowest_priority():
    m = NudgeManager(RULES)
    now = time.time()
    m.offer(cand("cross_sell", "multi_vehicle", priority=3), 8, now)
    m.offer(cand("buying_signal", "ready", priority=3, conf=0.95), 8, now)
    m.offer(cand("callback", "requested", priority=3, conf=0.95), 8, now)
    ev = m.offer(cand("compliance", "risky_claim", priority=1, conf=0.95), 8, now)
    assert any(e["type"] == "nudge_closed" and e["status"] == "evicted" for e in ev)
    assert kinds(ev) and len(m.active) <= RULES["defaults"]["max_active"]


def test_nudges_expire():
    m = NudgeManager(RULES)
    m.offer(cand(), 8)
    closed = m.tick(time.time() + 3600)
    assert closed and closed[0]["status"] == "expired_unactioned"


def test_frustration_needs_accumulated_evidence():
    eng = SignalEngine(RULES)
    one, _ = eng.process(Utterance("customer", "this is a bit annoying", True, 5.0, time.time(), 0.95, 5))
    assert not [c for c in one if c.kind == "frustration"]
    many = []
    for i, text in enumerate(["this is ridiculous", "how many times do I have to say the same thing",
                              "are you even listening to me"]):
        out, _ = eng.process(Utterance("customer", text, True, 10.0 + i * 3, time.time(), 0.95, 8))
        many += out
    assert [c for c in many if c.kind == "frustration"]


def test_risky_claim_from_agent_triggers_compliance():
    eng = SignalEngine(RULES)
    out, _ = eng.process(Utterance("agent", "do not worry your approval is guaranteed", True, 5.0, time.time(), 0.95, 7))
    assert [c for c in out if c.kind == "compliance" and c.topic == "risky_claim"]
