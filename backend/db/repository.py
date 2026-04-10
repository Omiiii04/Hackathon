"""
backend/db/repository.py
--------------------------
CRUD helpers for every table.
All functions accept an asyncpg.Pool or Connection.
"""
import hashlib
import json
import logging
from typing import List, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


def _md5(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


# ── Claims ────────────────────────────────────────────────────────────────────

async def upsert_claim(
    pool: asyncpg.Pool,
    text: str,
    embedding: list,        # list[float] length 384
    claim_type: str = "general",
    entities: list = None,
    intent: str = "unknown",
) -> str:
    """Insert or get existing claim. Returns claim UUID as string."""
    text_hash = _md5(text)
    async with pool.acquire() as conn:
        # Try to find existing
        existing = await conn.fetchrow(
            "SELECT id FROM claims WHERE text_hash = $1", text_hash
        )
        if existing:
            return str(existing["id"])

        row = await conn.fetchrow(
            """
            INSERT INTO claims (text, text_hash, embedding, claim_type, entities, intent)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            text,
            text_hash,
            embedding,
            claim_type,
            json.dumps(entities or []),
            intent,
        )
        return str(row["id"])


async def find_similar_claims(
    pool: asyncpg.Pool,
    embedding: list,
    threshold: float = 0.75,
    limit: int = 5,
) -> List[dict]:
    """Find claims similar to the given embedding using cosine similarity."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, text, claim_type,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM claims
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) >= $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            embedding,
            threshold,
            limit,
        )
        return [dict(r) for r in rows]


# ── Reports ───────────────────────────────────────────────────────────────────

async def save_report(pool: asyncpg.Pool, claim_id: str, result: dict) -> str:
    """
    Persist a VerdictResult dict as a report.
    Returns the new report UUID.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO reports (
                claim_id, verdict, confidence, explanation, llm_provider,
                support_ratio, evidence_count, sources, sub_claims,
                algorithm_trace, processing_ms, cached, is_compound, is_mutation
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            RETURNING id
            """,
            claim_id,
            result.get("verdict", "UNVERIFIED"),
            float(result.get("confidence", 0.0)),
            result.get("explanation", ""),
            result.get("llm_provider", "template"),
            float(result.get("support_ratio", 0.5)),
            int(result.get("evidence_count", 0)),
            json.dumps(result.get("sources", [])),
            json.dumps(result.get("sub_claims", [])),
            json.dumps(result.get("algorithm_trace", {})),
            int(result.get("processing_ms", 0)),
            bool(result.get("cached", False)),
            bool(result.get("is_compound", False)),
            bool(result.get("is_mutation", False)),
        )
        report_id = str(row["id"])

    # Save normalised source rows
    sources = result.get("sources", [])
    if sources and claim_id:
        async with pool.acquire() as conn:
            for s in sources:
                await conn.execute(
                    """
                    INSERT INTO sources (report_id, domain, source_name, url, credibility, stance)
                    VALUES ($1,$2,$3,$4,$5,$6)
                    """,
                    report_id,
                    s.get("domain", ""),
                    s.get("name", s.get("source", "")),
                    s.get("url", ""),
                    float(s.get("credibility", 0.4)),
                    s.get("stance", "NEUTRAL"),
                )

    return report_id


async def get_recent_reports(pool: asyncpg.Pool, limit: int = 30) -> List[dict]:
    """Return the most recent N verification reports."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.id, r.verdict, r.confidence, r.created_at,
                   c.text as claim_text
            FROM reports r
            LEFT JOIN claims c ON c.id = r.claim_id
            ORDER BY r.created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def get_verdict_distribution(pool: asyncpg.Pool) -> dict:
    """Return count per verdict label for dashboard metrics."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT verdict, COUNT(*) as count FROM reports GROUP BY verdict"
        )
        return {r["verdict"]: int(r["count"]) for r in rows}


# ── Mutation chains ───────────────────────────────────────────────────────────

async def save_mutation(
    pool: asyncpg.Pool,
    original_id: str,
    mutated_id: str,
    similarity: float,
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO mutation_chains (original_claim_id, mutated_claim_id, similarity)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            original_id,
            mutated_id,
            similarity,
        )


async def get_mutation_chain(pool: asyncpg.Pool, claim_id: str) -> List[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mc.similarity, mc.detected_at,
                   c.text as original_text, cm.text as mutated_text
            FROM mutation_chains mc
            JOIN claims c  ON c.id  = mc.original_claim_id
            JOIN claims cm ON cm.id = mc.mutated_claim_id
            WHERE mc.original_claim_id = $1 OR mc.mutated_claim_id = $1
            ORDER BY mc.detected_at DESC
            LIMIT 10
            """,
            claim_id,
        )
        return [dict(r) for r in rows]


# ── NLI Telemetry ─────────────────────────────────────────────────────────────

async def log_nli(
    pool: asyncpg.Pool,
    claim_id: Optional[str],
    snippet: str,
    stance: str,
    score: float,
    model: str = "bart-large-mnli",
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO telemetry_nli (claim_id, snippet, stance, score, model)
            VALUES ($1, $2, $3, $4, $5)
            """,
            claim_id,
            snippet[:500],
            stance,
            score,
            model,
        )


# ── Dynamic credibility ───────────────────────────────────────────────────────

async def get_dynamic_credibility(pool: asyncpg.Pool, domain: str) -> Optional[float]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT score FROM source_credibility_dynamic WHERE domain = $1",
            domain,
        )
        return float(row["score"]) if row else None
