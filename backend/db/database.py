"""
backend/db/database.py
------------------------
asyncpg connection pool — connects to the Docker PostgreSQL container.

Connection URL is read from config.settings.database_url which in turn
comes from DATABASE_URL in .env.

All table creation is handled by infra/init.sql which Docker runs
automatically on first container start. This module's create_all_tables()
is a programmatic fallback (useful when connecting to a pre-existing DB).
"""
import logging
from typing import Optional

import asyncpg
from pgvector.asyncpg import register_vector

from config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    Returns (or creates) the shared asyncpg connection pool.
    Connects to the Docker Postgres container via DATABASE_URL in .env.
    """
    global _pool
    if _pool is None:
        logger.info(f"[DB] Connecting: {_sanitise_url(settings.database_url)}")
        try:
            _pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
                # pgvector type codec registration
                # init=_register_vector_codec,
            )

            async with _pool.acquire() as conn:
                await register_vector(conn)


            logger.info("[DB] ✅ Connection pool ready")
        except Exception as e:
            logger.error(f"[DB] ❌ Connection failed: {e}")
            raise
    return _pool


async def _register_vector_codec(conn: asyncpg.Connection):
    """Register pgvector's vector type with asyncpg so we can pass Python lists."""
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.set_type_codec(
        "vector",
        encoder=_encode_vector,
        decoder=_decode_vector,
        schema="pg_catalog",
        format="text",
    )


def _encode_vector(value) -> str:
    """Encode a Python list[float] as Postgres vector literal '[1.0,2.0,...]'"""
    if hasattr(value, "tolist"):   # numpy array
        value = value.tolist()
    return "[" + ",".join(str(float(x)) for x in value) + "]"


def _decode_vector(value: str) -> list:
    """Decode a Postgres vector string back to Python list[float]."""
    return [float(x) for x in value.strip("[]").split(",")]


def _sanitise_url(url: str) -> str:
    """Hide password in log output."""
    try:
        import re
        return re.sub(r":[^@/]+@", ":***@", url)
    except Exception:
        return url


async def close_pool():
    """Gracefully close the pool on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("[DB] Pool closed")


async def db_ping() -> bool:
    """Returns True if the Docker Postgres container is reachable."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"[DB] Ping failed: {e}")
        return False


# ── Programmatic schema creation (fallback) ───────────────────────────────────
# Docker auto-runs infra/init.sql on first start.
# Use this only when connecting to a DB that was NOT started via docker-compose.

_EXTENSIONS_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
"""

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS claims (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text        TEXT NOT NULL,
    text_hash   TEXT UNIQUE NOT NULL,
    embedding   vector(384),
    claim_type  TEXT DEFAULT 'general',
    entities    JSONB DEFAULT '[]',
    intent      TEXT DEFAULT 'assertion',
    language    TEXT DEFAULT 'en',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claims_embedding
    ON claims USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX IF NOT EXISTS idx_claims_hash ON claims (text_hash);

CREATE TABLE IF NOT EXISTS reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID REFERENCES claims(id) ON DELETE SET NULL,
    verdict         TEXT NOT NULL,
    confidence      FLOAT NOT NULL,
    explanation     TEXT NOT NULL DEFAULT '',
    llm_provider    TEXT DEFAULT 'template',
    support_ratio   FLOAT DEFAULT 0.5,
    evidence_count  INT DEFAULT 0,
    sources         JSONB DEFAULT '[]',
    sub_claims      JSONB DEFAULT '[]',
    algorithm_trace JSONB DEFAULT '{}',
    processing_ms   INT DEFAULT 0,
    cached          BOOLEAN DEFAULT FALSE,
    is_compound     BOOLEAN DEFAULT FALSE,
    is_mutation     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_claim   ON reports (claim_id);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports (created_at DESC);

CREATE TABLE IF NOT EXISTS sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id           UUID REFERENCES reports(id) ON DELETE CASCADE,
    domain              TEXT,
    source_name         TEXT,
    url                 TEXT,
    credibility         FLOAT DEFAULT 0.4,
    tier                INT DEFAULT 3,
    stance              TEXT DEFAULT 'NEUTRAL',
    stance_confidence   FLOAT DEFAULT 0.5,
    semantic_similarity FLOAT DEFAULT 0.5,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_credibility_dynamic (
    domain      TEXT PRIMARY KEY,
    score       FLOAT NOT NULL,
    tier        INT GENERATED ALWAYS AS (
                    CASE WHEN score >= 0.85 THEN 1
                         WHEN score >= 0.55 THEN 2
                         WHEN score >= 0.35 THEN 3
                         ELSE 4
                    END) STORED,
    report_count INT DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mutation_chains (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_claim_id   UUID REFERENCES claims(id) ON DELETE CASCADE,
    mutated_claim_id    UUID REFERENCES claims(id) ON DELETE CASCADE,
    similarity          FLOAT NOT NULL,
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (original_claim_id, mutated_claim_id)
);

CREATE TABLE IF NOT EXISTS telemetry_nli (
    id          SERIAL PRIMARY KEY,
    claim_id    UUID REFERENCES claims(id) ON DELETE SET NULL,
    snippet     TEXT,
    stance      TEXT,
    score       FLOAT,
    model       TEXT DEFAULT 'bart-large-mnli',
    source_domain TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""


async def create_all_tables():
    """
    Programmatic fallback schema creation.
    Docker's init.sql already handles this — this is for non-Docker setups.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(_EXTENSIONS_SQL)
        await conn.execute(_TABLES_SQL)
    logger.info("[DB] ✅ Schema verified / created")


async def seed_credibility_data():
    """
    Seed source_credibility_dynamic from the static python dict.
    Runs automatically on startup; ON CONFLICT DO UPDATE makes it idempotent.
    """
    from credibility import DOMAIN_SCORES
    pool = await get_pool()
    async with pool.acquire() as conn:
        for domain, score in DOMAIN_SCORES.items():
            await conn.execute(
                """
                INSERT INTO source_credibility_dynamic (domain, score)
                VALUES ($1, $2)
                ON CONFLICT (domain) DO UPDATE
                    SET score = EXCLUDED.score, updated_at = NOW()
                """,
                domain, float(score),
            )
    logger.info(f"[DB] ✅ Seeded {len(DOMAIN_SCORES)} credibility records")
