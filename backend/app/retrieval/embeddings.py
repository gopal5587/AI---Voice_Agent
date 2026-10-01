"""Embedding providers. `local` needs no network: hashed word + character n-gram vectors, robust to
spelling variants and ASR errors but not cross-lingual. `openai` uses text-embedding-3-small."""
import hashlib
import math
import re
from functools import lru_cache

import httpx
import numpy as np

from ..config import settings
from .text import terms

DIM = 4096


def _bucket(feature: str) -> int:
    return int.from_bytes(hashlib.blake2b(feature.encode(), digest_size=4).digest(), "little") % DIM


class LocalEmbedder:
    name = "local-hash-ngram-4096"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            counts: dict[int, float] = {}
            words = terms(text)
            for w in words:
                counts[_bucket("w:" + w)] = counts.get(_bucket("w:" + w), 0) + 1.0
                padded = f"#{w}#"
                for n in (3, 4):
                    for i in range(len(padded) - n + 1):
                        b = _bucket(f"c{n}:" + padded[i:i + n])
                        counts[b] = counts.get(b, 0) + 0.35
            for a, b in zip(words, words[1:]):
                counts[_bucket(f"b:{a}_{b}")] = counts.get(_bucket(f"b:{a}_{b}"), 0) + 0.7
            for b, c in counts.items():
                out[row, b] = 1 + math.log(c) if c >= 1 else c
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


class OpenAIEmbedder:
    def __init__(self) -> None:
        self.name = settings.openai_embedding_model

    def embed(self, texts: list[str]) -> np.ndarray:
        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": self.name, "input": [re.sub(r"\s+", " ", t) for t in texts]},
            timeout=30,
        )
        resp.raise_for_status()
        vecs = np.array([d["embedding"] for d in resp.json()["data"]], dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


@lru_cache
def get_embedder():
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbedder()
    return LocalEmbedder()
