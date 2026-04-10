-- =============================================================================
-- infra/init.sql
-- Auto-executed by Docker on first container start.
-- This file is idempotent — safe to re-run.
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================================
-- Table: claims
-- Stores every parsed claim with its embedding for mutation / similarity search.
-- =============================================================================
CREATE TABLE IF NOT EXISTS claims (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text            TEXT        NOT NULL,
    text_hash       TEXT        UNIQUE NOT NULL,         -- MD5 for fast dedup
    embedding       vector(384),                         -- all-MiniLM-L6-v2 (384-dim)
    claim_type      TEXT        DEFAULT 'general',       -- general | scientific | political | ...
    entities        JSONB       DEFAULT '[]',            -- spaCy NER output
    intent          TEXT        DEFAULT 'assertion',     -- assertion | question | speculation
    language        TEXT        DEFAULT 'en',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Vector similarity index (IVFFlat — fast approximate nearest-neighbour)
-- lists=50 is a good starting point; increase for larger datasets
CREATE INDEX IF NOT EXISTS idx_claims_embedding
    ON claims USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_claims_hash ON claims (text_hash);
CREATE INDEX IF NOT EXISTS idx_claims_type ON claims (claim_type);
CREATE INDEX IF NOT EXISTS idx_claims_created ON claims (created_at DESC);


-- =============================================================================
-- Table: reports
-- One report per verification run (multiple runs on same claim allowed).
-- =============================================================================
CREATE TABLE IF NOT EXISTS reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id            UUID REFERENCES claims(id) ON DELETE SET NULL,
    verdict             TEXT        NOT NULL CHECK (verdict IN ('TRUE','FALSE','MISLEADING','CONFLICTING','UNVERIFIED')),
    confidence          FLOAT       NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    explanation         TEXT        NOT NULL DEFAULT '',
    llm_provider        TEXT        DEFAULT 'template',   -- lm_studio | gemini | template
    support_ratio       FLOAT       DEFAULT 0.5,
    evidence_count      INT         DEFAULT 0,
    sources             JSONB       DEFAULT '[]',          -- serialised top sources
    sub_claims          JSONB       DEFAULT '[]',          -- compound sub-claim results
    algorithm_trace     JSONB       DEFAULT '{}',          -- full trace for debugging
    processing_ms       INT         DEFAULT 0,
    cached              BOOLEAN     DEFAULT FALSE,
    is_compound         BOOLEAN     DEFAULT FALSE,
    is_mutation         BOOLEAN     DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_claim    ON reports (claim_id);
CREATE INDEX IF NOT EXISTS idx_reports_verdict  ON reports (verdict);
CREATE INDEX IF NOT EXISTS idx_reports_created  ON reports (created_at DESC);


-- =============================================================================
-- Table: sources
-- Normalised per-source citation records linked to a report.
-- =============================================================================
CREATE TABLE IF NOT EXISTS sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id       UUID REFERENCES reports(id) ON DELETE CASCADE,
    domain          TEXT,
    source_name     TEXT,
    url             TEXT,
    credibility     FLOAT   DEFAULT 0.4  CHECK (credibility >= 0 AND credibility <= 1),
    tier            INT     DEFAULT 3    CHECK (tier BETWEEN 1 AND 4),
    stance          TEXT    DEFAULT 'NEUTRAL' CHECK (stance IN ('SUPPORTING','CONTRADICTING','NEUTRAL')),
    stance_confidence FLOAT DEFAULT 0.5,
    semantic_similarity FLOAT DEFAULT 0.5,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sources_report  ON sources (report_id);
CREATE INDEX IF NOT EXISTS idx_sources_domain  ON sources (domain);


-- =============================================================================
-- Table: source_credibility_dynamic
-- Static + dynamic credibility scores per domain.
-- Seeded from credibility.py; updated as new data comes in.
-- =============================================================================
CREATE TABLE IF NOT EXISTS source_credibility_dynamic (
    domain          TEXT PRIMARY KEY,
    score           FLOAT NOT NULL CHECK (score >= 0 AND score <= 1),
    tier            INT GENERATED ALWAYS AS (
                        CASE
                            WHEN score >= 0.85 THEN 1
                            WHEN score >= 0.55 THEN 2
                            WHEN score >= 0.35 THEN 3
                            ELSE 4
                        END
                    ) STORED,
    report_count    INT DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);


-- =============================================================================
-- Table: mutation_chains
-- Links claims that are semantically similar (rumour evolution).
-- =============================================================================
CREATE TABLE IF NOT EXISTS mutation_chains (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_claim_id   UUID REFERENCES claims(id) ON DELETE CASCADE,
    mutated_claim_id    UUID REFERENCES claims(id) ON DELETE CASCADE,
    similarity          FLOAT NOT NULL CHECK (similarity >= 0 AND similarity <= 1),
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (original_claim_id, mutated_claim_id)
);

CREATE INDEX IF NOT EXISTS idx_mutation_original ON mutation_chains (original_claim_id);
CREATE INDEX IF NOT EXISTS idx_mutation_mutated  ON mutation_chains (mutated_claim_id);


-- =============================================================================
-- Table: telemetry_nli
-- Per-snippet stance classification logs for model analysis.
-- =============================================================================
CREATE TABLE IF NOT EXISTS telemetry_nli (
    id              SERIAL PRIMARY KEY,
    claim_id        UUID REFERENCES claims(id) ON DELETE SET NULL,
    snippet         TEXT,
    stance          TEXT,
    score           FLOAT,
    model           TEXT DEFAULT 'bart-large-mnli',
    source_domain   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nli_claim   ON telemetry_nli (claim_id);
CREATE INDEX IF NOT EXISTS idx_nli_stance  ON telemetry_nli (stance);


-- =============================================================================
-- Seed: source_credibility_dynamic
-- Tier 1 and Tier 2 domains pre-loaded for instant credibility lookups.
-- =============================================================================
INSERT INTO source_credibility_dynamic (domain, score) VALUES
    -- Tier 1 — Wire services + authoritative bodies
    ('reuters.com',           0.97),
    ('apnews.com',            0.97),
    ('afp.com',               0.94),
    ('bbc.com',               0.95),
    ('bbc.co.uk',             0.95),
    ('who.int',               0.96),
    ('un.org',                0.96),
    ('cdc.gov',               0.96),
    ('nih.gov',               0.96),
    ('nasa.gov',              0.96),
    -- Tier 1 — Major newspapers
    ('nytimes.com',           0.92),
    ('theguardian.com',       0.91),
    ('washingtonpost.com',    0.90),
    ('economist.com',         0.90),
    ('ft.com',                0.90),
    -- Tier 1 — Fact-checkers
    ('snopes.com',            0.93),
    ('politifact.com',        0.93),
    ('factcheck.org',         0.93),
    ('fullfact.org',          0.92),
    -- Tier 1 — Science journals
    ('nature.com',            0.95),
    ('science.org',           0.95),
    ('thelancet.com',         0.94),
    -- Tier 2 — Regional / national media
    ('ndtv.com',              0.80),
    ('aljazeera.com',         0.80),
    ('bloomberg.com',         0.85),
    ('thehindu.com',          0.82),
    ('timesofindia.com',      0.72),
    ('dw.com',                0.85),
    ('france24.com',          0.82),
    ('channelnewsasia.com',   0.80),
    ('bbc.com/news',          0.95),
    -- Tier 2 — Reference
    ('wikipedia.org',         0.65),
    ('britannica.com',        0.80),
    -- Tier 3–4 — Low/social
    ('medium.com',            0.40),
    ('reddit.com',            0.30),
    ('twitter.com',           0.25),
    ('x.com',                 0.25),
    ('facebook.com',          0.22),
    ('tiktok.com',            0.20)
ON CONFLICT (domain) DO UPDATE
    SET score = EXCLUDED.score, updated_at = NOW();
