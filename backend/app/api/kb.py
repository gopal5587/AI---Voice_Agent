import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import settings
from ..ingestion.pipeline import build
from ..retrieval import index as index_mod
from ..retrieval.answer import answer

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


class AnswerRequest(BaseModel):
    query: str
    market: str = "IN"
    lang: str = "en"


@router.get("/search")
def search(q: str, market: str | None = None, product: str | None = None, category: str | None = None,
           top_k: int = Query(5, le=20), include_superseded: bool = False):
    res = index_mod.get_index().search(q, market=market, product=product, categories=[category] if category else None,
                                       top_k=top_k, include_superseded=include_superseded)
    return res.to_dict()


@router.post("/answer")
def kb_answer(req: AnswerRequest):
    return answer(req.query, market=req.market, lang=req.lang)


@router.get("/records")
def records(market: str | None = None, category: str | None = None, status: str | None = None, limit: int = 200):
    out = [r for r in index_mod.get_index().records
           if (not market or r["market"] == market) and (not category or r["category"] == category) and (not status or r["status"] == status)]
    return {"count": len(out), "records": out[:limit]}


@router.get("/records/{record_id}")
def record(record_id: str):
    rec = index_mod.get_index().by_id.get(record_id)
    if not rec:
        raise HTTPException(404, "record not found")
    return rec


@router.get("/report")
def report():
    path = settings.processed_dir / "ingestion_report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@router.post("/rebuild")
def rebuild():
    summary = build()["summary"]
    index_mod.get_index.cache_clear()
    index_mod.get_index()
    return summary
