"""Embeddings for chunks and queries.

With ``SNAP_LLM_API_KEY`` set, chunks are embedded through any OpenAI-compatible
``/embeddings`` endpoint. Without a key -- and whenever the provider fails -- the
pipeline falls back to a deterministic local hashing embedding so an offline run
still retrieves lexically and a network blip never blocks an upload.
"""

import hashlib
import logging
import math
import re
from collections import Counter

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z0-9][a-z0-9._%+-]*")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "its", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "was", "we", "were", "with", "you", "your", "i", "my", "me",
}


def tokenize(text: str) -> list[str]:
    return [word for word in _WORD.findall(text.lower()) if word not in _STOP]


def _bucket(feature: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    index = int.from_bytes(digest[:4], "little") % dimensions
    sign = 1.0 if digest[4] & 1 else -1.0
    return index, sign


def _local_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    words = tokenize(text)
    counts = Counter(words)
    for word, count in counts.items():
        weight = 1.0 + math.log(count)
        index, sign = _bucket(f"w:{word}", dimensions)
        vector[index] += sign * weight
        if len(word) >= 4:
            for offset in range(len(word) - 2):
                trigram = word[offset : offset + 3]
                index, sign = _bucket(f"3:{trigram}", dimensions)
                vector[index] += sign * 0.35
    for left, right in zip(words, words[1:], strict=False):
        index, sign = _bucket(f"b:{left}_{right}", dimensions)
        vector[index] += sign * 0.5

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]


def _remote_embeddings(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    dimensions = settings.embedding_dimensions
    vectors: list[list[float]] = []
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
    with httpx.Client(timeout=settings.llm_timeout_seconds * 2) as client:
        for start in range(0, len(texts), 32):
            batch = texts[start : start + 32]
            payload: dict[str, object] = {
                "model": settings.embedding_model,
                "input": batch,
            }
            if dimensions:
                payload["dimensions"] = dimensions
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 400 and "dimensions" in payload:
                payload.pop("dimensions", None)
                response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json().get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise ValueError("embedding provider returned an unexpected payload")
            ordered = sorted(data, key=lambda item: item.get("index", 0))
            for item in ordered:
                vector = item.get("embedding")
                if not isinstance(vector, list) or len(vector) != dimensions:
                    raise ValueError("embedding dimension mismatch")
                vectors.append([float(value) for value in vector])
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed each text, degrading to local hashing on any provider error."""
    if not texts:
        return []
    settings = get_settings()
    dimensions = settings.embedding_dimensions
    if settings.llm_api_key:
        try:
            return _remote_embeddings(texts)
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning("embeddings provider failed; using local hashing: %s", exc)
    return [_local_embedding(text, dimensions) for text in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    width = min(len(left), len(right))
    if width == 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(width))
    left_norm = math.sqrt(sum(value * value for value in left[:width]))
    right_norm = math.sqrt(sum(value * value for value in right[:width]))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
