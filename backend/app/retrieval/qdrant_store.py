"""Optional Qdrant backend (enabled when QDRANT_URL is set). The in-process numpy index is the default;
Qdrant is the production path when the KB grows beyond what fits comfortably in memory."""
import logging
import uuid

import httpx
import numpy as np

from ..config import settings

log = logging.getLogger("kb")


class QdrantStore:
    def __init__(self, url: str, collection: str) -> None:
        self.url, self.collection = url.rstrip("/"), collection

    @classmethod
    def maybe_connect(cls, records: list[dict], vectors: np.ndarray, embedder_name: str) -> "QdrantStore | None":
        if not settings.qdrant_url or not records:
            return None
        kb_version = records[0].get("kb_version", "dev")
        store = cls(settings.qdrant_url, f"kb_{kb_version}_{embedder_name}".replace("-", "_").replace(".", "_"))
        try:
            store._ensure(records, vectors)
            return store
        except httpx.HTTPError as exc:
            log.warning("Qdrant unavailable (%s); falling back to in-memory index", exc)
            return None

    def _ensure(self, records: list[dict], vectors: np.ndarray) -> None:
        if httpx.get(f"{self.url}/collections/{self.collection}", timeout=5).status_code == 200:
            return
        httpx.put(f"{self.url}/collections/{self.collection}", timeout=10,
                  json={"vectors": {"size": int(vectors.shape[1]), "distance": "Cosine"}}).raise_for_status()
        points = [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, r["record_id"])), "vector": vectors[i].tolist(),
                   "payload": {k: r[k] for k in ("record_id", "market", "product", "category", "status", "version")}}
                  for i, r in enumerate(records)]
        httpx.put(f"{self.url}/collections/{self.collection}/points?wait=true", json={"points": points}, timeout=60).raise_for_status()

    def scores(self, qvec: np.ndarray, record_ids: list[str]) -> dict[str, float]:
        resp = httpx.post(f"{self.url}/collections/{self.collection}/points/search", timeout=5, json={
            "vector": qvec.tolist(), "limit": len(record_ids), "with_payload": True,
            "filter": {"must": [{"key": "record_id", "match": {"any": record_ids}}]},
        })
        resp.raise_for_status()
        return {p["payload"]["record_id"]: float(p["score"]) for p in resp.json()["result"]}
