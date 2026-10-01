import hashlib
import re


def content_hash(text: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def shingles(text: str, n: int = 3) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(max(1, len(words) - n + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


# 3-word shingles: a single changed word in a ~45-word paragraph scores ~0.84; distinct same-topic answers score < 0.75
NEAR_DUP_THRESHOLD = 0.80
