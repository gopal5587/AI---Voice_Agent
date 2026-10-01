"""Market-specific agents for Q3. Wording, register, number/date formats, and rules live in each script;
these classes only add the market-specific calculations and actions."""
from datetime import date, datetime, timedelta, timezone

from . import actions
from .engine import FlowAgent, Session

ID_MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
ID_DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
TL_DAYS = ["Lunes", "Martes", "Miyerkules", "Huwebes", "Biyernes", "Sabado", "Linggo"]


def format_php(value: float) -> str:
    return f"₱{value:,.0f}"


def format_idr(value: float) -> str:
    return "Rp" + f"{value:,.0f}".replace(",", ".")


def id_date(d: date) -> str:
    return f"{ID_DAYS[d.weekday()]}, {d.day} {ID_MONTHS[d.month - 1]} {d.year}"


class PhilippinesLifeAgent(FlowAgent):
    def format_money(self, value: float) -> str:
        return format_php(value)

    def evaluate(self, session: Session) -> str:
        rules = self.script["business_rules"]
        lo, hi = rules["entry_age"]
        age = session.slots.get("age")
        parts = []
        if isinstance(age, (int, float)) and not lo <= age <= hi:
            session.outcome = {"status": "age_out_of_range", "age": age}
            parts.append(self.line("age_out_of_range", session, min_age=lo, max_age=hi))
        else:
            illus = rules["illustration"]
            budget = session.slots.get("monthly_budget_php")
            coverage = None
            if isinstance(budget, (int, float)):
                c_lo, c_hi = rules["coverage_bounds_php"]
                coverage = min(c_hi, max(c_lo, round(budget / illus["premium_php"] * illus["per_coverage_php"], -5)))
            session.outcome = {"status": "qualified_lead", "indicative_coverage_php": coverage,
                               "basis": f"illustration: PHP {illus['premium_php']}/month per PHP {illus['per_coverage_php']:,} ({illus['profile']})"}
            if coverage:
                parts.append(self.line("quote_summary", session, budget=format_php(budget), coverage=format_php(coverage)))
            if session.slots.get("coverage_goal") == "critical_illness":
                parts.append(self.line("rider_hint", session))
            if session.slots.get("dependents") not in (None, "none"):
                parts.append(self.kb_fact(session, "how many beneficiaries can I name"))
            actions.record(session, "quotation_request", {"slots": session.slots, "outcome": session.outcome})
        parts.append(self.line("not_advisor", session))
        return " ".join(parts)

    def on_filled(self, session: Session, slot: str) -> str | None:
        if slot == "advisor_callback" and session.slots[slot] is False:
            return self.line("callback_declined", session)
        if slot == "callback_time":
            when = datetime.strptime(session.slots[slot], "%Y-%m-%d %H:%M")
            spoken = (f"{TL_DAYS[when.weekday()]}, {when.strftime('%B')} {when.day}, alas-{when.strftime('%I:%M').lstrip('0')} "
                      f"ng {'umaga' if when.hour < 12 else 'hapon'}") if session.lang == "tl" else when.strftime("%A, %B %d at %I:%M %p")
            actions.record(session, "callback_scheduled", {"when": session.slots[slot], "timezone": "Asia/Manila",
                                                            "summary": self.crm_summary(session)})
            return self.line("callback_confirmed", session, when=spoken)
        return super().on_filled(session, slot)


class IndonesiaReminderAgent(FlowAgent):
    def format_money(self, value: float) -> str:
        return format_idr(value)

    def on_start(self, session: Session) -> None:
        rules = self.script["business_rules"]
        acct = rules["mock_account"]
        due = session.today_date + timedelta(days=acct["due_in_days"])
        local_hour = (datetime.now(timezone.utc) + timedelta(hours=rules["utc_offset_hours"])).hour
        daypart = "pagi" if local_hour < 11 else "siang" if local_hour < 15 else "sore" if local_hour < 18 else "malam"
        start_h, end_h = (int(t[:2]) for t in rules["contact_hours_local"])
        session.context.update({
            "customer_title": acct["customer_title"], "customer_name": acct["customer_name"],
            "installment_no": acct["installment_no"], "vehicle": acct["vehicle"],
            "amount_text": format_idr(acct["amount_idr"]), "due_text": id_date(due), "due_date": due.isoformat(),
            "daypart": daypart, "within_contact_hours": start_h <= local_hour < end_h,
        })

    def handle(self, session: Session, user_text: str) -> dict:
        if session.pending == "payment_date" and self._match("objection", user_text.lower()) and "bayar" in user_text.lower() \
                and any(w in user_text.lower() for w in ("sudah", "udah", "sampun", "wis")):
            session.slots["payment_date"] = "claimed_paid"
            session.outcome = {"status": "claimed_paid"}
            actions.record(session, "payment_claim", {"note": "customer states installment already paid; verify"})
            session.context.setdefault("queued_lines", []).append(self.line("claimed_paid", session))
        return super().handle(session, user_text)

    def on_hardship(self, session: Session) -> str | None:
        if not session.context.get("hardship_flagged"):
            session.context["hardship_flagged"] = True
            actions.record(session, "hardship_flag", {"note": "possible restructuring case; route to collections officer"})
            return self.line("hardship_noted", session)
        return None

    def on_filled(self, session: Session, slot: str) -> str | None:
        if slot == "payment_date" and session.slots[slot] != "claimed_paid":
            pay = date.fromisoformat(session.slots[slot])
            due = date.fromisoformat(session.context["due_date"])
            days_late = (pay - due).days
            amount = self.script["business_rules"]["mock_account"]["amount_idr"]
            penalty = amount * self.script["business_rules"]["late_fee_rate_per_day"] * max(0, days_late)
            session.outcome = {"status": "promise_to_pay", "payment_date": pay.isoformat(), "days_late": max(0, days_late),
                               "estimated_penalty_idr": penalty}
            actions.record(session, "promise_to_pay", session.outcome)
            if days_late > 0:
                return self.line("promise_late", session, date_text=id_date(pay), days_late=days_late, penalty_text=format_idr(penalty))
            return self.line("promise_on_time", session, date_text=id_date(pay))
        if slot == "payment_date":
            session.outcome = {"status": "claimed_paid"}
            return self.line("claimed_paid", session)
        if slot == "payment_channel":
            names = {"va_bca": "virtual account BCA", "va_bri": "virtual account BRI", "va_mandiri": "virtual account Mandiri",
                     "retail": "gerai Indomaret/Alfamart", "app": "aplikasi Sinar Mobile", "undecided": "metode yang belum ditentukan"}
            text = self.line("channel_noted", session, channel_text=names[session.slots[slot]])
            if session.slots[slot] == "retail":
                text += " " + self.kb_fact(session, "biaya admin pembayaran gerai ritel Indomaret Alfamart")
            return text
        return super().on_filled(session, slot)

    def evaluate(self, session: Session) -> str:
        session.outcome = {**(session.outcome or {}), "channel": session.slots.get("payment_channel"),
                           "hardship": bool(session.context.get("hardship_flagged")),
                           "within_contact_hours": session.context["within_contact_hours"]}
        return ""
