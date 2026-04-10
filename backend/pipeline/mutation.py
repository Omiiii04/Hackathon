"""
backend/pipeline/mutation.py
------------------------------
Mutation detection: compare current claim embedding against the database
to find semantically similar prior claims (rumour evolution tracking).

Threshold: 0.75 cosine similarity (config.MUTATION_SIMILARITY_THRESHOLD)
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class MutationResult:
    is_mutation: bool = False
    similar_claims: List[dict] = field(default_factory=list)
    max_similarity: float = 0.0
    mutation_chain: List[dict] = field(default_factory=list)


async def detect_mutation(
    claim_text: str,
    claim_embedding: list,    # list[float] 384d
    claim_id: str,
    pool,                     # asyncpg.Pool
) -> MutationResult:
    """
    Compare the current claim's embedding against all stored claims.
    If similar claims are found above threshold, record mutation links.

    Returns MutationResult with similar claim metadata.
    """
    from db.repository import find_similar_claims, save_mutation

    threshold = settings.mutation_similarity_threshold

    try:
        similar = await find_similar_claims(
            pool, claim_embedding, threshold=threshold, limit=5
        )
    except Exception as e:
        logger.warning(f"[Mutation] Query failed: {e}")
        return MutationResult()

    # Filter out the claim itself (same text hash might appear)
    similar = [s for s in similar if str(s.get("id")) != claim_id]

    if not similar:
        return MutationResult()

    # Save mutation links to DB
    for s in similar:
        try:
            await save_mutation(
                pool,
                original_claim_id=str(s["id"]),
                mutated_claim_id=claim_id,
                similarity=float(s["similarity"]),
            )
        except Exception as e:
            logger.warning(f"[Mutation] Could not save link: {e}")

    max_sim = max(s["similarity"] for s in similar)
    mutation_chain = [
        {
            "original_text": s.get("text", "")[:120],
            "similarity": round(float(s["similarity"]), 3),
            "claim_type": s.get("claim_type", "general"),
        }
        for s in similar
    ]

    logger.info(
        f"[Mutation] Found {len(similar)} similar claims "
        f"(max_similarity={max_sim:.3f})"
    )

    return MutationResult(
        is_mutation=True,
        similar_claims=similar,
        max_similarity=round(max_sim, 3),
        mutation_chain=mutation_chain,
    )
