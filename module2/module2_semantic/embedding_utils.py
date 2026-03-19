"""Embedding utilities with singleton sentence-transformer loading."""

from __future__ import annotations

import os
from threading import Lock
from typing import Iterable, List

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore[assignment]


MODEL_NAME = "all-MiniLM-L6-v2"
_MODEL: "SentenceTransformer | None" = None
_MODEL_LOCK = Lock()
_MODEL_DEVICE = ""


def get_model_device() -> str:
    return _MODEL_DEVICE or "cpu"


def _select_device() -> str:
    forced_device = os.getenv("MODULE2_SEMANTIC_DEVICE", "").strip().lower()
    if forced_device:
        return forced_device

    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _get_model() -> "SentenceTransformer":
    """Load the embedding model once per process."""
    if SentenceTransformer is None:
        raise RuntimeError(
            "sentence-transformers is not installed. Install with: pip install sentence-transformers"
        )

    global _MODEL
    global _MODEL_DEVICE
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                _MODEL_DEVICE = _select_device()
                _MODEL = SentenceTransformer(MODEL_NAME, device=_MODEL_DEVICE)
    return _MODEL


def _encode_batch(texts: List[str]) -> np.ndarray:
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=min(32, max(1, len(texts))),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(embeddings, dtype=np.float32)


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string as a normalized numpy vector."""
    if not text or not text.strip():
        return np.array([], dtype=np.float32)
    return _encode_batch([text.strip()])[0]


def embed_sentences(sentences: Iterable[str]) -> List[np.ndarray]:
    """Embed multiple text units in one batch call."""
    cleaned_sentences = [sentence.strip() for sentence in sentences if sentence and sentence.strip()]
    if not cleaned_sentences:
        return []
    return [embedding for embedding in _encode_batch(cleaned_sentences)]
