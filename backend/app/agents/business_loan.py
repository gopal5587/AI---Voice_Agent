from datetime import datetime, timedelta

from ..retrieval.index import get_index
from . import actions
from .engine import FlowAgent, Session

OPS = {
    ">=": lambda v, t: v >= float(t),
    "<=": lambda v, t: v <= float(t),
    "between": lambda v, t: float(t.split("-")[0]) <= v <= float(t.split("-")[1]),
    "==": lambda v, t: v == t,
}
FLAG_FIELDS = {"recent_default", "business_registered"}


def evaluate_eligibility(fields: dict, product: str = "business_loan") -> dict:
    """Apply the current eligibility rules stored in the KB. Missing/unknown values -> needs_review, never a pass."""
    passed, failed, unverified = [], [], []
    for rule in get_index().rules(product):
        name = rule["field"]
        value = fields.get(name)
        if value is None or value == "unknown":
            if name != "applicant_age":  # verified from KYC documents later, not asked on the call
                unverified.append(rule)
            continue
        if name in FLAG_FIELDS:
            value = "yes" if value is True else "no" if value is False else str(value).lower()
        ok = OPS[rule["operator"]](value, rule["value"])
        (passed if ok else failed).append(rule)
    purpose = str(fields.get("loan_purpose") or "")
    excluded = purpose.split(":", 1)[1] if purpose.startswith("excluded:") else None
    status = "not_eligible" if failed or excluded else "needs_review" if unverified else "pre_qualified"
    return {
        "status": status,
        "failed_rules": [{"rule_id": r["rule_id"], "description": r["description"]} for r in failed],
        "unverified_rules": [{"rule_id": r["rule_id"], "description": r["description"]} for r in unverified],
        "passed_rules": [r["rule_id"] for r in passed],
        "excluded_purpose": excluded,
        "rules_version": get_index().records[0]["kb_version"],
        "disclaimer": "Preliminary check only, not an approval; final decision subject to credit assessment.",
    }


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


class BusinessLoanAgent(FlowAgent):
    def format_money(self, value: float) -> str:
        if value >= 1e7:
            return f"{value / 1e7:g} crore rupees"
        if value >= 1e5:
            return f"{value / 1e5:g} lakh rupees"
        return f"{value:,.0f} rupees"

    def evaluate(self, session: Session) -> str:
        result = evaluate_eligibility(session.slots)
        session.outcome = result
        actions.record(session, "eligibility_check", result)
        parts = []
        if result["excluded_purpose"]:
            parts.append(self.line("excluded_purpose", session, purpose=result["excluded_purpose"]))
        if result["status"] == "pre_qualified":
            parts.append(self.line("eligible", session))
        elif result["status"] == "not_eligible":
            reasons = "; ".join(_lower_first(r["description"]) for r in result["failed_rules"]) or "the loan purpose is not supported"
            parts.append(self.line("not_eligible", session, reasons=reasons))
        else:
            reasons = "; ".join(_lower_first(r["description"]) for r in result["unverified_rules"])
            parts.append(self.line("needs_review", session, reasons=reasons))
        parts.append(self.line("disclosure", session))
        return " ".join(parts)

    def on_filled(self, session: Session, slot: str) -> str | None:
        if session.context.get("annualized_slot") == slot:
            session.context.pop("annualized_slot")
            return self.line("turnover_annualized", session, value=self.format_money(session.slots[slot]))
        if slot == "callback_wanted" and session.slots[slot] is False:
            return self.line("callback_declined", session)
        if slot == "callback_time":
            when, adjusted = self._within_hours(session.slots[slot])
            session.slots[slot] = when
            actions.record(session, "callback_scheduled", {"when": when, "timezone": "Asia/Kolkata",
                                                            "summary": self.crm_summary(session)})
            line = "callback_outside_hours" if adjusted else "callback_confirmed"
            return self.line(line, session, when=self._speak_time(when))
        return super().on_filled(session, slot)

    def _within_hours(self, when: str) -> tuple[str, bool]:
        hours = self.script["business_rules"]["callback_hours"]
        dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
        start = datetime.strptime(hours["start"], "%H:%M").time()
        end = datetime.strptime(hours["end"], "%H:%M").time()
        adjusted = False
        if dt.time() < start or dt.time() > end:
            dt = dt.replace(hour=start.hour, minute=start.minute) + (timedelta(days=1) if dt.time() > end else timedelta())
            adjusted = True
        while dt.weekday() not in hours["days"]:
            dt += timedelta(days=1)
            adjusted = True
        return dt.strftime("%Y-%m-%d %H:%M"), adjusted

    @staticmethod
    def _speak_time(when: str) -> str:
        return datetime.strptime(when, "%Y-%m-%d %H:%M").strftime("%A %d %B at %I:%M %p").replace(" 0", " ")
