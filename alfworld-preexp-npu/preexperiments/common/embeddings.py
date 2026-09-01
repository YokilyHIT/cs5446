"""
Single shared embedding model wrapper (sentence-transformers/all-MiniLM-L6-v2
by default, per spec sections 10.2 and 24). Both experiment A (lesson/goal
similarity, novelty) and experiment B (semantic correctness of world-model
predictions) must use the SAME embedding model instance/config so that
similarity numbers are comparable across the report.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

import numpy as np


@lru_cache(maxsize=1)
def _load_model(model_name: str, device: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device=device)


class Embedder:
    def __init__(self, config: Dict):
        emb_cfg = config["embedding"]
        self.model_name = emb_cfg["model_name"]
        self.device = emb_cfg.get("device", "cpu")
        self._model = _load_model(self.model_name, self.device)

    def encode(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(
            list(texts), convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for two already L2-normalized vectors (dot product);
    falls back to explicit normalization if inputs aren't unit norm."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
