"""Pattern + context based PII detection and redaction. Applied before anything is indexed or logged."""
import re

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@(?!kosha-demo\.example\b)[\w-]+\.[\w.]+\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("AADHAAR", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("PHONE", re.compile(r"(?:\+91[ -]?)?\b[6-9]\d{4}[ -]?\d{5}\b|\+?63[ -]?9\d{2}[ -]?\d{3}[ -]?\d{4}\b|\b09\d{2}[ -]?\d{3}[ -]?\d{4}\b|\+?62[ -]?8\d{2}[ -]?\d{3,4}[ -]?\d{3,4}\b|\b08\d{2}[ -]?\d{3,4}[ -]?\d{3,4}\b")),
]
# names are only redacted where a role word signals a person, which keeps product names intact
NAME_CONTEXT = re.compile(r"\b(Customer|Caller|Mr\.?|Mrs\.?|Ms\.?|Bapak|Ibu|Pak|Bu|Ma'am|Sir)\s+((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+){0,2})")
NAME_STOPWORDS = {"Answer", "The", "At", "Service", "Care"}


def redact(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    for label, pattern in PATTERNS:
        text, n = pattern.subn(f"[{label}]", text)
        found += [label] * n

    def _name(m: re.Match) -> str:
        if m.group(2).split()[0] in NAME_STOPWORDS:
            return m.group(0)
        found.append("NAME")
        return f"{m.group(1)} [NAME]"

    text = NAME_CONTEXT.sub(_name, text)
    return text, found


def contains_pii(text: str) -> bool:
    return bool(redact(text)[1])
