"""
backend/pipeline/embedder.py
------------------------------
SentenceTransformer embedding wrapper.
Model: all-MiniLM-L6-v2  (384-dim, fast CPU-friendly)

Responsibilities:
  - embed(text) → numpy array (384d)
  - similarity(a, b) → cosine similarity float
  - rank_evidence(claim_emb, evidence_list) → sorted by semantic relevance
"""
import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy singleton model ──────────────────────────────────────────────────────
_model = None
MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    global _model
    if _model is None:
        logger.info(f"[Embedder] Loading {MODEL_NAME}…")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
        logger.info(f"[Embedder] {MODEL_NAME} loaded ✅")
    return _model


# ── Core functions ────────────────────────────────────────────────────────────

def embed(text: str) -> np.ndarray:
    """Encode a single string → 384-dimensional float32 array."""
    model = _get_model()
    return model.encode(text, convert_to_numpy=True, normalize_embeddings=True)


def embed_batch(texts: List[str]) -> np.ndarray:
    """Encode multiple strings in one efficient batch call."""
    model = _get_model()
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two normalised embedding vectors.
    Since embeddings are L2-normalised, dot product == cosine similarity.
    """
    return float(np.dot(a, b))


def similarity(text_a: str, text_b: str) -> float:
    """Convenience: embed two strings and return their cosine similarity."""
    emb_a = embed(text_a)
    emb_b = embed(text_b)
    return cosine_similarity(emb_a, emb_b)


def rank_evidence(claim_embedding: np.ndarray, evidence_list: list) -> list:
    """
    Sort evidence items by semantic similarity to the claim.
    Each item must have a 'snippet' and optionally 'title' field.

    Returns the same list, sorted descending by similarity (most relevant first).
    """
    if not evidence_list:
        return evidence_list

    # Batch-encode all snippets
    snippets = [
        f"{e.title}. {e.snippet}" if hasattr(e, "title") else str(e)
        for e in evidence_list
    ]
    snippet_embs = embed_batch(snippets)

    # Compute similarities
    scores = [cosine_similarity(claim_embedding, emb) for emb in snippet_embs]

    # Attach semantic similarity score to each evidence item
    for ev, score in zip(evidence_list, scores):
        ev.semantic_similarity = round(float(score), 4)

    # Sort by semantic similarity descending
    return sorted(evidence_list, key=lambda e: getattr(e, "semantic_similarity", 0), reverse=True)


def embedding_to_list(emb: np.ndarray) -> List[float]:
    """Convert numpy array to Python list for JSON/DB serialisation."""
    return emb.tolist()
