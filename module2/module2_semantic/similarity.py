"""Similarity utilities for semantic skill matching."""

from __future__ import annotations

import numpy as np


def compute_similarity(vec1, vec2) -> float:
    """Compute cosine similarity between two vectors."""
    if vec1 is None or vec2 is None:
        return 0.0

    a = np.asarray(vec1, dtype=np.float32)
    b = np.asarray(vec2, dtype=np.float32)
    if a.size == 0 or b.size == 0:
        return 0.0

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compute_similarity_matrix(left_matrix, right_matrix) -> np.ndarray:
    """Compute cosine similarity for two 2D matrices."""
    left = np.asarray(left_matrix, dtype=np.float32)
    right = np.asarray(right_matrix, dtype=np.float32)
    if left.size == 0 or right.size == 0:
        return np.zeros((0, 0), dtype=np.float32)

    left_norms = np.linalg.norm(left, axis=1, keepdims=True)
    right_norms = np.linalg.norm(right, axis=1, keepdims=True).T
    denom = left_norms * right_norms
    denom[denom == 0.0] = 1e-12
    return (left @ right.T) / denom
