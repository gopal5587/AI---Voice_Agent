"""Grounded answer composition. The answer may only use retrieved KB content; otherwise it refuses."""
import re

from .. import llm
from .index import SearchResult, get_index
from .text import terms

NO_ANSWER = {
    "en": "I don't have verified information about that in our approved material, so I won't guess.",
    "tl": "Pasensya na po, wala akong verified na impormasyon tungkol diyan sa aming approved materials, kaya ayokong manghula.",
    "id": "Mohon maaf, informasi tersebut tidak tersedia di materi resmi kami, jadi saya tidak bisa memastikannya.",
}


def _best_sentences(query: str, content: str, limit: int = 2) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if s.strip()]
    q = set(terms(query))
    ranked = sorted(range(len(sentences)), key=lambda i: (-len(q & set(terms(sentences[i]))), i))
    keep = sorted(ranked[:limit])
    return " ".join(sentences[i] for i in keep)


def answer(query: str, market: str = "IN", lang: str = "en", result: SearchResult | None = None, **filters) -> dict:
    result = result or get_index().search(query, market=market, **filters)
    if result.status != "OK":
        return {"status": "INSUFFICIENT_EVIDENCE", "answer": NO_ANSWER.get(lang, NO_ANSWER["en"]),
                "citations": [], "retrieval": result.to_dict(), "generator": "refusal"}

    top = [h for h in result.hits[:3] if h.confidence >= result.hits[0].confidence * 0.8] or result.hits[:1]
    generated = llm.chat([
        {"role": "system", "content": (
            "You answer customer questions on a phone call using ONLY the provided records. Reply in at most 2 short "
            "spoken sentences in the same language and register as the question. If the records do not answer the "
            "question, reply exactly INSUFFICIENT. Never add numbers, promises, or facts not present in the records.")},
        {"role": "user", "content": "Records:\n" + "\n".join(f"[{h.record['record_id']}] {h.record['content']}" for h in top)
                                    + f"\n\nQuestion: {query}"},
    ], max_tokens=120)
    if generated and generated.strip() == "INSUFFICIENT":
        return {"status": "INSUFFICIENT_EVIDENCE", "answer": NO_ANSWER.get(lang, NO_ANSWER["en"]), "citations": [],
                "retrieval": result.to_dict(), "generator": "llm-refusal"}
    text = generated.strip() if generated else _best_sentences(query, top[0].record["content"])
    return {"status": "OK", "answer": text, "citations": [h.citation for h in top[:2]],
            "record_ids": [h.record["record_id"] for h in top[:2]], "retrieval": result.to_dict(),
            "generator": "llm-grounded" if generated else "extractive"}
