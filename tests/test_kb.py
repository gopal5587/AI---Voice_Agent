import json
import re

import pytest

from app.config import settings
from app.ingestion.dedup import NEAR_DUP_THRESHOLD, jaccard, shingles
from app.ingestion.pii import redact
from app.retrieval.answer import answer
from app.retrieval.index import get_index

RECORDS = [json.loads(line) for line in (settings.processed_dir / "kb_records.jsonl").read_text(encoding="utf-8").splitlines()]
REPORT = json.loads((settings.processed_dir / "ingestion_report.json").read_text(encoding="utf-8"))
SOURCES = {s["source_id"] for s in json.loads((settings.raw_dir / "sources.json").read_text(encoding="utf-8"))["sources"]}

PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@(?!kosha-demo\.example)[\w-]+\.[\w.]+"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "indian_mobile": re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"),
    "aadhaar": re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"),
}


def test_no_exact_duplicate_content():
    hashes = [r["content_hash"] for r in RECORDS if r["status"] == "current"]
    assert len(hashes) == len(set(hashes))


def test_duplicates_were_detected_and_removed():
    types = {d["type"] for d in REPORT["duplicates"]}
    assert REPORT["summary"]["duplicates_removed"] >= 2 and {"exact", "near"} <= types


def test_near_duplicate_threshold_separates_copies_from_versions():
    by_id = {r["record_id"]: r for r in RECORDS}
    near = [d for d in REPORT["duplicates"] if d["type"] == "near"]
    assert near and all(d["similarity"] >= NEAR_DUP_THRESHOLD for d in near)
    versions = [(r, by_id[r["superseded_by"]]) for r in RECORDS if r["status"] == "superseded"]
    assert all(jaccard(shingles(a["content"]), shingles(b["content"])) < NEAR_DUP_THRESHOLD for a, b in versions)


@pytest.mark.parametrize("label,pattern", PII_PATTERNS.items())
def test_no_pii_in_published_records(label, pattern):
    leaks = [r["record_id"] for r in RECORDS if pattern.search(r["content"])]
    assert not leaks, f"{label} found in {leaks}"


def test_redactor_masks_common_identifiers():
    text, labels = redact("Call Ravi Kumar at +91 98765 43210 or ravi.k@gmail.com, PAN ABCDE1234F")
    assert "98765" not in text and "gmail" not in text and "ABCDE1234F" not in text
    assert {"PHONE", "EMAIL", "PAN"} <= set(labels)


def test_every_record_is_traceable():
    required = ["record_id", "source_id", "source_uri", "source_locator", "version", "kb_version", "content_hash", "category"]
    for r in RECORDS:
        missing = [k for k in required if not r.get(k)]
        assert not missing, f"{r['record_id']} missing {missing}"
        assert r["source_id"] in SOURCES


def test_superseded_records_link_to_replacement():
    by_id = {r["record_id"]: r for r in RECORDS}
    superseded = [r for r in RECORDS if r["status"] == "superseded"]
    assert superseded
    for r in superseded:
        assert r["superseded_by"] in by_id and by_id[r["superseded_by"]]["status"] == "current"


def test_default_search_excludes_superseded_policy():
    res = get_index().search("What is the foreclosure charge?", market="IN")
    hits = res.to_dict()["hits"]
    assert res.status == "OK"
    assert all(h["status"] == "current" for h in hits)
    assert "4%" in hits[0]["content"]


def test_include_superseded_exposes_old_version():
    res = get_index().search("foreclosure charge after 12 EMIs 5%", market="IN", include_superseded=True, top_k=8)
    assert any(h["status"] == "superseded" for h in res.to_dict()["hits"])


@pytest.mark.parametrize("query,market", [("Do you offer home loans?", "IN"), ("car insurance premium", "IN"),
                                          ("berapa harga emas hari ini", "ID")])
def test_out_of_scope_queries_are_refused(query, market):
    res = answer(query, market=market, lang="id" if market == "ID" else "en")
    assert res["status"] == "INSUFFICIENT_EVIDENCE" and not res["citations"]


def test_grounded_answer_has_citations():
    res = answer("Is a GST certificate mandatory?", market="IN")
    assert res["status"] == "OK" and res["citations"]
    assert all(re.match(r"\[kb_[a-z]{2}_\w+\] .+ > .+ \(.+, v[\w.]+, .+#.+\)$", c) for c in res["citations"]), res["citations"]
