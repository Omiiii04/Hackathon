"""
backend/pipeline/persistence.py
---------------------------------
Shared DB post-verdict helpers.
"""
from __future__ import annotations


async def upsert_and_detect_mutation(claim: str, embedding_list: list, parsed):
    """Persist the claim and detect semantically similar prior claims."""
    from db.database import get_pool
    from db.repository import upsert_claim
    from pipeline.mutation import detect_mutation

    pool = await get_pool()
    claim_id = await upsert_claim(
        pool,
        claim,
        embedding_list,
        parsed.claim_type,
        parsed.entities,
        parsed.intent,
    )
    mutation = await detect_mutation(claim, embedding_list, claim_id, pool)
    return claim_id, mutation
