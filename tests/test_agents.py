import json

import pytest

from app.agents.business_loan import evaluate_eligibility
from app.agents.nlu import parse_money, parse_years
from app.config import settings
from run_agent_scenarios import run

SCENARIOS = [s for p in sorted((settings.scenarios_dir / "agents").glob("*.json"))
             for s in json.loads(p.read_text(encoding="utf-8"))]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(scenario):
    res = run(scenario)
    assert res["passed"], res["failures"]


def test_required_q1_behaviours_are_covered():
    titles = " ".join(s["title"].lower() for s in SCENARIOS if s["agent"] == "business_loan")
    for behaviour in ("cooperative", "objection", "conflict", "out-of-scope", "human"):
        assert behaviour in titles, behaviour


@pytest.mark.parametrize("text,value", [("about 25 lakh", 2_500_000), ("1.5 crore", 15_000_000), ("Rp 2,5 juta", 2_500_000),
                                        ("sejuta", 1_000_000), ("50k", 50_000)])
def test_money_parsing(text, value):
    assert parse_money(text) == pytest.approx(value)


def test_years_parsing():
    assert parse_years("three and a half years") == pytest.approx(3.5)


def test_eligibility_rules_from_kb():
    good = {"business_vintage_years": 4, "annual_turnover_inr": 3_000_000, "loan_amount_inr": 1_000_000, "credit_score": 750,
            "recent_default": False, "business_registered": True, "loan_purpose": "working capital"}
    assert evaluate_eligibility(good)["status"] == "pre_qualified"
    assert evaluate_eligibility({**good, "business_vintage_years": 1})["status"] == "not_eligible"
    assert evaluate_eligibility({**good, "credit_score": "unknown"})["status"] == "needs_review"
    assert evaluate_eligibility({**good, "loan_purpose": "excluded:speculative trading"})["status"] == "not_eligible"
