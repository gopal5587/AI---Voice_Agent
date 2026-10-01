"""Hybrid retrieval over versioned KB records: BM25 + dense cosine, fused with reciprocal-rank fusion."""
import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..config import settings
from ..ingestion.normalize import expand_query
from .embeddings import get_embedder
from .qdrant_store import QdrantStore
from .text import terms

log = logging.getLogger("kb")
RRF_K = 60
OBJECTION_HINT = re.compile(r"too (high|expensive|costly)|not interested|don't (want|trust)|worried|think about|scam|mahal|"
                            r"pag-iisipan|kemahalan|keberatan|belum gajian|kok (gede|besar)|hidden", re.I)


@dataclass
class Hit:
    record: dict
    score: float
    confidence: float
    bm25: float
    dense: float
    coverage: float

    @property
    def citation(self) -> str:
        r = self.record
        return f"[{r['record_id']}] {r['doc_title']} > {r['title']} ({r['source_type']}, v{r['version']}, {r['source_locator']})"

    def to_dict(self) -> dict:
        r = self.record
        return {
            "record_id": r["record_id"], "title": r["title"], "content": r["content"], "category": r["category"],
            "product": r["product"], "market": r["market"], "source_uri": r["source_uri"],
            "source_locator": r["source_locator"], "version": r["version"], "status": r["status"],
            "score": round(self.score, 4), "confidence": round(self.confidence, 3), "bm25": round(self.bm25, 3),
            "dense": round(self.dense, 3), "term_coverage": round(self.coverage, 3), "citation": self.citation,
        }


@dataclass
class SearchResult:
    query: str
    status: str
    hits: list[Hit]
    latency_ms: float
    filters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"query": self.query, "status": self.status, "latency_ms": round(self.latency_ms, 2),
                "filters": self.filters, "hits": [h.to_dict() for h in self.hits]}


class KBIndex:
    def __init__(self, records: list[dict]) -> None:
        self.records = records
        self.by_id = {r["record_id"]: r for r in records}
        self.embedder = get_embedder()
        docs = [self._doc_text(r) for r in records]
        self.doc_terms = [terms(d) for d in docs]
        self.doc_tf = [Counter(t) for t in self.doc_terms]
        self.avgdl = sum(map(len, self.doc_terms)) / max(1, len(self.doc_terms))
        df = Counter(t for ts in self.doc_terms for t in set(ts))
        n = len(records)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.max_idf = max(self.idf.values(), default=1.0)
        self.doc_term_sets = [set(t) for t in self.doc_terms]
        self.vectors = self.embedder.embed(docs) if records else np.zeros((0, 1))
        self.qdrant = QdrantStore.maybe_connect(records, self.vectors, self.embedder.name)

    @staticmethod
    def _doc_text(r: dict) -> str:
        return f"{r['title']}. {r['title']}. {r['content']} {' '.join(r.get('terms', []))}"

    def _bm25(self, q_terms: list[str], i: int, k1: float = 1.4, b: float = 0.75) -> float:
        tf, dl = self.doc_tf[i], len(self.doc_terms[i])
        return sum(self.idf.get(t, 0) * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / self.avgdl)) for t in set(q_terms) if t in tf)

    def search(self, query: str, market: str | None = None, product: str | None = None,
               categories: list[str] | None = None, top_k: int = 5, include_superseded: bool = False,
               min_confidence: float | None = None) -> SearchResult:
        t0 = time.perf_counter()
        threshold = settings.retrieval_min_score if min_confidence is None else min_confidence
        filters = {"market": market, "product": product, "categories": categories, "include_superseded": include_superseded}
        candidates = [i for i, r in enumerate(self.records)
                      if (include_superseded or r["status"] == "current")
                      and (not market or r["market"] == market)
                      and (not product or r["product"] == product)
                      and (not categories or r["category"] in categories)]
        expanded = expand_query(query)
        q_terms = terms(expanded)
        if not candidates or not q_terms:
            return SearchResult(query, "INSUFFICIENT_EVIDENCE", [], (time.perf_counter() - t0) * 1000, filters)

        qvec = self.embedder.embed([expanded])[0]
        if self.qdrant:
            by_id = self.qdrant.scores(qvec, [self.records[i]["record_id"] for i in candidates])
            dense = {i: by_id.get(self.records[i]["record_id"], 0.0) for i in candidates}
        else:
            dense = {i: float(self.vectors[i] @ qvec) for i in candidates}
        bm25 = {i: self._bm25(q_terms, i) for i in candidates}
        bm_rank = {i: r for r, i in enumerate(sorted(candidates, key=lambda i: -bm25[i]))}
        de_rank = {i: r for r, i in enumerate(sorted(candidates, key=lambda i: -dense[i]))}

        # coverage is IDF-weighted and terms unseen in the corpus get maximum weight, so a query whose
        # distinctive words are absent (e.g. "home loan", "gold rate") cannot pass on generic overlap
        weights = {t: self.idf.get(t, 2.0 * self.max_idf) for t in set(q_terms)}
        total_weight = sum(weights.values())
        objection = bool(OBJECTION_HINT.search(query))
        hits = []
        for i in candidates:
            rec = self.records[i]
            fused = (1 / (RRF_K + bm_rank[i]) + 1 / (RRF_K + de_rank[i])) * RRF_K / 2  # 1.0 when ranked first by both
            doc_set = self.doc_term_sets[i]
            coverage = sum(w for t, w in weights.items() if t in doc_set) / total_weight
            bm_norm = bm25[i] / (bm25[i] + 4.0)
            confidence = 0.35 * dense[i] + 0.25 * bm_norm + 0.40 * coverage
            score = 0.5 * fused + 0.5 * confidence
            if objection and rec["category"] == "objection_handling":
                score *= 1.1
            hits.append(Hit(rec, score, confidence, bm25[i], dense[i], coverage))
        hits.sort(key=lambda h: (-h.score, -h.confidence))
        hits = hits[:top_k]
        status = "OK" if hits and max(h.confidence for h in hits[:3]) >= threshold else "INSUFFICIENT_EVIDENCE"
        latency = (time.perf_counter() - t0) * 1000
        log.info("kb.search q_len=%d status=%s ids=%s latency_ms=%.1f", len(query), status,
                 [h.record["record_id"] for h in hits[:3]], latency)
        return SearchResult(query, status, hits, latency, filters)

    def rules(self, product: str) -> list[dict]:
        return [r["structured"] for r in self.records
                if r["category"] == "eligibility_rule" and r["product"] == product and r["status"] == "current" and r.get("structured")]


def load_records(path: Path | None = None) -> list[dict]:
    path = path or settings.processed_dir / "kb_records.jsonl"
    if not path.exists():
        from ..ingestion.pipeline import build
        build()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@lru_cache
def get_index() -> KBIndex:
    return KBIndex(load_records())
