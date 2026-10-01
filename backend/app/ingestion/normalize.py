"""Date, terminology, heading, category, and form-field standardization."""
import re
from datetime import datetime

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%b %d, %Y", "%B %d, %Y"]


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# canonical term -> variants found in sources and in spoken queries
GLOSSARY: dict[str, list[str]] = {
    "loan amount": ["borrow", "how much can i get", "maximum loan", "loan size"],
    "tenure": ["how long", "repayment period", "loan duration", "tenor"],
    "emi": ["monthly instalment", "monthly installment", "instalment", "installment", "emis"],
    "turnover": ["revenue", "annual revenue", "sales", "annual sales"],
    "credit score": ["cibil", "cibil score", "credit rating", "bureau score"],
    "business vintage": ["years in business", "business age", "operating history", "how old is the business", "running"],
    "eligibility": ["qualify", "eligible", "qualification", "criteria"],
    "foreclosure": ["prepay", "prepayment", "close the loan early", "pay off early", "foreclose"],
    "processing fee": ["file charge", "upfront fee", "processing charge"],
    "collateral": ["security", "guarantee property", "mortgage", "pledge"],
    "late payment charge": ["penalty", "missed emi", "late fee", "bounce"],
    "relationship manager": ["human", "person", "agent", "executive", "speak to someone"],
    "documents": ["papers", "kyc", "paperwork"],
    # Philippines
    "premium": ["hulog", "bayad buwan-buwan", "monthly payment"],
    "beneficiary": ["benepisyaryo", "beneficiaries"],
    "lapse": ["nag-lapse", "lapsed", "ma-lapse"],
    "rider": ["add-on", "riders"],
    "coverage": ["sum assured", "face amount"],
    # Indonesia
    "angsuran": ["cicilan", "installment", "kredit bulanan"],
    "denda": ["penalti", "late fee", "biaya keterlambatan"],
    "jatuh tempo": ["due date", "tanggal bayar"],
    "pelunasan dipercepat": ["lunasin", "pelunasan", "early settlement"],
    "restrukturisasi": ["keringanan", "reschedule", "restruktur"],
}
_VARIANT_TO_CANON = {v: canon for canon, variants in GLOSSARY.items() for v in variants}


def canonical_terms(text: str) -> list[str]:
    low = text.lower()
    found = {canon for canon in GLOSSARY if canon in low}
    found |= {canon for variant, canon in _VARIANT_TO_CANON.items() if re.search(rf"\b{re.escape(variant)}\b", low)}
    return sorted(found)


def expand_query(query: str) -> str:
    """Append canonical terms so lexical retrieval matches inconsistent source terminology."""
    extra = []
    for canon in canonical_terms(query):
        extra.append(canon)
        extra.extend(GLOSSARY[canon][:2])
    return query + (" " + " ".join(extra) if extra else "")


def normalize_heading(heading: str) -> str:
    heading = re.sub(r"^(FAQ|Objection|Keberatan)\s*:\s*", "", heading.strip(), flags=re.I)
    heading = heading.rstrip("?").strip()
    return heading[:1].upper() + heading[1:]


CATEGORY_RULES: list[tuple[str, str]] = [
    (r"^(objection|keberatan)\b", "objection_handling"),
    (r"compliance|etika|rules for agents", "compliance"),
    (r"speak to a person|eskalasi|human", "contact_escalation"),
    (r"^faq\b|\?$", "faq"),
    (r"interest|fee|charge|denda|premium|commission|cicilan", "pricing_fees"),
    (r"vintage|credit score|turnover|eligib|entry age|women entrepreneurs|excluded", "eligibility_rule"),
]


def assign_category(heading: str, default: str) -> str:
    if default in ("eligibility_rule", "form_schema", "partnership_benefits", "pricing_fees"):
        return default
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, heading.strip(), re.I):
            return category
    return default


FORM_FIELD_MAP = {
    "appl_name": ("applicant_name", True),
    "mob": ("mobile_number", True),
    "biz_nm": ("business_name", False),
    "biz_type": ("business_constitution", False),
    "yrs_in_biz": ("business_vintage_years", False),
    "ann_rev": ("annual_turnover_inr", False),
    "loan_amt": ("loan_amount_inr", False),
    "purpose": ("loan_purpose", False),
    "cibil": ("credit_score", False),
    "dob": ("date_of_birth", True),
    "pan_no": ("pan", True),
    "consent": ("credit_bureau_consent", False),
}


def normalize_form_fields(fields: list[dict]) -> list[dict]:
    out = []
    for f in fields:
        canonical, is_pii = FORM_FIELD_MAP.get(f["source_name"], (f["source_name"], False))
        out.append({**f, "canonical_name": canonical, "pii_field": is_pii})
    return out
