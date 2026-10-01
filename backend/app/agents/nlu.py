"""Deterministic, multilingual slot extraction (English, Filipino/Taglish, Indonesian incl. colloquial/regional).
Kept rule-based on purpose: values that drive eligibility decisions must be auditable."""
import re
from datetime import date, timedelta

WORD_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "twenty five": 25, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "a": 1, "an": 1, "half": 0.5, "couple": 2, "few": 3,
    # Filipino
    "isa": 1, "isang": 1, "dalawa": 2, "dalawang": 2, "tatlo": 3, "tatlong": 3, "apat": 4, "lima": 5, "limang": 5,
    "anim": 6, "pito": 7, "walo": 8, "siyam": 9, "sampu": 10, "sampung": 10,
    # Indonesian
    "satu": 1, "se": 1, "dua": 2, "tiga": 3, "empat": 4, "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
    "sepuluh": 10, "seratus": 100, "dua puluh": 20, "tiga puluh": 30, "dua puluh lima": 25,
}
_WORDS_RE = "|".join(sorted((re.escape(w) for w in WORD_NUM), key=len, reverse=True))
NUM = rf"(?<![\w.,])(\d+(?:[.,]\d+)*|(?:{_WORDS_RE})(?!\w))"
MULTIPLIERS = {
    "crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5,
    "million": 1e6, "mil": 1e6, "m": 1e6, "milyon": 1e6, "juta": 1e6, "jt": 1e6, "jeti": 1e6,
    "thousand": 1e3, "k": 1e3, "libo": 1e3, "ribu": 1e3, "rb": 1e3, "rebu": 1e3, "hundred": 100, "ratus": 100, "daan": 100,
}
_MULT_RE = "|".join(sorted(MULTIPLIERS, key=len, reverse=True))

# regional / colloquial Indonesian and Javanese/Sundanese tokens normalized before intent matching
REGIONAL_NORMALIZE = {
    "mboten": "tidak", "ora": "tidak", "ndak": "tidak", "nda": "tidak", "teu": "tidak", "henteu": "tidak", "gak": "tidak",
    "nggak": "tidak", "ngga": "tidak", "enggak": "tidak", "ga": "tidak", "kagak": "tidak",
    "nggih": "iya", "inggih": "iya", "enggih": "iya", "muhun": "iya", "yoi": "iya", "yo": "iya",
    "sampun": "sudah", "wis": "sudah", "udah": "sudah", "dah": "sudah", "parantos": "sudah",
    "durung": "belum", "acan": "belum", "blm": "belum", "sesok": "besok", "enjing": "besok", "isuk": "besok",
    "duit": "uang", "gajian": "gajian", "bayarnya": "bayar",
}
REGIONAL_MARKERS = {
    "javanese": {"mboten", "nggih", "inggih", "sampun", "monggo", "piye", "ora", "durung", "sesok", "matur", "nuwun", "mas", "mbak", "wis", "lho", "tho", "rek"},
    "sundanese": {"teh", "aa", "akang", "euy", "atuh", "mah", "teu", "henteu", "muhun", "parantos", "acan", "nya"},
    "betawi": {"aye", "ente", "kagak", "kudu", "gimane", "ape"},
    "medan_batak": {"bah", "lae", "kek", "kau", "tulang", "inang"},
}


def normalize_regional(text: str) -> str:
    return " ".join(REGIONAL_NORMALIZE.get(w, w) for w in re.findall(r"[\w'.,%-]+|\S", text.lower()))


def regional_markers(text: str) -> list[str]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return sorted(d for d, markers in REGIONAL_MARKERS.items() if len(words & markers) >= 1)


def _to_number(token: str) -> float | None:
    token = token.lower().strip()
    if token in WORD_NUM:
        return float(WORD_NUM[token])
    cleaned = token.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{2,3})+(\.\d+)?", token) else token
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):  # Indonesian thousands separator: 850.000
        cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_money(text: str) -> float | None:
    low = text.lower().replace("₹", " ").replace("₱", " ").replace("php", " ")
    low = re.sub(r"\brp\.?\s*", " ", low)
    low = re.sub(r"\bsejuta\b", "1 juta", low).replace("setengah", "0.5")
    m = re.search(rf"{NUM}\s*({_MULT_RE})\b", low)
    if m:
        base = _to_number(m.group(1))
        return base * MULTIPLIERS[m.group(2)] if base is not None else None
    m = re.search(r"\b(\d{1,3}(?:[,.]\d{2,3})+|\d{4,})\b", low)
    return _to_number(m.group(1)) if m else None


def is_monthly(text: str) -> bool:
    return bool(re.search(r"per month|a month|monthly|every month|/month|kada buwan|buwan-buwan|sebulan|per bulan|tiap bulan", text, re.I))


def parse_years(text: str, today: date | None = None) -> float | None:
    today = today or date.today()
    low = text.lower()
    m = re.search(r"\b(since|from|noong|sejak|dari)\s+(?:the year\s+)?((?:19|20)\d{2})\b", low)
    if m:
        return float(today.year - int(m.group(2)))
    m = re.search(rf"{NUM}\s*(?:and a half\s*)?(years?|yrs?|taon|tahun|thn)\b", low)
    if m:
        val = _to_number(m.group(1))
        if val is not None and "and a half" in low[m.start():m.end()]:
            val += 0.5
        return val
    m = re.search(rf"{NUM}\s*(months?|buwan|bulan)\b", low)
    if m and (val := _to_number(m.group(1))) is not None:
        return round(val / 12, 2)
    if re.search(r"last year|just started|new business|kakasimula|baru buka|tahun lalu", low):
        return 1.0 if "last year" in low or "tahun lalu" in low else 0.5
    return None


def parse_number(text: str, lo: float, hi: float) -> float | None:
    for m in re.finditer(rf"{NUM}", text.lower()):
        val = _to_number(m.group(1))
        if val is not None and lo <= val <= hi:
            return val
    return None


YES = r"\b(yes|yeah|yep|yup|sure|correct|right|okay|ok|of course|definitely|go ahead|oo|opo|oho|sige|tama|pwede|iya|ya|betul|benar|boleh|siap|bisa|baik)\b"
NO = r"\b(no|nope|nah|not really|never|none|don't|do not|haven't|hindi|wala|ayoko|tidak|bukan|jangan)\b"


def parse_yes_no(text: str) -> bool | None:
    low = normalize_regional(text)
    no, yes = re.search(NO, low), re.search(YES, low)
    if no and (not yes or no.start() < yes.start()):
        return False
    return True if yes else None


UNKNOWN = re.compile(r"\b(don't know|do not know|not sure|no idea|never checked|can't remember|hindi ko alam|di ko alam|"
                     r"ewan|tidak tahu|nggak tahu|gak tau|ga tau|kurang tahu|lupa)\b", re.I)

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
            "lunes": 0, "martes": 1, "miyerkules": 2, "huwebes": 3, "biyernes": 4, "sabado": 5, "linggo": 6,
            "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3, "jumat": 4, "sabtu": 5, "minggu": 6}


def parse_date(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    low = normalize_regional(text)
    if re.search(r"\b(today|ngayon|hari ini|sekarang)\b", low):
        return today
    if re.search(r"day after tomorrow|lusa|sa makalawa", low):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|bukas|besok)\b", low):
        return today + timedelta(days=1)
    if re.search(r"next week|minggu depan|susunod na linggo|pekan depan", low):
        return today + timedelta(days=7)
    m = re.search(r"\b(?:on the|tanggal|tgl|sa|petsa)?\s*(\d{1,2})(?:st|nd|rd|th)?\b", low)
    if m and re.search(r"tanggal|tgl|\bon the\b|\d(st|nd|rd|th)\b|\bpetsa\b|\bsa \d", low):
        day = int(m.group(1))
        if 1 <= day <= 31:
            month, year = today.month, today.year
            if day < today.day:
                month, year = (1, year + 1) if month == 12 else (month + 1, year)
            try:
                return date(year, month, day)
            except ValueError:
                return None
    for name, wd in WEEKDAYS.items():
        if re.search(rf"\b{name}\b", low) and not (name == "minggu" and "minggu depan" in low):
            return today + timedelta(days=(wd - today.weekday()) % 7 or 7)
    m = re.search(r"\bin (\d+|a|two|three) days?\b|(\d+) hari lagi", low)
    if m:
        n = _to_number(m.group(1) or m.group(2))
        return today + timedelta(days=int(n or 1))
    return None


def parse_time_of_day(text: str) -> str | None:
    low = text.lower()
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", low)
    if m:
        hour = int(m.group(1)) % 12 + (12 if m.group(3).startswith("p") else 0)
        return f"{hour:02d}:{m.group(2) or '00'}"
    m = re.search(r"\b(?:jam|pukul|alas)\s*(\d{1,2})(?:[.:](\d{2}))?", low)
    if m:
        hour = int(m.group(1))
        if re.search(r"sore|malam|hapon|gabi", low) and hour < 12:
            hour += 12
        return f"{hour:02d}:{m.group(2) or '00'}"
    for words, slot in ((r"morning|umaga|pagi", "10:00"), (r"afternoon|hapon|siang|sore", "15:00"), (r"evening|gabi|malam", "17:30")):
        if re.search(words, low):
            return slot
    return None
