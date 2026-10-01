"""Build the knowledge base: raw sources -> cleaned, PII-safe, deduplicated, versioned, traceable records."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from . import dedup, normalize, pii
from .models import ExtractionError, Section
from .parsers import parse

MAX_WORDS = 220  # ~300 tokens; sections above this are split on sentence boundaries


def _slug(text: str, limit: int = 32) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:limit].strip("_")


def _record_id(market: str, source_id: str, heading: str, part: int) -> str:
    digest = hashlib.sha1(f"{source_id}|{heading}|{part}".encode()).hexdigest()[:6]
    return f"kb_{market.lower()}_{_slug(heading)}_{digest}"


def _chunks(text: str) -> list[str]:
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], []
    for sent in sentences:
        if current and len(" ".join(current + [sent]).split()) > MAX_WORDS:
            chunks.append(" ".join(current))
            current = current[-1:]  # one-sentence overlap keeps context across the split
        current.append(sent)
    if current:
        chunks.append(" ".join(current))
    return chunks


def build(raw_dir: Path | None = None, out_dir: Path | None = None) -> dict:
    raw_dir = raw_dir or settings.raw_dir
    out_dir = out_dir or settings.processed_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    registry = json.loads((raw_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    registered = {s["path"] for s in registry}

    report: dict = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": [],
                    "unregistered_files": [], "duplicates": [], "version_conflicts": [], "quality_flags": []}
    for f in raw_dir.rglob("*"):
        rel = f.relative_to(raw_dir).as_posix()
        if f.is_file() and rel not in registered and f.name not in ("sources.json", "README.md"):
            report["unregistered_files"].append(rel)

    records: list[dict] = []
    for src in registry:
        path = raw_dir / src["path"]
        entry = {"source_id": src["source_id"], "path": src["path"], "status": "ok"}
        try:
            doc = parse(path)
        except (ExtractionError, FileNotFoundError, UnicodeDecodeError) as exc:
            entry.update(status="extraction_failed", error=str(exc))
            report["sources"].append(entry)
            continue

        version = src.get("version") or doc.meta.get("version") or "1.0"
        effective = normalize.normalize_date(doc.meta.get("effective_from") or doc.meta.get("last_updated"))
        entry.update(sections=len(doc.sections), boilerplate_blocks_removed=len(doc.removed_boilerplate),
                     version=version, effective_from=effective, pii_redactions={})
        for flag in doc.quality_flags:
            report["quality_flags"].append({"source_id": src["source_id"], **flag})

        for section in doc.sections:
            records.extend(_section_records(src, doc.title, section, version, effective, entry))
        report["sources"].append(entry)

    records = _deduplicate(records, report)
    _link_versions(records, report)
    records.sort(key=lambda r: (r["market"], r["source_id"], r["source_locator"]))

    kb_version = hashlib.sha1("".join(r["content_hash"] for r in records).encode()).hexdigest()[:10]
    for r in records:
        r["kb_version"] = kb_version
    previous = _load_previous(out_dir / "kb_records.jsonl")
    changelog = _changelog(previous, records, kb_version, out_dir / "kb_changelog.json")

    with (out_dir / "kb_records.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    report["summary"] = {
        "kb_version": kb_version,
        "records_total": len(records),
        "records_current": sum(r["status"] == "current" for r in records),
        "records_superseded": sum(r["status"] == "superseded" for r in records),
        "sources_ok": sum(s["status"] == "ok" for s in report["sources"]),
        "sources_failed": sum(s["status"] != "ok" for s in report["sources"]),
        "duplicates_removed": len(report["duplicates"]),
        "pii_redactions": sum(sum(s.get("pii_redactions", {}).values()) for s in report["sources"]),
        "quality_flags": len(report["quality_flags"]),
        "changes_vs_previous_build": changelog,
    }
    (out_dir / "ingestion_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _section_records(src: dict, doc_title: str, section: Section, version: str, effective: str | None, entry: dict) -> list[dict]:
    heading = normalize.normalize_heading(section.heading)
    category = normalize.assign_category(section.heading, src["default_category"])
    text, found = pii.redact(section.text)
    if section.raw_text:
        found = pii.redact(section.raw_text)[1]
    for label in found:
        entry["pii_redactions"][label] = entry["pii_redactions"].get(label, 0) + 1
    structured = section.structured
    if structured and "fields" in structured:
        structured = {"fields": normalize.normalize_form_fields(structured["fields"])}

    out = []
    for part, chunk in enumerate(_chunks(text)):
        out.append({
            "record_id": _record_id(src["market"], src["source_id"], heading, part),
            "title": heading if heading.lower() != doc_title.lower() else doc_title,
            "doc_title": doc_title,
            "content": chunk,
            "category": category,
            "product": src["product"],
            "market": src["market"],
            "lang": src.get("lang", "en"),
            "source_id": src["source_id"],
            "source_type": src["source_type"],
            "source_uri": src.get("url") or f"data/raw/{src['path']}",
            "source_locator": section.locator + (f"/part-{part}" if part else ""),
            "version": version,
            "effective_from": effective,
            "status": src.get("status", "current"),
            "superseded_by": None,
            "content_hash": dedup.content_hash(chunk),
            "pii": pii.contains_pii(chunk),
            "pii_redacted": bool(found),
            "terms": normalize.canonical_terms(heading + " " + chunk),
            "structured": structured,
        })
    return out


def _deduplicate(records: list[dict], report: dict) -> list[dict]:
    # current records win over superseded ones; within a status, registry order wins
    ordered = sorted(enumerate(records), key=lambda ir: (ir[1]["status"] != "current", ir[0]))
    kept: list[dict] = []
    seen_hash: dict[str, str] = {}
    shingle_cache: list[tuple[dict, set]] = []
    for _, rec in ordered:
        h = rec["content_hash"]
        if h in seen_hash:
            report["duplicates"].append({"removed": rec["record_id"], "locator": rec["source_locator"],
                                         "duplicate_of": seen_hash[h], "type": "exact"})
            continue
        sh = dedup.shingles(rec["content"])
        # a superseded record that is only similar to its replacement is a version change, not a duplicate
        match = next((k for k, ks in shingle_cache if k["market"] == rec["market"] and k["status"] == rec["status"]
                      and dedup.jaccard(sh, ks) >= dedup.NEAR_DUP_THRESHOLD), None)
        if match:
            report["duplicates"].append({"removed": rec["record_id"], "locator": rec["source_locator"],
                                         "duplicate_of": match["record_id"], "type": "near",
                                         "similarity": round(dedup.jaccard(sh, dedup.shingles(match["content"])), 3)})
            continue
        seen_hash[h] = rec["record_id"]
        shingle_cache.append((rec, sh))
        kept.append(rec)
    return kept


def _link_versions(records: list[dict], report: dict) -> None:
    current = {(r["source_id"], r["title"].lower()): r for r in records if r["status"] == "current"}
    registry = json.loads((settings.raw_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    successor = {s["source_id"]: s.get("superseded_by_source") for s in registry}
    for r in records:
        if r["status"] != "superseded":
            continue
        newer = current.get((successor.get(r["source_id"]), r["title"].lower()))
        if newer:
            r["superseded_by"] = newer["record_id"]
            report["version_conflicts"].append({
                "topic": r["title"], "old": {"record_id": r["record_id"], "version": r["version"], "content": r["content"]},
                "new": {"record_id": newer["record_id"], "version": newer["version"], "content": newer["content"]},
            })


def _load_previous(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {(r := json.loads(line))["record_id"]: r["content_hash"] for line in path.read_text(encoding="utf-8").splitlines() if line}


def _changelog(previous: dict[str, str], records: list[dict], kb_version: str, path: Path) -> dict:
    now = {r["record_id"]: r["content_hash"] for r in records}
    diff = {
        "added": sorted(set(now) - set(previous)),
        "removed": sorted(set(previous) - set(now)),
        "changed": sorted(k for k in set(now) & set(previous) if now[k] != previous[k]),
    }
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not history or history[-1]["kb_version"] != kb_version:
        history.append({"kb_version": kb_version, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "records": len(records), **{k: len(v) for k, v in diff.items()}})
        path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return {k: len(v) for k, v in diff.items()}


if __name__ == "__main__":
    print(json.dumps(build()["summary"], indent=2))
