"""Format-specific extractors. Each returns a ParsedDoc of heading-scoped sections with source locators."""
import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .models import ExtractionError, ParsedDoc, Section

BOILERPLATE_TAGS = ["nav", "header", "footer", "script", "style", "noscript", "aside"]
BOILERPLATE_CLASS = re.compile(r"cookie|banner|promo|newsletter|social|breadcrumb", re.I)
DATE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[-/][A-Za-z]{3}[-/]\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|[A-Za-z]{3,9} \d{1,2}, \d{4})"
META_LINE = re.compile(rf"(version|versi)\s*:?\s*(\d[\w.]*)|(effective|berlaku)\s*(from)?\s*:?\s*{DATE}", re.I)


def parse_html(path: Path) -> ParsedDoc:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    removed: list[str] = []
    for tag in soup.find_all(BOILERPLATE_TAGS):
        removed.append(_squash(tag.get_text(" ")))
        tag.decompose()
    for tag in soup.find_all(class_=BOILERPLATE_CLASS):
        removed.append(_squash(tag.get_text(" ")))
        tag.decompose()

    meta: dict = {}
    updated = soup.find("meta", attrs={"name": "last-updated"})
    if updated:
        meta["last_updated"] = updated.get("content")

    if soup.find("form"):
        return _parse_form(soup, path, removed)

    root = soup.find("main") or soup.body or soup
    h1 = root.find("h1")
    title = _squash(h1.get_text()) if h1 else path.stem
    sections: list[Section] = []
    for idx, h2 in enumerate(root.find_all("h2"), start=1):
        parts = []
        for sib in h2.find_next_siblings():
            if sib.name in ("h1", "h2"):
                break
            parts.append(_squash(sib.get_text(" ")))
        text = " ".join(p for p in parts if p)
        if text:
            sections.append(Section(_squash(h2.get_text()), text, f"{path.name}#h2-{idx}"))
    if not sections:
        raise ExtractionError("no heading-scoped content found in HTML main body")
    return ParsedDoc(title, sections, meta, removed)


def _parse_form(soup: BeautifulSoup, path: Path, removed: list[str]) -> ParsedDoc:
    fields = []
    for label in soup.find_all("label"):
        target = label.get("for")
        control = soup.find(id=target) if target else label.find("input")
        if control is None:
            continue
        fields.append({
            "source_name": control.get("name"),
            "label": _squash(label.get_text()).rstrip("*").strip(),
            "required": control.has_attr("required"),
            "type": control.get("type", control.name),
        })
    h1 = soup.find("h1")
    title = _squash(h1.get_text()) if h1 else path.stem
    text = "Application form fields: " + "; ".join(f["label"] for f in fields) + "."
    return ParsedDoc(title, [Section("Form Fields", text, f"{path.name}#form", {"fields": fields})], {}, removed)


def parse_markdown(path: Path) -> ParsedDoc:
    lines = path.read_text(encoding="utf-8").splitlines()
    title, meta, sections = path.stem, {}, []
    heading, buf, idx = None, [], 0

    def flush():
        if heading and buf:
            text = _squash(" ".join(buf).replace("- ", "; "))
            sections.append(Section(heading, text.lstrip("; "), f"{path.name}#sec-{idx}"))

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            idx += 1
            heading, buf = line[3:].strip(), []
        elif heading is None:
            for m in META_LINE.finditer(line):
                if m.group(2):
                    meta["version"] = m.group(2)
                if m.group(5):
                    meta["effective_from"] = m.group(5).strip()
        elif line.strip():
            buf.append(line.strip())
    flush()
    if not sections:
        raise ExtractionError("markdown has no '##' sections")
    return ParsedDoc(title, sections, meta)


def parse_pdf(path: Path) -> ParsedDoc:
    try:
        reader = PdfReader(str(path))
        pages = [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    except (PdfReadError, ValueError, KeyError, OSError) as exc:
        raise ExtractionError(f"unreadable PDF: {exc.__class__.__name__}: {exc}") from exc
    if not any(t.strip() for _, t in pages):
        raise ExtractionError("PDF contains no extractable text (scanned image? needs OCR)")

    title, meta, sections, removed = path.stem, {}, [], []
    heading, buf, page_of_heading = None, [], 1
    for page_no, text in pages:
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if re.search(r"confidential|page \d+", line, re.I):
                removed.append(line)
                continue
            if title == path.stem:
                title = line
                continue
            if META_LINE.search(line) and not sections and heading is None:
                for m in META_LINE.finditer(line):
                    if m.group(2):
                        meta["version"] = m.group(2)
                    if m.group(5):
                        meta["effective_from"] = m.group(5).strip()
                continue
            if _looks_like_heading(line):
                if heading and buf:
                    sections.append(Section(heading, _squash(" ".join(buf)), f"{path.name}#page-{page_of_heading}"))
                heading, buf, page_of_heading = line, [], page_no
            else:
                buf.append(line)
    if heading and buf:
        sections.append(Section(heading, _squash(" ".join(buf)), f"{path.name}#page-{page_of_heading}"))
    if not sections:
        raise ExtractionError("PDF text found but no sections could be segmented")
    return ParsedDoc(title, sections, meta, removed)


def _looks_like_heading(line: str) -> bool:
    words = line.split()
    return len(words) <= 4 and not line.endswith(".") and all(w[0].isupper() for w in words if w[0].isalpha())


def parse_csv(path: Path) -> ParsedDoc:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ExtractionError("CSV has no data rows")
    flags, sections, seen = [], [], {}
    is_rules = "rule_id" in rows[0]
    for n, row in enumerate(rows, start=2):
        row = {k.strip(): (v or "").strip() for k, v in row.items()}
        locator = f"{path.name}#row-{n}"
        if is_rules:
            sections.append(Section(row["rule_id"], row["description"] + ".", locator, row))
            continue
        name, amount, notes = row.get("Charge", ""), row.get("Amount", ""), row.get("Notes", "")
        key = name.lower()
        if not amount:
            flags.append({"locator": locator, "issue": "missing_value", "detail": f"'{name}' has no amount"})
            continue
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", amount)
        bad = False
        if pct and float(pct.group(1)) > 10 and "month" not in amount:
            flags.append({"locator": locator, "issue": "suspicious_value", "detail": f"'{name}' = '{amount}' exceeds 10% sanity bound"})
            bad = True
        if key in seen:
            flags.append({"locator": locator, "issue": "conflicting_duplicate_row",
                          "detail": f"'{name}' = '{amount}' conflicts with {seen[key]}; kept first occurrence"})
            bad = True
        if bad:
            continue
        seen[key] = locator
        text = f"{name}: {amount}." + (f" {notes}." if notes else "")
        sections.append(Section(name, text, locator, {"charge": name, "amount": amount, "notes": notes}))
    return ParsedDoc(path.stem.replace("_", " ").title(), sections, {}, [], flags)


def parse_text(path: Path) -> ParsedDoc:
    content = path.read_text(encoding="utf-8")
    sections = []
    for m in re.finditer(r"Note (\d+):\s*(.+?)(?=\n\s*Note \d+:|\Z)", content, re.S):
        body = _squash(m.group(2))
        q = re.search(r"(?:asked|wanted to know)\s+(.+?)\.\s*Answer given:\s*(.+)", body)
        heading = q.group(1)[:80] if q else f"Note {m.group(1)}"
        text = f"Question: {q.group(1)}. Answer: {q.group(2)}" if q else body
        sections.append(Section(heading, text, f"{path.name}#note-{m.group(1)}", raw_text=body))
    if not sections:
        raise ExtractionError("no 'Note N:' entries found")
    return ParsedDoc(content.splitlines()[0].strip(), sections)


PARSERS = {".html": parse_html, ".htm": parse_html, ".md": parse_markdown, ".pdf": parse_pdf, ".csv": parse_csv, ".txt": parse_text}


def parse(path: Path) -> ParsedDoc:
    parser = PARSERS.get(path.suffix.lower())
    if parser is None:
        raise ExtractionError(f"no parser for {path.suffix}")
    return parser(path)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
