# Software Design Document (SDD)

## OSINT Rumor Verification Platform

---

| Field          | Details                           |
| -------------- | --------------------------------- |
| Document Title | Software Design Document          |
| Project Name   | OSINT Rumor Verification Platform |
| Team           | Radio Frequency                   |
| Event          | VIT Code Apex 2.0 — PS ID 1.5    |
| Version        | 5.2.0                             |
| Status         | Final — All Reviews Incorporated |
| Date           | April 2026                        |

---

## Revision History

| Version | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Date       |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| 1.0.0   | Initial draft                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | March 2026 |
| 2.0.0   | Deterministic verdict; LLM explanation-only; Early Exit; algorithm improvements                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | March 2026 |
| 3.0.0   | CONFLICTING verdict; bounded sigmoid; hnsw index; temperature=0.0; circuit breakers; GPU memory management; telemetry                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | March 2026 |
| 4.0.0   | asyncio.run() wrapper for Celery tasks; UX cache buffering design; utterance-date vs event-date disambiguation; sub-claim breakdown UI                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | March 2026 |
| 5.0.0   | **Explainability UI 2.0** (EvidenceGraph, SupportBar, SourceTimeline components); **Dynamic credibility** (DynamicCredibilityScorer); **Rumor Evolution Tracking** (RumorEvolutionTracker + mutation_chains table); **BART-MNLI batching** (up to 25 sentences per call); **Embedding cache** (Redis TTL 12h); **Context-aware VerdictEngine** (claim type detection + threshold tables); **User profiles** (UserProfileManager); **Ollama as primary LLM** (cloud as fallback); **Standalone verdict pipeline** (verdict_pipeline/ module, no FastAPI/Celery); Adversarial signal detection; ARQ migration path       | April 2026 |
| 5.1.0   | **Killer Screen layout** (Section 23 — KillerScreen.jsx, single-view impact design); **VerdictReasonTagEngine** (deterministic tag selection, no LLM); **Mutation Alert as headline** (inline MutationAlert component, not buried in tabs); **CredibilityShiftBadge** (delta arrow on source cards); popup.js killer layout update                                                                                                                                                                                                                                                                                                                  | April 2026 |
| 5.2.0   | **LLM latency fix** (Section 24 — Qwen 2.5 3B/Llama 3.2 3B, max_tokens=120, TTFT streaming, 5s TTFT fallback trigger); **Syndication echo-chamber fix** (Section 24 — pairwise MiniLM similarity >0.90 triggers penalty); **Sybil protection** (Section 24 — IP rate-limit + trust weight + FREEZE_CREDIBILITY flag); **Gather timeout** (Section 24 — asyncio.wait_for 15s + per-request httpx 5s); **UNVERIFIED null-state UI** (Section 24 — empty-state bar + "Awaiting credible coverage"); **LMStudioProvider** (Section 5 — drop-in OpenAI-compatible); **WSL 2 deployment path** (Section 19 — replaces VirtualBox) | April 2026 |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Architecture](#2-system-architecture)
3. [Module Design](#3-module-design)
4. [Verdict Engine — Full Algorithm Design](#4-verdict-engine--full-algorithm-design)
5. [LLM Integration Design](#5-llm-integration-design)
6. [Database Design](#6-database-design)
7. [API Design](#7-api-design)
8. [Chrome Extension Design](#8-chrome-extension-design)
9. [Source Credibility System](#9-source-credibility-system)
10. [Caching Strategy &amp; UX Buffering](#10-caching-strategy--ux-buffering)
11. [Performance &amp; GPU Memory Management](#11-performance--gpu-memory-management)
12. [Circuit Breaker Design](#12-circuit-breaker-design)
13. [Explainability UI 2.0](#13-explainability-ui-20)
14. [Rumor Evolution Tracker](#14-rumor-evolution-tracker)
15. [User Personalization](#15-user-personalization)
16. [Adversarial Robustness](#16-adversarial-robustness)
17. [Standalone Verdict Pipeline](#17-standalone-verdict-pipeline)
18. [Security Design](#18-security-design)
19. [Deployment Design](#19-deployment-design)
20. [Project Structure](#20-project-structure)
21. [Technology Stack](#21-technology-stack)
22. [Error Handling &amp; Telemetry](#22-error-handling--telemetry)

---

## 1. Introduction

### 1.1 Purpose

This SDD describes internal architecture, component design, data flow, and implementation details for the OSINT Rumor Verification Platform v5.2. It translates SRS v5.2.0 into concrete technical decisions.

### 1.2 Key Design Decisions (v5.2 Updates)

| Decision                 | Choice                                             | Reason                                                |
| ------------------------ | -------------------------------------------------- | ----------------------------------------------------- |
| LLM primary              | LM Studio (local OpenAI-compatible server)         | Local-first; no key management; offline-capable       |
| LLM fallback chain       | Gemini → Grok → rule-based                       | Cloud only on LM Studio failure                       |
| BART-MNLI batching       | All sentences in one call (max 25)                 | ~50% latency reduction vs per-sentence loop           |
| Embedding cache          | Redis key = url_md5, TTL 12h                       | Eliminates re-encoding for repeat articles            |
| Context-aware thresholds | Lookup table keyed by claim_type                   | Breaking news needs less evidence certainty           |
| Dynamic credibility      | feedback_adj + consistency, async update           | Learning system without blocking critical path        |
| Rumor tracking           | mutation_chains table + pgvector similarity > 0.75 | Weaponizes existing pgvector index                    |
| Evidence graph           | JSON nodes+edges in API response                   | Dashboard renders as SVG, extension shows support bar |
| User profile             | localStorage + DB — 3 tiers                       | Same backend, different UI depth                      |
| Standalone pipeline      | verdict_pipeline/ — zero heavy deps               | Researcher/batch use without full stack               |
| Adversarial detection    | Tier-4/5 spam signal + pgvector variant check      | Robustness without breaking main path                 |
| Celery + async           | asyncio.run() at task boundary                     | Unchanged — still correct for hackathon              |
| Post-hackathon           | Replace Celery with ARQ                            | Native async, cleaner architecture                    |
| Cache UX                 | 1.5–2.0s simulated WebSocket progress             | Unchanged — instant cache hit still distrust         |
| Verdict determination    | Deterministic algorithm                            | Auditable, no hallucination                           |
| LLM role                 | Explanation only, temperature=0.0                  | Anchored output, no creative drift                    |

---

## 2. System Architecture

### 2.1 High-Level Architecture (v5.2)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│   Chrome Extension  │  Web Dashboard  │  REST Client / CLI          │
│   (SupportBar, SubClaimUI, UserProfile)  (EvidenceGraph, Timeline)  │
└──────────┬──────────┴────────┬─────────┴──────────┬─────────────────┘
           │ HTTPS + WS        │                    │
           ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY — FastAPI                            │
│  POST /verify   GET /status/:id   GET /report/:id                  │
│  POST /feedback   GET /history   WS /ws/:id   GET /metrics         │
│  GET /mutation/:id   GET /credibility/:domain                      │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ Enqueue Celery job
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│               CELERY TASK QUEUE (Redis broker)                      │
│  def verify_claim_task(claim_text, job_id):                         │
│      result = asyncio.run(run_pipeline(claim_text))  ← event loop  │
└──────┬──────────────────────────────────────────────────────────────┘
       │ asyncio.run() creates event loop
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       ASYNC PIPELINE                                 │
│  1.  Language detect → Translate to English                          │
│  2.  Claim Parser (spaCy sm, CPU) + claim type detection             │
│      └── Extract EVENT date (not utterance date)                    │
│      └── Detect: breaking_news / scientific / political / general    │
│  3.  asyncio.gather() — all sources in parallel                      │
│      └── Every source wrapped in circuit breaker                    │
│  4.  Early Exit check per batch                                      │
│  5.  Evidence Extractor                                              │
│      ├── MiniLM CPU → embedding cache check → encode if miss         │
│      └── BART GPU → BATCHED (≤25 sentences per call)                │
│  6.  Context-Aware Verdict Engine (5 verdicts + claim_type thresholds)│
│  7.  Explainability Builder (support_bar, evidence_graph)           │
│  8.  LM Studio Explainer (primary) → Gemini → Grok → rule-based     │
│  9.  Rumor Evolution Tracker (mutation chain linkage)               │
│  10. Adversarial Signal Detector                                     │
│  11. Translate explanation back (if non-English)                    │
│  12. Report Generator + telemetry log                               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
   PostgreSQL + pgvector       Redis
   (hnsw + mutation_chains)    (cache + CB state + UX buffer + emb cache)
```

### 2.2 Standalone Verdict Pipeline (Independent)

```
verdict_pipeline/           ← no FastAPI, Celery, or Redis
    ├── engine.py           ← VerdictEngine (same algorithm)
    ├── extractor.py        ← EvidenceExtractor (same BART/MiniLM)
    ├── storage.py          ← SQLite adapter
    ├── cli.py              ← python -m verdict_pipeline verify "..."
    └── batch.py            ← process list[str] → list[VerdictResult]
```

### 2.3 Celery + asyncio Boundary (Unchanged)

```
Celery worker (sync)
  └── asyncio.run(pipeline())    ← creates new event loop
        └── await asyncio.gather(
                search_scraper.search_all(),
                news_scraper.fetch_all(),
                factcheck_scraper.check_all(),
            )
```

**Post-hackathon path:** Replace Celery with ARQ — natively async, no asyncio.run() needed.

---

## 3. Module Design

### 3.1 Claim Parser — Event Date + Claim Type (`analysis/claim_parser.py`)

```python
import spacy
import dateparser
from datetime import datetime, date
from dataclasses import dataclass
from typing import Optional

nlp = spacy.load("en_core_web_sm")  # CPU only

BREAKING_NEWS_SIGNALS = [
    "just", "breaking", "now", "alert", "latest", "happened",
    "minutes ago", "hours ago"
]
SCIENTIFIC_SIGNALS = [
    "study", "research", "scientists", "vaccine", "virus", "clinical",
    "journal", "published", "found", "proven", "data shows"
]

@dataclass
class TemporalContext:
    event_date:     Optional[date]
    utterance_date: date
    explicit:       bool

@dataclass
class ParsedClaim:
    raw_text:          str
    normalized_text:   str
    temporal_context:  TemporalContext
    claim_type:        str    # "breaking_news" | "scientific" | "political" | "general"
    is_compound:       bool
    sub_claims:        list[str]

def detect_claim_type(text: str, entities: list) -> str:
    text_lower = text.lower()
    if any(s in text_lower for s in BREAKING_NEWS_SIGNALS):
        return "breaking_news"
    if any(s in text_lower for s in SCIENTIFIC_SIGNALS):
        return "scientific"
    orgs = [e.text for e in entities if e.label_ in ("ORG", "GPE", "NORP")]
    if orgs:
        return "political"
    return "general"

def extract_temporal_context(text: str) -> TemporalContext:
    utterance_date = datetime.now().date()
    doc = nlp(text)
    date_entities = [ent.text for ent in doc.ents if ent.label_ == "DATE"]

    parsed_dates = []
    for d in date_entities:
        parsed = dateparser.parse(d, settings={
            "PREFER_DAY_OF_MONTH": "first",
            "PREFER_DATES_FROM":   "past",
            "RELATIVE_BASE":       datetime.now(),
        })
        if parsed:
            parsed_dates.append(parsed.date())

    if parsed_dates:
        historical = [d for d in parsed_dates if d <= utterance_date]
        if historical:
            return TemporalContext(
                event_date=min(historical), utterance_date=utterance_date, explicit=True
            )

    relative_keywords = ["yesterday", "today", "last week", "this week",
                         "last month", "recently", "just now"]
    for kw in relative_keywords:
        if kw in text.lower():
            parsed = dateparser.parse(kw)
            if parsed:
                return TemporalContext(
                    event_date=parsed.date(), utterance_date=utterance_date, explicit=False
                )

    return TemporalContext(
        event_date=utterance_date, utterance_date=utterance_date, explicit=False
    )
```

---

### 3.2 Evidence Extractor — Batched BART + Embedding Cache (`analysis/evidence_extractor.py`)

```python
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import torch
import hashlib
import json
import redis.asyncio as aioredis

embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
stance_classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli",
    device=0    # GPU — ~1.6GB VRAM
)

redis_client = aioredis.from_url(settings.redis_url)

# ── Embedding Cache ──────────────────────────────────────────────────
async def get_cached_embeddings(sentences: list[str],
                                 article_url: str) -> dict:
    """
    Cache embeddings by (article_url, sentence_index).
    Avoids re-encoding sentences from the same article on repeat requests.
    TTL 12h matches article cache TTL.
    """
    cache_key = f"emb:{hashlib.md5(article_url.encode()).hexdigest()}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)   # dict: sentence_text → embedding list

    # Cache miss — encode all sentences in one call (not per-sentence)
    embs = embedder.encode(sentences, batch_size=64)
    payload = {s: embs[i].tolist() for i, s in enumerate(sentences)}
    await redis_client.setex(cache_key, 43200, json.dumps(payload))  # 12h
    return payload

# ── BART-MNLI Batching ───────────────────────────────────────────────
def classify_stance_batch(sentences: list[str],
                           claim_text: str) -> list[str]:
    """
    Single GPU call for up to 25 sentences.
    BEFORE (v4): loop → 25 separate GPU calls
    AFTER  (v5): one batched call → ~50% latency reduction
    """
    if not sentences:
        return []

    results = stance_classifier(
        sentences,                          # ← pass list, not single string
        candidate_labels=["supports the claim",
                          "contradicts the claim",
                          "unrelated"],
        hypothesis_template="This text {} that: " + claim_text,
        multi_label=False,
        batch_size=25
    )

    label_map = {
        "supports the claim":    "SUPPORTING",
        "contradicts the claim": "CONTRADICTING",
        "unrelated":             "NEUTRAL",
    }

    # results is a list when input is a list
    return [label_map[r["labels"][0]] for r in results]

class EvidenceExtractor:
    async def extract(self, articles, claim):
        sentences = []
        sentence_to_article = {}

        for article in articles:
            sents = sent_tokenize(article.text)
            for s in sents:
                sentences.append(s)
                sentence_to_article[s] = article

        # ── Step 1: Embeddings (cached per article URL) ──────────────
        # Group by article to hit per-URL cache
        all_embs = {}
        for article in articles:
            sents = sent_tokenize(article.text)
            emb_map = await get_cached_embeddings(sents, article.url)
            all_embs.update(emb_map)

        import numpy as np
        claim_emb  = embedder.encode(claim.normalized_text)
        sent_embs  = np.array([all_embs[s] for s in sentences])
        scores     = cosine_similarity([claim_emb], sent_embs)[0]
        top_25     = top_k_per_article(sentences, scores, articles, k=5)

        # ── Step 2: BART-MNLI — ONE batched call ─────────────────────
        top_sentences  = [s for s, _ in top_25]
        stances        = classify_stance_batch(top_sentences, claim.normalized_text)

        evidence = []
        for (sentence, article), stance in zip(top_25, stances):
            evidence.append(Evidence(
                sentence     = sentence,
                stance       = stance,
                credibility  = get_dynamic_credibility(article.domain),
                relevance    = float(scores[sentences.index(sentence)]),
                recency      = recency_factor(article.published_at),
                url          = article.url,
                source_name  = article.source_name,
                published_at = article.published_at,
            ))
        return evidence

    def detect_syndicated_echo_chamber(self, evidence: list[Evidence]) -> tuple[bool, str]:
        """
        Detect echo chamber via content similarity — not just domain count.
        Catches Reuters wire syndicated across Yahoo, MSN, 40 local papers.
        Reuses cached MiniLM embeddings — zero extra encoding cost.
        """
        if len(evidence) < 2:
            return False, None

        # Single-domain echo chamber (original check)
        domains = set(extract_domain(e.url) for e in evidence)
        if len(domains) == 1:
            return True, "single_domain"

        # Syndication check — pairwise cosine similarity of evidence sentences
        top5       = sorted(evidence, key=lambda e: e.evidence_score, reverse=True)[:5]
        sentences  = [e.sentence for e in top5]
        embeddings = embedder.encode(sentences)   # already cached per article — fast

        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim
        sim_matrix = cos_sim(embeddings)
        n          = len(sentences)
        pairs      = [(i, j) for i in range(n) for j in range(i+1, n)]
        if not pairs:
            return False, None

        mean_sim = float(np.mean([sim_matrix[i][j] for i, j in pairs]))

        if mean_sim > 0.90:
            return True, "syndicated_content"

        return False, None
```

---

### 3.3 Data Acquisition — All Sources with Circuit Breakers (Unchanged)

```python
class SearchScraper:
    @circuit_breaker("serp")
    async def search_serp(self, query): ...

    @circuit_breaker("brave")
    async def search_brave(self, query): ...

class NewsScraper:
    @circuit_breaker("newsapi")
    async def fetch_newsapi(self, query, from_date): ...

    @circuit_breaker("gdelt")
    async def fetch_gdelt(self, query): ...

class FactCheckScraper:
    @circuit_breaker("google_factcheck")
    async def check_google_factcheck(self, claim): ...

    @circuit_breaker("snopes")
    async def scrape_snopes(self, claim): ...
```

---

### 3.4 Celery Task — asyncio.run() Pattern (Unchanged from v4)

```python
@celery_app.task(bind=True, time_limit=30, soft_time_limit=25, max_retries=3)
def verify_claim_task(self, claim_text: str, job_id: str):
    try:
        result = asyncio.run(run_pipeline_with_early_exit(claim_text, job_id))
        return result.dict()
    except SoftTimeLimitExceeded:
        return {"verdict": "UNVERIFIED", "confidence": 0.0,
                "explanation": "Verification timed out. Please retry."}
    except Exception as exc:
        raise self.retry(exc=exc)
```

**Post-hackathon — ARQ replacement:**

```python
# arq worker — no asyncio.run() needed
async def verify_claim_task(ctx, claim_text: str, job_id: str):
    result = await run_pipeline_with_early_exit(claim_text, job_id)
    return result.dict()
```

---

## 4. Verdict Engine — Full Algorithm Design

### 4.1 Context-Aware Threshold Table

```python
CLAIM_TYPE_THRESHOLDS = {
    #               TRUE_T  FALSE_T  TIER1_REQ
    "breaking_news": (0.70,  0.30,    2),
    "scientific":    (0.75,  0.25,    3),   # higher evidence bar
    "political":     (0.75,  0.25,    2),
    "general":       (0.75,  0.25,    2),
}
```

### 4.2 Complete Implementation

```python
import math
from dataclasses import dataclass
from typing import List

class VerdictEngine:
    MIN_EVIDENCE_THRESHOLD  = 0.15
    MIN_SOURCES_REQUIRED    = 3
    NEUTRAL_WEIGHT_FACTOR   = 0.3
    DIVERSITY_PENALTY       = 0.80
    TEMPORAL_MISMATCH_DAYS  = 30
    CONFLICTING_LOW         = 0.40
    CONFLICTING_HIGH        = 0.60

    def compute_verdict(self, evidence: List[Evidence],
                        claim: ParsedClaim) -> VerdictResult:

        sup = [e for e in evidence if e.stance == "SUPPORTING"]
        con = [e for e in evidence if e.stance == "CONTRADICTING"]
        neu = [e for e in evidence if e.stance == "NEUTRAL"]

        sup_w = sum(e.evidence_score for e in sup)
        con_w = sum(e.evidence_score for e in con)
        neu_w = sum(e.evidence_score for e in neu)
        total = sup_w + con_w + (neu_w * self.NEUTRAL_WEIGHT_FACTOR)

        if len(evidence) < self.MIN_SOURCES_REQUIRED or total < self.MIN_EVIDENCE_THRESHOLD:
            return VerdictResult(verdict="UNVERIFIED", confidence=0.0,
                                 claim_type=claim.claim_type)

        active = sup_w + con_w
        ratio  = sup_w / active if active > 0 else 0.5
        tier1  = sum(1 for e in evidence if e.credibility_score >= 0.90)

        # ── Context-aware thresholds ─────────────────────────────────
        true_t, false_t, tier1_req = CLAIM_TYPE_THRESHOLDS.get(
            claim.claim_type, (0.75, 0.25, 2)
        )

        temporal_mismatch = check_temporal_mismatch(evidence, claim.temporal_context)
        echo_chamber      = len(set(extract_domain(e.url) for e in evidence)) == 1

        if temporal_mismatch:
            verdict = "MISLEADING"
        elif all(e.credibility_score < 0.55 for e in evidence):
            verdict = "UNVERIFIED"
        elif ratio >= true_t  and tier1 >= tier1_req:
            verdict = "TRUE"
        elif ratio <= false_t and tier1 >= tier1_req:
            verdict = "FALSE"
        elif self.CONFLICTING_LOW <= ratio <= self.CONFLICTING_HIGH and tier1 >= 2:
            verdict = "CONFLICTING"
        else:
            verdict = "MISLEADING"

        confidence = self._bounded_sigmoid_confidence(evidence, echo_chamber)

        # ── Support/Contradict bar data ──────────────────────────────
        support_bar = {
            "support_pct":   round(ratio * 100),
            "contradict_pct": round((1 - ratio) * 100),
        }

        trace = AlgorithmTrace(
            support_ratio         = round(ratio, 3),
            total_evidence_items  = len(evidence),
            tier1_sources_found   = tier1,
            temporal_mismatch     = temporal_mismatch,
            echo_chamber_penalty  = echo_chamber,
            early_exit_triggered  = False,
            event_date_extracted  = str(claim.temporal_context.event_date),
            utterance_date        = str(claim.temporal_context.utterance_date),
            confidence_raw        = round(self._raw_conf(evidence), 3),
            confidence_final      = confidence,
            claim_type            = claim.claim_type,
            threshold_used        = {"TRUE": true_t, "FALSE": false_t},
            adversarial_signals   = [],    # filled by AdversarialDetector
            llm_provider_used     = "",    # filled after LLM call
        )

        return VerdictResult(
            verdict=verdict, confidence=confidence,
            trace=trace, support_bar=support_bar,
            claim_type=claim.claim_type,
        )

    def _bounded_sigmoid_confidence(self, evidence, echo_chamber):
        top5    = sorted(evidence, key=lambda e: e.evidence_score, reverse=True)[:5]
        weights = [e.credibility_score for e in top5]
        scores  = [e.evidence_score    for e in top5]
        raw     = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        n     = len(evidence)
        scale = 1 - math.exp(-n / 10)
        conf  = raw * (0.7 + 0.3 * scale)

        if echo_chamber:
            conf *= self.DIVERSITY_PENALTY

        return round(min(conf, 0.99), 2)

    def _raw_conf(self, evidence):
        top5    = sorted(evidence, key=lambda e: e.evidence_score, reverse=True)[:5]
        weights = [e.credibility_score for e in top5]
        scores  = [e.evidence_score    for e in top5]
        return sum(s * w for s, w in zip(scores, weights)) / sum(weights)
```

### 4.3 Early Exit Logic (Unchanged)

```python
async def run_pipeline_with_early_exit(claim: ParsedClaim,
                                        job_id: str) -> VerdictResult:
    evidence_so_far      = []
    early_exit_triggered = False

    async for batch in fetch_sources_in_batches(claim):
        evidence_so_far.extend(batch)
        await emit_ws(job_id, "searching",
                      f"Fetched {len(evidence_so_far)} evidence items...")

        sup_w = sum(e.evidence_score for e in evidence_so_far if e.stance == "SUPPORTING")
        con_w = sum(e.evidence_score for e in evidence_so_far if e.stance == "CONTRADICTING")
        tier1 = sum(1 for e in evidence_so_far if e.credibility_score >= 0.90)

        if (sup_w + con_w) > 0 and tier1 >= 2:
            ratio = sup_w / (sup_w + con_w)
            if ratio >= 0.80 or ratio <= 0.20:
                early_exit_triggered = True
                await emit_ws(job_id, "early_exit", "Strong verdict — stopping early.")
                break

    result = verdict_engine.compute_verdict(evidence_so_far, claim)
    result.trace.early_exit_triggered = early_exit_triggered
    return result
```

### 4.4 Verdict Decision Table

| ratio      | tier1 | claim_type        | temporal_mismatch | verdict     |
| ---------- | ----- | ----------------- | ----------------- | ----------- |
| ≥ 0.70    | ≥ 2  | breaking_news     | false             | TRUE        |
| ≥ 0.75    | ≥ 2  | general/political | false             | TRUE        |
| ≥ 0.75    | ≥ 3  | scientific        | false             | TRUE        |
| ≤ 0.30    | ≥ 2  | breaking_news     | false             | FALSE       |
| ≤ 0.25    | ≥ 2  | general/political | false             | FALSE       |
| 0.40–0.60 | ≥ 2  | any               | false             | CONFLICTING |
| other      | any   | any               | false             | MISLEADING  |
| any        | any   | any               | true              | MISLEADING  |
| —         | —    | —                | —                | UNVERIFIED  |

---

## 5. LLM Integration Design

### 5.1 Explanation-Only Prompt (Unchanged)

```python
PROMPT = """
You are a professional fact-checker writing an explanation for a verdict.
The verdict has already been computed by a deterministic algorithm.
Your ONLY job is to write a clear 2-3 sentence explanation.

RULES:
- Do NOT re-evaluate the claim
- Do NOT change the verdict
- Do NOT add information not present in the evidence below
- Write for a general audience

CLAIM: {claim}
VERDICT (algorithm-determined): {verdict}
CONFIDENCE: {confidence}

SUPPORTING EVIDENCE:
{supporting_evidence}

CONTRADICTING EVIDENCE:
{contradicting_evidence}

Return ONLY the explanation text. No JSON. No preamble. 2-3 sentences.
"""
```

### 5.2 LLM Provider Chain — LM Studio Primary (v5.2)

```
LM Studio (local OpenAI-compatible server)  ← PRIMARY — local-first, no API key, offline-capable
  │ failure or TTFT > 5s
  ▼
Gemini-3-flash-preview                       ← fallback #1 — low-latency cloud fallback
  │ failure
  ▼
grok-4.20-reasoning                  ← fallback #2 — low-latency cloud fallback
  │ failure
  ▼
Rule-based                                 ← always available, no LLM required
```

```python
class LMStudioProvider:
    """
    PRIMARY local LLM provider.
    Uses LM Studio's OpenAI-compatible server.
    Activate via LM_STUDIO_BASE_URL + LM_STUDIO_MODEL in .env.
    Configure GPU layer offload in LM Studio UI, not in code.
    On Windows + WSL 2: use base_url = http://host.docker.internal:1234/v1
    """
    name = "lm_studio"

    async def generate(self, prompt: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url=settings.lm_studio_base_url,
            api_key="lm-studio"
        )
        r = await client.chat.completions.create(
            model=settings.lm_studio_model,     # "qwen3-4b-2507"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=120,                     # hard cap — enforces latency budget
        )
        return r.choices[0].message.content

    async def generate_streaming(self, prompt: str):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url=settings.lm_studio_base_url,
            api_key="lm-studio"
        )
        async with client.chat.completions.stream(
            model=settings.lm_studio_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=120,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta


class GeminiFlashLiteProvider:
    """Fallback #1 — only called if LM Studio fails or times out."""
    name = "gemini"

    async def generate(self, prompt: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            "gemini-3-flash-preview",
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=256,
            )
        )
        return model.generate_content(prompt).text


class GrokProvider:
    """Fallback #2 — only called if Gemini fails."""
    name = "grok"

    async def generate(self, prompt: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url="https://api.x.ai/v1",
            api_key=settings.xai_api_key
        )
        r = await client.chat.completions.create(
            model="grok-4.20-reasoning",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=256,
        )
        return r.choices[0].message.content


class RuleBasedProvider:
    """Final fallback — no LLM required. Always available."""
    name = "rule_based"

    def generate(self, verdict, evidence_count, tier1_count) -> str:
        templates = {
            "TRUE":        f"Supported by {evidence_count} sources including {tier1_count} Tier-1.",
            "FALSE":       f"Contradicted by {evidence_count} sources including {tier1_count} Tier-1.",
            "CONFLICTING": f"High-credibility sources disagree. {tier1_count} Tier-1 on each side.",
            "MISLEADING":  f"Evidence shows inconsistencies across {evidence_count} sources.",
            "UNVERIFIED":  f"Insufficient evidence ({evidence_count} sources checked).",
        }
        return templates.get(verdict, "Verdict determined by weighted evidence scoring.")


class LLMClient:
    """
    Priority chain: LM Studio → Gemini → Grok → rule-based.
    Streaming via generate_streaming(); TTFT timeout = 5s before fallback.
    """

    def _get_providers(self):
        return [LMStudioProvider(), GeminiFlashLiteProvider(), GrokProvider()]

    async def explain_streaming(self, prompt: str, job_id: str,
                                 verdict_result: VerdictResult) -> str:
        """
        Stream explanation tokens to WebSocket.
        Applies 5s TTFT timeout — if LM Studio doesn't return the first token
        within 5s, fall back to the next provider immediately.
        """
        for provider in self._get_providers():
            if not hasattr(provider, "generate_streaming"):
                try:
                    text = await asyncio.wait_for(provider.generate(prompt), timeout=10.0)
                    await emit_ws(job_id, "explaining", text, progress=95)
                    return text, provider.name
                except Exception:
                    continue

            full_text = []
            try:
                async for token in provider.generate_streaming(prompt):
                    full_text.append(token)
                    await emit_ws(job_id, "explaining_chunk", token, progress=88)

                return "".join(full_text), provider.name

            except asyncio.TimeoutError:
                continue
            except Exception:
                continue

        rb   = RuleBasedProvider()
        text = rb.generate(verdict_result.verdict,
                           verdict_result.trace.total_evidence_items,
                           verdict_result.trace.tier1_sources_found)
        return text, rb.name

    async def explain(self, prompt: str, verdict_result: VerdictResult) -> tuple[str, str]:
        """Non-streaming path — for cache hits and final fallback."""
        for provider in self._get_providers():
            try:
                text = await asyncio.wait_for(provider.generate(prompt), timeout=10.0)
                return text, provider.name
            except Exception:
                continue

        rb   = RuleBasedProvider()
        text = rb.generate(verdict_result.verdict,
                           verdict_result.trace.total_evidence_items,
                           verdict_result.trace.tier1_sources_found)
        return text, rb.name
```

---

## 6. Database Design

### 6.1 Schema (v5.0 — adds mutation_chains, source_credibility_dynamic)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE claims (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_text        TEXT NOT NULL,
    normalized_text TEXT,
    language        VARCHAR(10),
    input_type      VARCHAR(20),
    embedding       VECTOR(384),
    event_date      DATE,
    utterance_date  DATE,
    claim_type      VARCHAR(20) DEFAULT 'general',
    mutation_chain_id UUID,       -- FK to mutation_chains
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON claims
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE mutation_chains (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_claim_id UUID REFERENCES claims(id),
    variant_count   INT DEFAULT 1,
    first_seen_at   TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE mutation_variants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_id            UUID REFERENCES mutation_chains(id),
    claim_id            UUID REFERENCES claims(id),
    similarity_score    FLOAT,
    first_seen_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_id        UUID REFERENCES claims(id) ON DELETE CASCADE,
    verdict         VARCHAR(20) CHECK (verdict IN
                    ('TRUE','FALSE','MISLEADING','CONFLICTING','UNVERIFIED')),
    confidence      FLOAT CHECK (confidence BETWEEN 0 AND 1),
    explanation     TEXT,
    algorithm_trace JSONB,     -- includes claim_type, threshold_used, adversarial_signals, llm_provider_used
    sub_claims      JSONB,
    evidence_graph  JSONB,     -- {nodes, edges}
    support_bar     JSONB,     -- {support_pct, contradict_pct}
    is_compound     BOOLEAN DEFAULT FALSE,
    processing_ms   INTEGER,
    early_exit      BOOLEAN DEFAULT FALSE,
    cached          BOOLEAN DEFAULT FALSE,
    llm_provider    VARCHAR(30),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sources (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id      UUID REFERENCES reports(id) ON DELETE CASCADE,
    name           VARCHAR(255),
    url            TEXT,
    credibility    FLOAT,       -- static base score
    dynamic_score  FLOAT,       -- current dynamic score (denormalized)
    stance         VARCHAR(20),
    published_at   TIMESTAMP,
    extracted_text TEXT,
    evidence_score FLOAT
);

CREATE TABLE source_credibility_dynamic (
    domain              VARCHAR(255) PRIMARY KEY,
    base_score          FLOAT NOT NULL,
    feedback_adjustment FLOAT DEFAULT 0.0,   -- ∈ [-1, +1]
    consistency_score   FLOAT DEFAULT 0.5,   -- ∈ [0, 1]
    dynamic_score       FLOAT GENERATED ALWAYS AS (
        GREATEST(0.05, LEAST(1.0,
            base_score + (feedback_adjustment * 0.3) + (consistency_score * 0.2)
        ))
    ) STORED,
    correct_feedback    INT DEFAULT 0,
    incorrect_feedback  INT DEFAULT 0,
    total_reports_30d   INT DEFAULT 0,
    aligned_reports_30d INT DEFAULT 0,
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feedback (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id UUID REFERENCES reports(id),
    rating    VARCHAR(20) CHECK (rating IN ('correct','incorrect','partial')),
    comment   TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE telemetry_nli (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sentence    TEXT,
    claim       TEXT,
    predicted   VARCHAR(20),
    user_rating VARCHAR(20),
    report_id   UUID REFERENCES reports(id),
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

## 7. API Design

**Base URL:** `https://api.osint-verify.io/v1`

### 7.1 POST `/verify`

```json
Request:  { "claim": "...", "input_type": "text" }
Response: { "job_id": "uuid", "status": "queued",
            "estimated_seconds": 8,
            "websocket_url": "wss://..." }
```

### 7.2 WebSocket `/ws/{job_id}`

**Cold start (real events):**

```json
{ "stage": "parsing",    "progress": 10, "message": "Extracting entities... (breaking_news detected)" }
{ "stage": "searching",  "progress": 30, "message": "Querying 10 sources..." }
{ "stage": "scoring",    "progress": 70, "message": "Computing weighted scores..." }
{ "stage": "explaining", "progress": 85, "message": "Generating explanation (LM Studio)..." }
{ "stage": "complete",   "progress": 100, "verdict": "FALSE", "confidence": 0.84,
  "support_bar": {"support_pct": 8, "contradict_pct": 92},
  "report_id": "uuid", "cached": false }
```

### 7.3 GET `/mutation/{claim_id}`

```json
{
  "chain_id": "uuid",
  "original_claim": "COVID vaccine has microchips",
  "original_first_seen": "2021-01-15",
  "variant_count": 3,
  "variants": [
    { "text": "5G microchips in COVID vaccine", "similarity": 0.81,
      "first_seen": "2021-02-03", "verdict": "FALSE" },
    { "text": "Bill Gates tracking people via vaccine",
      "similarity": 0.74, "first_seen": "2021-03-12", "verdict": "FALSE" }
  ]
}
```

### 7.4 GET `/credibility/{domain}`

```json
{
  "domain": "ndtv.com",
  "base_score":          0.78,
  "feedback_adjustment": 0.04,
  "consistency_score":   0.82,
  "dynamic_score":       0.80,
  "correct_feedback":    47,
  "incorrect_feedback":  11
}
```

### 7.5 GET `/metrics`

```json
{
  "verdict_distribution":    { "TRUE": 142, "FALSE": 389, "MISLEADING": 201, "CONFLICTING": 47, "UNVERIFIED": 89 },
  "avg_confidence":          0.81,
  "avg_processing_ms":       5840,
  "cache_hit_rate":          0.67,
  "early_exit_rate":         0.43,
  "llm_provider_usage":      { "lm_studio": 0.71, "gemini": 0.18, "grok": 0.08, "rule_based": 0.03 },
  "claim_type_distribution": { "general": 0.45, "political": 0.30, "breaking_news": 0.15, "scientific": 0.10 },
  "circuit_breaker_opens":   { "newsapi": 3, "snopes": 1 }
}
```

---

## 8. Chrome Extension Design

### 8.1 manifest.json (Unchanged)

```json
{
  "manifest_version": 3,
  "name": "OSINT Verify",
  "version": "1.0.0",
  "permissions": ["contextMenus", "activeTab", "scripting", "storage"],
  "host_permissions": ["<all_urls>"],
  "background": { "service_worker": "background.js" },
  "action": { "default_popup": "popup.html" },
  "content_scripts": [{ "matches": ["<all_urls>"], "js": ["content.js"] }]
}
```

### 8.2 Verdict Color Scheme (Unchanged)

```javascript
const VERDICT_COLORS = {
  TRUE:        { bg: "#dcfce7", border: "#16a34a", text: "#15803d" },
  FALSE:       { bg: "#fee2e2", border: "#dc2626", text: "#991b1b" },
  MISLEADING:  { bg: "#fef3c7", border: "#d97706", text: "#92400e" },
  CONFLICTING: { bg: "#fed7aa", border: "#ea580c", text: "#9a3412" },
  UNVERIFIED:  { bg: "#f3f4f6", border: "#6b7280", text: "#374151" },
};
```

### 8.3 Sub-Claim Breakdown UI (Unchanged from v4)

```javascript
function renderSubClaimBreakdown(subClaims) {
  const icons = { TRUE:"✅", FALSE:"❌", MISLEADING:"⚠️", CONFLICTING:"🔀", UNVERIFIED:"❓" };
  const rows = subClaims.map(sc => `
    <div class="sub-claim-row">
      <span class="sub-icon">${icons[sc.verdict]}</span>
      <span class="sub-text">${truncate(sc.text, 60)}</span>
      <span class="sub-badge" style="color: ${VERDICT_COLORS[sc.verdict].text}">
        ${sc.verdict}
      </span>
    </div>
  `).join("");
  return `<div class="sub-claim-section"><div class="sub-heading">Claim breakdown</div>${rows}</div>`;
}
```

### 8.4 Support/Contradict Bar (New in v5.0)

```javascript
function renderSupportBar(supportBar) {
  const { support_pct, contradict_pct } = supportBar;
  const supportFill    = `width: ${support_pct}%`;
  const contradictFill = `width: ${contradict_pct}%`;

  return `
    <div class="evidence-bars">
      <div class="bar-row">
        <span class="bar-label">Support</span>
        <div class="bar-track">
          <div class="bar-fill bar-support" style="${supportFill}"></div>
        </div>
        <span class="bar-pct">${support_pct}%</span>
      </div>
      <div class="bar-row">
        <span class="bar-label">Contradict</span>
        <div class="bar-track">
          <div class="bar-fill bar-contradict" style="${contradictFill}"></div>
        </div>
        <span class="bar-pct">${contradict_pct}%</span>
      </div>
    </div>
  `;
}
// CSS: .bar-support { background: #16a34a; } .bar-contradict { background: #dc2626; }
```

### 8.5 WebSocket Handler (v5.0)

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateProgressBar(data.progress);
  updateStatus(data.message);

  if (data.stage === "complete") {
    ws.close();
    displayVerdict(data.verdict, data.confidence, data.report_id);

    if (data.sub_claims?.length > 0)
      renderSubClaimBreakdown(data.sub_claims);

    if (data.support_bar)
      renderSupportBar(data.support_bar);

    if (data.cached)
      document.querySelector('#cache-indicator').style.display = 'block';
  }
};
```

---

## 9. Source Credibility System

### 9.1 Static Tier Table

| Tier | Score      | Examples                                                      |
| ---- | ---------- | ------------------------------------------------------------- |
| 1    | 0.90–1.00 | reuters.com, apnews.com, bbc.com, who.int, un.org, .gov, .int |
| 2    | 0.75–0.89 | nytimes.com, guardian.com, ndtv.com, aljazeera.com            |
| 3    | 0.55–0.74 | wikipedia.org, major regional papers                          |
| 4    | 0.30–0.54 | Blogs, unverified sites                                       |
| 5    | 0.00–0.29 | Known misinformation domains                                  |

### 9.2 Dynamic Credibility Scorer (`analysis/dynamic_credibility.py`)

```python
class DynamicCredibilityScorer:
    """
    Updates source credibility from user feedback.
    Runs ASYNCHRONOUSLY after feedback — NOT on the critical path.
    """

    async def get_score(self, domain: str) -> float:
        row = await db.fetchrow(
            "SELECT dynamic_score FROM source_credibility_dynamic WHERE domain=$1",
            domain
        )
        if row:
            return row["dynamic_score"]
        return self._heuristic_score(domain)

    async def update_from_feedback(self, report_id: str, rating: str):
        """Called after POST /feedback — async, non-blocking."""
        sources = await db.fetch(
            "SELECT name FROM sources WHERE report_id=$1", report_id
        )
        for source in sources:
            domain = extract_domain(source["name"])
            if rating == "correct":
                await db.execute(
                    "UPDATE source_credibility_dynamic "
                    "SET correct_feedback = correct_feedback + 1, updated_at=NOW() "
                    "WHERE domain=$1", domain
                )
            elif rating == "incorrect":
                await db.execute(
                    "UPDATE source_credibility_dynamic "
                    "SET incorrect_feedback = incorrect_feedback + 1, updated_at=NOW() "
                    "WHERE domain=$1", domain
                )
            await self._recalculate_adjustment(domain)

    async def _recalculate_adjustment(self, domain: str):
        row = await db.fetchrow(
            "SELECT correct_feedback, incorrect_feedback "
            "FROM source_credibility_dynamic WHERE domain=$1", domain
        )
        if not row:
            return
        c, i  = row["correct_feedback"], row["incorrect_feedback"]
        total = c + i
        if total == 0:
            return
        adj = (c - i) / total   # ∈ [-1, +1]
        await db.execute(
            "UPDATE source_credibility_dynamic "
            "SET feedback_adjustment=$1, updated_at=NOW() WHERE domain=$2",
            adj, domain
        )

    def _heuristic_score(self, domain: str) -> float:
        if domain in credibility_db:
            return credibility_db[domain]["score"]
        if domain.endswith((".gov", ".int")): return 0.90
        if domain.endswith(".edu"):           return 0.80
        if domain.endswith(".org"):           return 0.55
        return 0.25
```

---

## 10. Caching Strategy & UX Buffering

### 10.1 Cache Layers (v5.0)

| Key                      | TTL | Content                                                       |
| ------------------------ | --- | ------------------------------------------------------------- |
| `claim:{md5}`          | 24h | Full VerdictResult JSON                                       |
| `search:{query_md5}`   | 1h  | Search result list                                            |
| `article:{url_md5}`    | 12h | Article text                                                  |
| `emb:{url_md5}`        | 12h | **MiniLM sentence embeddings (dict: sentence→vector)** |
| `llm:{prompt_md5}`     | 6h  | LLM explanation                                               |
| `credibility:{domain}` | 7d  | Dynamic credibility float                                     |
| `cb:{source_name}`     | 60s | Circuit breaker open flag                                     |

### 10.2 Multi-Level Cache Lookup (Unchanged)

```python
async def verify_with_cache(claim_text: str, job_id: str) -> VerdictResult:
    key    = f"claim:{md5(claim_text)}"
    cached = await redis.get(key)
    if cached:
        result = VerdictResult.parse_raw(cached)
        result.cached = True
        await ux_buffer(job_id, result)
        return result

    emb     = embedder.encode(claim_text)
    similar = await db.find_similar(emb, threshold=0.85)
    if similar:
        result = similar.cached_result
        result.cached = True
        await ux_buffer(job_id, result)
        return result

    result = await run_pipeline_with_early_exit(claim_text, job_id)
    await redis.setex(key, 86400, result.json())
    return result
```

### 10.3 UX Buffer (Unchanged from v4)

```python
UX_BUFFER_STAGES = [
    (0.0, 20,  "Parsing claim..."),
    (0.6, 50,  "Checking knowledge graph..."),
    (1.2, 80,  "Cross-referencing sources..."),
    (1.8, 100, "Verdict ready."),
]

async def ux_buffer(job_id: str, cached_result: VerdictResult):
    for delay, progress, message in UX_BUFFER_STAGES:
        await asyncio.sleep(0 if delay == 0 else 0.6)
        await emit_ws(job_id, "searching", message, progress)

    await emit_ws(job_id, "complete",
                  verdict    = cached_result.verdict,
                  confidence = cached_result.confidence,
                  support_bar = cached_result.support_bar,
                  report_id  = cached_result.report_id,
                  cached     = True,
                  sub_claims = cached_result.sub_claims,
                  progress   = 100)
```

---

## 11. Performance & GPU Memory Management

### 11.1 Model Placement Strategy (Unchanged)

```python
# startup.py — loaded ONCE at application start
nlp      = spacy.load("en_core_web_sm")               # CPU — 50MB RAM
embedder = SentenceTransformer("all-MiniLM-L6-v2",
                                device="cpu")          # CPU — 500MB RAM
stance_classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli",
    device=0                                           # GPU — ~1.6GB VRAM
)
# LM Studio GPU layer offload is configured in the LM Studio UI, not in application code
```

### 11.2 VRAM Budget (Unchanged)

```
RTX 4050 (6GB VRAM)
────────────────────────────────────
BART-large-MNLI       ~1,600 MB  ✅
CUDA overhead          ~500 MB   ✅
────────────────────────────────────
Total GPU              ~2,100 MB ✅ (3.9GB free)
```

### 11.3 Performance Improvements (v5.2)

```
Technique                              Saving (estimated)
──────────────────────────────────────────────────────────────
BART-MNLI batching (25 sentences)      −50% vs per-sentence loop
Embedding cache (Redis TTL 12h)        −100% encoding for cached articles
asyncio.gather() parallelism           −60% vs sequential fetching
Redis cache hit + UX buffer            8s → 1.8s (78% reduction)
Early Exit (2× Tier-1 found)           −40–60% fetch time
Evidence cap (5×5 = 25 max)            −30% extraction time
Circuit breaker (skip dead API)        −5s per dead source
BART-MNLI on GPU                       −70% vs CPU inference
LLM response cache (6h TTL)            −3s on repeat claims
LM Studio local server (primary LLM)   0ms startup if already running
```

---

## 12. Circuit Breaker Design (Unchanged)

### 12.1 States

```
CLOSED (normal) →[3 failures]→ OPEN (skip, 60s TTL)
OPEN →[60s]→ HALF-OPEN (try once)
HALF-OPEN →[success]→ CLOSED
HALF-OPEN →[failure]→ OPEN (reset 60s)
```

### 12.2 Implementation

```python
class RedisCircuitBreakerStorage(pybreaker.CircuitBreakerStorage):
    def __init__(self, name: str):
        super().__init__(name)
        self.redis = aioredis.from_url(settings.redis_url)
        self.key   = f"cb:{name}"

    @property
    def state(self):
        val = self.redis.get(self.key)
        return pybreaker.STATE_OPEN if val else pybreaker.STATE_CLOSED

    @state.setter
    def state(self, new_state):
        if new_state == pybreaker.STATE_OPEN:
            self.redis.setex(self.key, 60, "open")
        else:
            self.redis.delete(self.key)
```

---

## 13. Explainability UI 2.0

### 13.1 Evidence Graph Builder (`analysis/explainability.py`)

```python
from dataclasses import dataclass
from typing import List

@dataclass
class GraphNode:
    id:     str         # domain
    tier:   int
    stance: str         # SUPPORTING / CONTRADICTING / NEUTRAL
    score:  float       # evidence_score

@dataclass
class GraphEdge:
    source:        str
    target:        str
    claim_overlap: float   # cosine similarity between extracted sentences

def build_evidence_graph(evidence: List[Evidence]) -> dict:
    """
    Build node-edge graph for dashboard SVG rendering.
    Nodes = unique source domains.
    Edges = pairs with high sentence similarity (overlap > 0.6).
    """
    # Deduplicate by domain
    domain_evidence = {}
    for e in evidence:
        domain = extract_domain(e.url)
        if domain not in domain_evidence or e.evidence_score > domain_evidence[domain].evidence_score:
            domain_evidence[domain] = e

    nodes = [
        GraphNode(
            id     = domain,
            tier   = get_tier(e.credibility_score),
            stance = e.stance,
            score  = round(e.evidence_score, 3),
        )
        for domain, e in domain_evidence.items()
    ]

    # Compute pairwise sentence overlap for edges
    edges = []
    domains = list(domain_evidence.keys())
    for i in range(len(domains)):
        for j in range(i + 1, len(domains)):
            e1 = domain_evidence[domains[i]]
            e2 = domain_evidence[domains[j]]
            emb1 = embedder.encode(e1.sentence)
            emb2 = embedder.encode(e2.sentence)
            overlap = float(cosine_similarity([emb1], [emb2])[0][0])
            if overlap > 0.6:
                edges.append(GraphEdge(
                    source=domains[i], target=domains[j],
                    claim_overlap=round(overlap, 2)
                ))

    return {
        "nodes": [{"id": n.id, "tier": n.tier,
                   "stance": n.stance, "score": n.score} for n in nodes],
        "edges": [{"source": e.source, "target": e.target,
                   "claim_overlap": e.claim_overlap} for e in edges],
    }
```

### 13.2 React Evidence Graph Component (`frontend/src/components/EvidenceGraph.jsx`)

```jsx
import { useEffect, useRef } from "react";
import * as d3 from "d3";

const STANCE_COLORS = {
  SUPPORTING:    "#16a34a",
  CONTRADICTING: "#dc2626",
  NEUTRAL:       "#9ca3af",
};

export function EvidenceGraph({ graphData }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!graphData?.nodes?.length) return;
    const { nodes, edges } = graphData;
    const width = 600, height = 400;

    const svg = d3.select(svgRef.current)
      .attr("viewBox", `0 0 ${width} ${height}`)
      .style("overflow", "visible");
    svg.selectAll("*").remove();

    const simulation = d3.forceSimulation(nodes)
      .force("link",   d3.forceLink(edges).id(d => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg.append("g").selectAll("line")
      .data(edges).join("line")
      .attr("stroke", "#d1d5db").attr("stroke-width", d => d.claim_overlap * 3);

    const node = svg.append("g").selectAll("circle")
      .data(nodes).join("circle")
      .attr("r", d => 8 + (1 - d.tier * 0.15) * 8)
      .attr("fill", d => STANCE_COLORS[d.stance] || "#9ca3af")
      .attr("stroke", "#fff").attr("stroke-width", 2)
      .call(d3.drag()
        .on("start", (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
        .on("drag",  (e, d) => { d.fx=e.x; d.fy=e.y; })
        .on("end",   (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; })
      )
      .append("title")
      .text(d => `${d.id}\n${d.stance}\nScore: ${d.score}`);

    simulation.on("tick", () => {
      link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
      node.attr("cx", d => d.x).attr("cy", d => d.y);
    });
  }, [graphData]);

  return (
    <div className="mt-4 border rounded-lg p-4 bg-gray-50">
      <p className="text-sm font-medium text-gray-500 mb-3">Evidence Network</p>
      <svg ref={svgRef} className="w-full" />
      <div className="flex gap-4 mt-2 text-xs text-gray-500">
        <span><span className="inline-block w-3 h-3 rounded-full bg-green-600 mr-1"/>Supporting</span>
        <span><span className="inline-block w-3 h-3 rounded-full bg-red-600 mr-1"/>Contradicting</span>
        <span><span className="inline-block w-3 h-3 rounded-full bg-gray-400 mr-1"/>Neutral</span>
      </div>
    </div>
  );
}
```

### 13.3 Source Timeline Component (`frontend/src/components/SourceTimeline.jsx`)

```jsx
export function SourceTimeline({ sources }) {
  if (!sources?.length) return null;
  const sorted = [...sources].sort((a, b) =>
    new Date(a.published_at) - new Date(b.published_at)
  );

  return (
    <div className="mt-4 border-t pt-4">
      <p className="text-sm font-medium text-gray-500 mb-3">Source Timeline</p>
      <div className="relative pl-4 border-l-2 border-gray-200 space-y-3">
        {sorted.map((s, i) => (
          <div key={i} className="relative">
            <div className={`absolute -left-[9px] w-4 h-4 rounded-full border-2 border-white
              ${s.stance==="SUPPORTING" ? "bg-green-500" :
                s.stance==="CONTRADICTING" ? "bg-red-500" : "bg-gray-400"}`}
            />
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-800">{s.name}</p>
              <p className="text-xs text-gray-500">
                {new Date(s.published_at).toLocaleDateString()} · {s.stance}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 14. Rumor Evolution Tracker

### 14.1 Implementation (`analysis/mutation_detector.py`)

```python
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class MutationResult:
    is_variant:       bool
    chain_id:         Optional[str]
    similarity:       float
    original_claim:   Optional[str]

class RumorEvolutionTracker:
    MUTATION_THRESHOLD = 0.75

    async def find_or_create_chain(self, claim_text: str,
                                    claim_embedding: list,
                                    claim_id: str) -> MutationResult:
        """
        Check if this claim is a variant of an existing claim in the mutation chain.
        Uses the hnsw index already built on claims.embedding.
        """
        # Find nearest neighbor above mutation threshold
        similar = await db.fetchrow("""
            SELECT c.id, c.raw_text, c.mutation_chain_id,
                   1 - (c.embedding <=> $1) AS similarity
            FROM claims c
            WHERE c.id != $2
              AND 1 - (c.embedding <=> $1) > $3
            ORDER BY c.embedding <=> $1
            LIMIT 1
        """, claim_embedding, claim_id, self.MUTATION_THRESHOLD)

        if not similar:
            # New original claim — create a chain for it
            chain_id = await db.fetchval("""
                INSERT INTO mutation_chains (original_claim_id)
                VALUES ($1)
                RETURNING id
            """, claim_id)

            await db.execute(
                "UPDATE claims SET mutation_chain_id=$1 WHERE id=$2",
                chain_id, claim_id
            )
            return MutationResult(is_variant=False, chain_id=chain_id,
                                   similarity=0.0, original_claim=None)

        # Found a variant — link to existing chain
        chain_id = similar["mutation_chain_id"]
        if chain_id is None:
            # Parent has no chain yet — create one
            chain_id = await db.fetchval("""
                INSERT INTO mutation_chains (original_claim_id)
                VALUES ($1) RETURNING id
            """, similar["id"])
            await db.execute(
                "UPDATE claims SET mutation_chain_id=$1 WHERE id=$2",
                chain_id, similar["id"]
            )

        # Link current claim and insert variant record
        await db.execute(
            "UPDATE claims SET mutation_chain_id=$1 WHERE id=$2",
            chain_id, claim_id
        )
        await db.execute("""
            INSERT INTO mutation_variants (chain_id, claim_id, similarity_score)
            VALUES ($1, $2, $3)
        """, chain_id, claim_id, float(similar["similarity"]))

        await db.execute("""
            UPDATE mutation_chains
            SET variant_count = variant_count + 1, updated_at=NOW()
            WHERE id=$1
        """, chain_id)

        return MutationResult(
            is_variant=True, chain_id=chain_id,
            similarity=float(similar["similarity"]),
            original_claim=similar["raw_text"],
        )

    async def get_chain(self, claim_id: str) -> dict:
        """Return full evolution chain for GET /mutation/{claim_id}."""
        chain = await db.fetchrow("""
            SELECT mc.id, mc.variant_count, mc.first_seen_at,
                   c.raw_text AS original_text
            FROM mutation_chains mc
            JOIN claims c ON c.id = mc.original_claim_id
            WHERE mc.id = (SELECT mutation_chain_id FROM claims WHERE id=$1)
        """, claim_id)

        if not chain:
            return {}

        variants = await db.fetch("""
            SELECT c.raw_text, mv.similarity_score, mv.first_seen_at,
                   r.verdict
            FROM mutation_variants mv
            JOIN claims c ON c.id = mv.claim_id
            LEFT JOIN reports r ON r.claim_id = mv.claim_id
            WHERE mv.chain_id = $1
            ORDER BY mv.first_seen_at
        """, chain["id"])

        return {
            "chain_id":         str(chain["id"]),
            "original_claim":   chain["original_text"],
            "original_first_seen": chain["first_seen_at"].isoformat(),
            "variant_count":    chain["variant_count"],
            "variants": [
                {
                    "text":         v["raw_text"],
                    "similarity":   round(v["similarity_score"], 3),
                    "first_seen":   v["first_seen_at"].isoformat(),
                    "verdict":      v["verdict"],
                }
                for v in variants
            ],
        }
```

---

## 15. User Personalization

### 15.1 User Profile Manager (`ux/user_profile.py`)

```python
from enum import Enum

class UserProfile(str, Enum):
    GENERAL    = "general"
    JOURNALIST = "journalist"
    RESEARCHER = "researcher"

PROFILE_CONFIG = {
    UserProfile.GENERAL: {
        "explanation_sentences": 2,
        "show_evidence_graph":   False,
        "show_algorithm_trace":  False,
        "show_mutation_chain":   False,
        "show_support_bar":      True,
        "show_sources":          3,
    },
    UserProfile.JOURNALIST: {
        "explanation_sentences": 4,
        "show_evidence_graph":   True,
        "show_algorithm_trace":  True,      # summary only
        "show_mutation_chain":   True,
        "show_support_bar":      True,
        "show_sources":          10,
    },
    UserProfile.RESEARCHER: {
        "explanation_sentences": 4,
        "show_evidence_graph":   True,
        "show_algorithm_trace":  True,      # full raw JSON
        "show_mutation_chain":   True,
        "show_support_bar":      True,
        "show_sources":          -1,        # all sources
        "show_confidence_formula": True,
        "show_telemetry_link":   True,
    },
}

def filter_report_by_profile(report: dict, profile: UserProfile) -> dict:
    """
    Return a view of the report appropriate for the user profile.
    Same backend data — different depth.
    """
    config = PROFILE_CONFIG[profile]
    filtered = {
        "report_id":   report["report_id"],
        "verdict":     report["verdict"],
        "confidence":  report["confidence"],
        "explanation": " ".join(
            report["explanation"].split(".")[:config["explanation_sentences"]]
        ).strip() + ".",
        "support_bar": report["support_bar"],
        "sources":     (report["sources"] if config["show_sources"] == -1
                        else report["sources"][:config["show_sources"]]),
    }

    if config["show_evidence_graph"]:
        filtered["evidence_graph"] = report.get("evidence_graph")

    if config["show_mutation_chain"]:
        filtered["mutation_chain"] = report.get("mutation_chain")

    if config["show_algorithm_trace"]:
        filtered["algorithm_trace"] = report.get("algorithm_trace")

    return filtered
```

---

## 16. Adversarial Robustness

### 16.1 Adversarial Signal Detector (`analysis/adversarial_detector.py`)

```python
from datetime import datetime, timedelta
from typing import List

class AdversarialDetector:
    PARAPHRASE_THRESHOLD = 0.70   # lower than mutation threshold
    SPAM_THRESHOLD_DOMAINS = 3
    SPAM_WINDOW_HOURS = 1

    async def detect(self, evidence: List[Evidence],
                      claim_embedding: list,
                      claim_id: str) -> list[str]:
        """
        Returns list of adversarial signal strings.
        These are warnings, not blockers — verdict still proceeds.
        """
        signals = []

        # Signal 1: Paraphrase of known false claim
        similar_false = await db.fetchrow("""
            SELECT c.raw_text, r.verdict,
                   1 - (c.embedding <=> $1) AS similarity
            FROM claims c
            JOIN reports r ON r.claim_id = c.id
            WHERE r.verdict = 'FALSE'
              AND c.id != $2
              AND 1 - (c.embedding <=> $1) > $3
            ORDER BY c.embedding <=> $1
            LIMIT 1
        """, claim_embedding, claim_id, self.PARAPHRASE_THRESHOLD)

        if similar_false:
            signals.append(
                f"PARAPHRASE_OF_FALSE_CLAIM: "
                f"{round(similar_false['similarity'], 2)} similarity to known false claim"
            )

        # Signal 2: Coordinated low-credibility source spam
        low_cred_sources = [e for e in evidence if e.credibility_score < 0.55]
        recent_cutoff    = datetime.utcnow() - timedelta(hours=self.SPAM_WINDOW_HOURS)
        recent_low_cred  = [
            e for e in low_cred_sources
            if e.published_at and e.published_at > recent_cutoff
        ]
        unique_spam_domains = len(set(extract_domain(e.url) for e in recent_low_cred))

        if unique_spam_domains >= self.SPAM_THRESHOLD_DOMAINS:
            signals.append(
                f"COORDINATED_SOURCE_SPAM: "
                f"{unique_spam_domains} low-credibility sources published within 1h"
            )

        # Signal 3: Low-credibility majority
        if (len(evidence) >= 3
                and len(low_cred_sources) > len(evidence) * 0.7):
            signals.append("LOW_CREDIBILITY_MAJORITY: >70% of sources are Tier 4/5")

        return signals
```

---

## 17. Standalone Verdict Pipeline

### 17.1 Module Structure (`verdict_pipeline/`)

```
verdict_pipeline/
├── __init__.py        # exports: VerdictEngine, EvidenceExtractor, run_verdict
├── engine.py          # VerdictEngine (same algorithm — no DB dependency)
├── extractor.py       # EvidenceExtractor (BART + MiniLM — GPU/CPU)
├── models.py          # ParsedClaim, Evidence, VerdictResult dataclasses
├── storage.py         # SQLiteStorage adapter (optional persistence)
├── cli.py             # CLI entrypoint
└── batch.py           # batch_verify(claims: list[str]) → list[VerdictResult]
```

### 17.2 Standalone Engine (`verdict_pipeline/engine.py`)

```python
"""
Standalone Verdict Engine — NO FastAPI, Celery, Redis, or PostgreSQL.
Import directly for batch processing or tracking use cases.

Usage:
    from verdict_pipeline import run_verdict
    result = run_verdict(claim_text, evidence_list)
"""

from verdict_pipeline.models import ParsedClaim, Evidence, VerdictResult
import math

CLAIM_TYPE_THRESHOLDS = {
    "breaking_news": (0.70, 0.30, 2),
    "scientific":    (0.75, 0.25, 3),
    "political":     (0.75, 0.25, 2),
    "general":       (0.75, 0.25, 2),
}

def run_verdict(claim: ParsedClaim, evidence: list[Evidence]) -> VerdictResult:
    """
    Pure function — no I/O, no external dependencies.
    Same deterministic algorithm as the full backend.
    """
    engine = VerdictEngine()
    return engine.compute_verdict(evidence, claim)

def run_verdict_text(claim_text: str, evidence_dicts: list[dict]) -> VerdictResult:
    """
    Convenience wrapper: accepts raw strings + dicts.
    Handles parsing and Evidence construction internally.
    """
    from verdict_pipeline.extractor import EvidenceExtractor
    extractor = EvidenceExtractor()
    claim    = extractor.parse_claim(claim_text)
    evidence = [Evidence(**d) for d in evidence_dicts]
    return run_verdict(claim, evidence)
```

### 17.3 CLI (`verdict_pipeline/cli.py`)

```python
"""
Usage:
    python -m verdict_pipeline verify "Iran lost the war"
    python -m verdict_pipeline batch claims.txt
    python -m verdict_pipeline batch claims.txt --output results.jsonl
"""

import argparse, json, sys
from verdict_pipeline import run_verdict_text

def main():
    parser = argparse.ArgumentParser(prog="verdict_pipeline")
    sub    = parser.add_subparsers(dest="command")

    verify_p = sub.add_parser("verify")
    verify_p.add_argument("claim", type=str)
    verify_p.add_argument("--evidence", type=str, help="JSON file of evidence")

    batch_p  = sub.add_parser("batch")
    batch_p.add_argument("input_file", type=str, help="One claim per line")
    batch_p.add_argument("--output", type=str, default=None)

    args = parser.parse_args()

    if args.command == "verify":
        evidence = []
        if args.evidence:
            with open(args.evidence) as f:
                evidence = json.load(f)
        result = run_verdict_text(args.claim, evidence)
        print(json.dumps(result.dict(), indent=2))

    elif args.command == "batch":
        with open(args.input_file) as f:
            claims = [line.strip() for line in f if line.strip()]

        results = []
        for claim in claims:
            r = run_verdict_text(claim, [])
            results.append({"claim": claim, **r.dict()})

        output = "\n".join(json.dumps(r) for r in results)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

if __name__ == "__main__":
    main()
```

---

## 18. Security Design

### 18.1 Input Validation

```python
class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=2000)

    @validator('claim')
    def sanitize(cls, v):
        return bleach.clean(v, tags=[], strip=True)
```

### 18.2 Rate Limiting + Image Cleanup

```python
@app.post("/verify")
@limiter.limit("10/minute")
async def verify(request: Request, body: VerifyRequest): ...

async def process_image(path: str):
    try:
        return await ocr.extract(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
```

---

## 19. Deployment Design

### 19.1 Docker Compose (v5.2)

```yaml
version: "3.9"
services:
  backend:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  celery_worker:
    build: .
    env_file: .env
    depends_on: [redis, postgres]
    command: celery -A backend.tasks worker --loglevel=info --concurrency=4
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: hackathon_db
      POSTGRES_USER: omii
      POSTGRES_PASSWORD: omii00
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru

volumes:
  pgdata:
```

### 19.2 Environment Variables (v5.2)

```env
# ── LLM — Primary is LOCAL (free, no key) ──────────────────────────
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen3-4b-2507   # primary local model in LM Studio
OFFLINE_MODE=false              # set true to skip all cloud LLMs

# ── LM Studio on Windows + WSL 2 ─────────────────────────────────────
# If the backend runs inside WSL 2, use the Windows host bridge:
# LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
# LM_STUDIO_MODEL=qwen3-4b-2507

# ── LLM — Cloud Fallbacks (optional) ────────────────────────────────
GEMINI_API_KEY=from_aistudio.google.com
XAI_API_KEY=from_console.x.ai

# ── Data Sources ────────────────────────────────────────────────────
SERP_API_KEY=your_key
NEWS_API_KEY=your_key
GOOGLE_FACTCHECK_API_KEY=your_key
GOOGLE_VISION_API_KEY=your_key

# ── INFRASTRUCTURE ───────────────────────────────────────────────────
DATABASE_URL=postgresql://omii:omii00@localhost:5432/hackathon_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=generate_a_random_32_character_string_here

# ── Algorithm Config ─────────────────────────────────────────────────
EVIDENCE_MAX_ARTICLES=5
EVIDENCE_MAX_SENTENCES=5
EARLY_EXIT_TIER1_THRESHOLD=2
EARLY_EXIT_RATIO_HIGH=0.80
EARLY_EXIT_RATIO_LOW=0.20
CIRCUIT_BREAKER_FAIL_MAX=3
CIRCUIT_BREAKER_RESET_SECONDS=60
CONFIDENCE_SIGMOID_SCALE=10
MUTATION_SIMILARITY_THRESHOLD=0.75
ADVERSARIAL_PARAPHRASE_THRESHOLD=0.70

# ── Hardening (v5.2) ─────────────────────────────────────────────────
FREEZE_CREDIBILITY=false        # set true for demo — locks all credibility writes
GATHER_TIMEOUT_SECONDS=15       # asyncio.wait_for deadline on all source gathering
HTTP_REQUEST_TIMEOUT_SECONDS=5  # per-request httpx connect+read timeout

# ── UX ───────────────────────────────────────────────────────────────
UX_BUFFER_MS=1800
```

### 19.3 Windows + WSL 2 Deployment Note

> **Do NOT run the backend in VirtualBox.** VirtualBox has no GPU passthrough for consumer GPUs — BART-MNLI runs on CPU, cold-start exceeds 60s.

On Windows, use **WSL 2 (Ubuntu 22.04)**:

- WSL 2 exposes the host RTX 4050 natively via NVIDIA's WSL driver stack (`nvidia-smi` works inside WSL 2)
- Docker Desktop with WSL 2 backend provides GPU access inside containers
- LM Studio runs on Windows; reachable from WSL 2 at `http://host.docker.internal:1234`
- All backend ports auto-forward from WSL 2 to Windows localhost — Chrome extension requires no config change

See Setup Guide §18 for the step-by-step WSL 2 + LM Studio installation.

---

## 20. Project Structure

```
osint-verify/
│
├── backend/
│   ├── main.py
│   ├── api_router.py
│   ├── config.py
│   ├── tasks.py                          # Celery — asyncio.run()
│   ├── pipeline.py                       # run_pipeline_with_early_exit
│   ├── circuit_breaker.py
│   │
│   ├── analysis/
│   │   ├── claim_parser.py               # + claim_type detection
│   │   ├── evidence_extractor.py         # + batched BART + embedding cache
│   │   ├── verdict_engine.py             # + context-aware thresholds
│   │   ├── explainability.py             # evidence graph + support bar builder
│   │   ├── mutation_detector.py          # rumor evolution tracker
│   │   ├── adversarial_detector.py       # adversarial signal detection
│   │   └── dynamic_credibility.py        # feedback-adjusted scores
│   │
│   ├── scraper/
│   │   ├── search_scraper.py
│   │   ├── news_scraper.py
│   │   ├── factcheck_scraper.py
│   │   ├── knowledge_scraper.py
│   │   └── web_scraper.py
│   │
│   ├── ocr/
│   │   ├── image_reader.py
│   │   └── reverse_image_search.py
│   │
│   ├── llm/
│   │   ├── client.py                     # tries LM Studio → Gemini → Grok → rule-based
│   │   ├── explainer.py
│   │   ├── lm_studio_provider.py         # PRIMARY — local OpenAI-compatible server
│   │   ├── gemini_provider.py            # fallback #1
│   │   ├── grok_provider.py              # fallback #2
│   │   └── rule_based_provider.py        # final fallback
│   │
│   ├── ux/
│   │   ├── cache_buffer.py               # UX buffering
│   │   └── user_profile.py               # profile-aware report filtering
│   │
│   ├── reports/
│   │   └── report_generator.py
│   │
│   ├── db/
│   │   ├── models.py                     # + mutation_chains, source_credibility_dynamic
│   │   ├── database.py
│   │   └── migrations/
│   │
│   ├── cache/
│   │   └── redis_client.py               # + embedding cache helpers
│   │
│   └── data/
│       └── source_credibility.json       # base scores
│
├── verdict_pipeline/                     # ← STANDALONE MODULE (no FastAPI/Celery)
│   ├── __init__.py
│   ├── engine.py
│   ├── extractor.py
│   ├── models.py
│   ├── storage.py                        # SQLite adapter
│   ├── cli.py
│   └── batch.py
│
├── extension/
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js                          # + SupportBar + SubClaimBreakdown
│   ├── popup.css
│   ├── background.js
│   └── content.js
│
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── pages/Report.jsx
│       └── components/
│           ├── VerdictCard.jsx
│           ├── SubClaimBreakdown.jsx
│           ├── EvidenceGraph.jsx          # D3 SVG interactive graph
│           ├── SourceTimeline.jsx         # publication date timeline
│           ├── SupportBar.jsx             # green/red ratio bar
│           ├── MutationChain.jsx          # rumor evolution timeline
│           └── UserProfileToggle.jsx      # general / journalist / researcher
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## 21. Technology Stack

| Component             | Technology                          | Note                                                                                                   |
| --------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------ |
| API Framework         | FastAPI 0.110                       | Async REST + WebSocket                                                                                 |
| Language              | Python 3.11                         |                                                                                                        |
| Task Queue            | Celery 5 + asyncio.run()            | Sync workers, async pipeline via run()                                                                 |
| Post-hackathon queue  | ARQ                                 | Native async, no asyncio.run() wrapper                                                                 |
| Database              | PostgreSQL 16 + pgvector            | hnsw index + mutation_chains                                                                           |
| Cache + CB state      | Redis 7                             | Multi-layer TTL + UX buffer + embedding cache                                                          |
| NER                   | spaCy en_core_web_sm                | CPU only                                                                                               |
| Embeddings            | all-MiniLM-L6-v2                    | CPU only                                                                                               |
| Stance                | BART-large-MNLI                     | GPU only,**batched (≤25 per call)**                                                             |
| **LLM Primary** | **LM Studio + Qwen3 4B 2507** | **LOCAL OpenAI-compatible server — zero local API key; tuned for short explanation generation** |
| LLM Local Backup      | Llama 3.2 3B in LM Studio           | Smaller local backup model                                                                             |
| LLM Fallback #1       | Gemini 2.5 Flash-Lite               | Low-latency cloud fallback, temperature=0.0                                                            |
| LLM Fallback #2       | Grok 4 Fast Non-Reasoning           | Low-latency cloud fallback, temperature=0.0                                                            |
| LLM Offline           | Rule-based                          | Always available, no model                                                                             |
| Circuit Breaker       | pybreaker + Redis                   | Shared across workers                                                                                  |
| OCR                   | EasyOCR + Tesseract                 |                                                                                                        |
| Image Search          | Google Vision API                   | Event date comparison                                                                                  |
| HTTP Client           | httpx (async)                       |                                                                                                        |
| Scraping              | BeautifulSoup4, Playwright          |                                                                                                        |
| Translation           | deep-translator                     | Free, no key                                                                                           |
| Evidence Graph        | D3.js (v7)                          | Interactive SVG in dashboard                                                                           |
| Extension             | Chrome Manifest V3                  | SupportBar + SubClaimBreakdown                                                                         |
| Dashboard             | React 18 + Vite                     | EvidenceGraph + SourceTimeline + MutationChain                                                         |
| Styling               | TailwindCSS 3                       |                                                                                                        |
| Deployment            | Docker + Railway                    | Free tier                                                                                              |

---

## 22. Error Handling & Telemetry

### 22.1 Source Fetch Failures

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
valid   = [r for r in results if not isinstance(r, Exception)]
if not valid:
    return VerdictResult(verdict="UNVERIFIED",
                         explanation="All sources unavailable. Please retry.")
```

### 22.2 LLM Failure Chain

```
LM Studio (local) → Gemini Flash-Lite → Grok Fast Non-Reasoning → rule-based
```

Rule-based always works. System never returns without explanation.

### 22.3 Celery Task Failure

```python
@celery_app.task(bind=True, time_limit=30, soft_time_limit=25)
def verify_claim_task(self, claim_text: str, job_id: str):
    try:
        return asyncio.run(run_pipeline_with_early_exit(claim_text, job_id))
    except SoftTimeLimitExceeded:
        return {"verdict": "UNVERIFIED", "explanation": "Timed out. Please retry."}
    except Exception as exc:
        raise self.retry(exc=exc)
```

### 22.4 Telemetry

```python
async def log_nli(sentence, claim, predicted, report_id):
    await db.execute(
        "INSERT INTO telemetry_nli (sentence,claim,predicted,report_id) "
        "VALUES ($1,$2,$3,$4)",
        sentence, claim, predicted, report_id
    )

async def log_feedback(report_id, rating):
    await db.execute(
        "UPDATE telemetry_nli SET user_rating=$1 WHERE report_id=$2",
        rating, report_id
    )
    # Also trigger async dynamic credibility update
    asyncio.create_task(
        dynamic_credibility_scorer.update_from_feedback(report_id, rating)
    )
```

**What telemetry enables (v5.2):**

- Identify BART-MNLI misclassification patterns
- Track which LLM provider is used most often (LM Studio vs fallbacks)
- Monitor dynamic credibility drift per domain
- Track mutation chain growth rate
- Circuit breaker frequency per source
- Claim type distribution over time
- Build labelled dataset from user feedback for future fine-tuning
- Surface all metrics at `/metrics` endpoint

### 22.5 HTTP Error Codes

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 202  | Accepted, pipeline started                |
| 400  | Invalid input                             |
| 404  | Job or report not found                   |
| 429  | Rate limit exceeded                       |
| 503  | All sources and LLM providers unavailable |

---

## 23. Demo Impact Design (v5.1)

### 23.1 Verdict Reason Tag Engine (`analysis/verdict_reason_tag.py`)

Deterministic — zero LLM. Tag selected from a priority-ordered lookup table using `algorithm_trace` fields.

```python
from dataclasses import dataclass

@dataclass
class VerdictReasonTag:
    tag:   str    # human-readable sentence
    code:  str    # machine key, e.g. "WIDELY_DEBUNKED"

REASON_TAG_RULES = [
    # Each rule: (verdict, condition_fn, tag_text, code)
    # Rules are evaluated in order — first match wins.

    ("FALSE",
     lambda t: t["tier1_sources_found"] >= 2 and
               all(s["tier"] == 1 for s in t.get("top_sources", [])),
     "Fact-checked and refuted by major news outlets",
     "REFUTED_BY_TIER1"),

    ("FALSE",
     lambda t: t["tier1_sources_found"] >= 2,
     "Widely debunked by credible sources",
     "WIDELY_DEBUNKED"),

    ("TRUE",
     lambda t: t["early_exit_triggered"] and t["tier1_sources_found"] >= 1,
     "Verified by a major news outlet",
     "VERIFIED_EARLY"),

    ("TRUE",
     lambda t: t["tier1_sources_found"] >= 2,
     "Confirmed by multiple credible sources",
     "CONFIRMED_MULTI_TIER1"),

    ("MISLEADING",
     lambda t: t["temporal_mismatch"],
     "Old content reused in a new context",
     "TEMPORAL_REUSE"),

    ("MISLEADING",
     lambda t: t["echo_chamber_penalty"],
     "Only reported by a single source",
     "ECHO_CHAMBER"),

    ("MISLEADING",
     lambda t: t.get("adversarial_signals") and
               "LOW_CREDIBILITY_MAJORITY" in " ".join(t["adversarial_signals"]),
     "Primarily from unreliable sources",
     "LOW_CRED_MAJORITY"),

    ("CONFLICTING",
     lambda t: t["tier1_sources_found"] >= 2,
     "Experts and credible outlets disagree",
     "EXPERTS_DISAGREE"),

    ("UNVERIFIED",
     lambda t: t["total_evidence_items"] < 3,
     "Not enough evidence found to decide",
     "INSUFFICIENT_EVIDENCE"),

    ("UNVERIFIED",
     lambda t: True,   # catch-all for UNVERIFIED
     "No reliable sources cover this claim",
     "NO_RELIABLE_SOURCES"),
]

def get_verdict_reason_tag(verdict: str, trace: dict) -> VerdictReasonTag:
    for rule_verdict, condition, tag_text, code in REASON_TAG_RULES:
        if rule_verdict == verdict:
            try:
                if condition(trace):
                    return VerdictReasonTag(tag=tag_text, code=code)
            except Exception:
                continue
    # Fallback
    return VerdictReasonTag(tag="Verdict determined by evidence scoring", code="DEFAULT")
```

The tag is added to the report response:

```python
report["verdict_reason_tag"] = get_verdict_reason_tag(
    verdict_result.verdict,
    verdict_result.trace.__dict__
).tag
```

---

### 23.2 Top Insight Generator (`analysis/top_insight.py`)

Single most impactful evidence sentence, auto-generated — no LLM.

```python
def get_top_insight(evidence: list[Evidence], verdict: str) -> str:
    """
    Generate ONE sentence that summarises the strongest evidence.
    Deterministic — built from evidence data, not LLM.
    Examples:
      "3 Tier-1 sources (Reuters, BBC, AP) contradict this claim."
      "Reuters published a fact-check directly refuting this claim."
      "No Tier-1 source covers this claim."
    """
    tier1_contra = [e for e in evidence
                    if e.stance == "CONTRADICTING" and e.credibility_score >= 0.90]
    tier1_sup    = [e for e in evidence
                    if e.stance == "SUPPORTING"    and e.credibility_score >= 0.90]

    if tier1_contra:
        names = ", ".join(e.source_name for e in tier1_contra[:3])
        n     = len(tier1_contra)
        return f"{n} Tier-1 source{'s' if n > 1 else ''} ({names}) contradict this claim."

    if tier1_sup:
        names = ", ".join(e.source_name for e in tier1_sup[:3])
        n     = len(tier1_sup)
        return f"{n} Tier-1 source{'s' if n > 1 else ''} ({names}) support this claim."

    # Fallback: most credible source found
    if evidence:
        best = max(evidence, key=lambda e: e.credibility_score)
        return f"Most credible source found: {best.source_name} ({best.stance.lower()})."

    return "No reliable sources found for this claim."
```

---

### 23.3 Killer Screen — React Component (`frontend/src/components/KillerScreen.jsx`)

The single result view. All critical information visible without scrolling or clicking.

```jsx
import { useState } from "react";
import { EvidenceGraph }   from "./EvidenceGraph";
import { SourceTimeline }  from "./SourceTimeline";
import { MutationAlert }   from "./MutationAlert";
import { CredibilityShiftBadge } from "./CredibilityShiftBadge";

const VERDICT_STYLES = {
  TRUE:        { bg: "bg-green-50",  border: "border-green-500", badge: "bg-green-600",  icon: "✅" },
  FALSE:       { bg: "bg-red-50",    border: "border-red-500",   badge: "bg-red-600",    icon: "❌" },
  MISLEADING:  { bg: "bg-amber-50",  border: "border-amber-500", badge: "bg-amber-600",  icon: "⚠️" },
  CONFLICTING: { bg: "bg-orange-50", border: "border-orange-400",badge: "bg-orange-500", icon: "🔀" },
  UNVERIFIED:  { bg: "bg-gray-50",   border: "border-gray-400",  badge: "bg-gray-500",   icon: "❓" },
};

export function KillerScreen({ report }) {
  const [showGraph,    setShowGraph]    = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);

  const style   = VERDICT_STYLES[report.verdict] ?? VERDICT_STYLES.UNVERIFIED;
  const confPct = Math.round(report.confidence * 100);

  return (
    <div className={`rounded-xl border-2 ${style.border} ${style.bg} p-5 space-y-4 max-w-xl`}>

      {/* ── 1. Verdict Badge + Confidence ─────────────────── */}
      <div className="flex items-center justify-between">
        <div className={`${style.badge} text-white text-lg font-bold px-4 py-2 rounded-lg flex items-center gap-2`}>
          <span>{style.icon}</span>
          <span>{report.verdict}</span>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-gray-800">{confPct}%</p>
          <p className="text-xs text-gray-500">Confidence</p>
        </div>
      </div>

      {/* ── 2. Support / Contradict Bar ───────────────────── */}
      {report.support_bar && (
        <div className="space-y-1.5">
          <SupportBarRow
            label="Support"
            pct={report.support_bar.support_pct}
            color="bg-green-500"
          />
          <SupportBarRow
            label="Contradict"
            pct={report.support_bar.contradict_pct}
            color="bg-red-500"
          />
        </div>
      )}

      {/* ── 3. Verdict Reason Tag ─────────────────────────── */}
      {report.verdict_reason_tag && (
        <p className="text-sm font-semibold text-gray-700 border-l-4 border-gray-400 pl-3 italic">
          "{report.verdict_reason_tag}"
        </p>
      )}

      {/* ── 4. Top Insight ────────────────────────────────── */}
      {report.top_insight && (
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Top Insight
          </p>
          <p className="text-sm text-gray-800">{report.top_insight}</p>
        </div>
      )}

      {/* ── 5. Mutation Alert (inline — headline) ─────────── */}
      {report.mutation_chain?.variant_count >= 2 && (
        <MutationAlert chain={report.mutation_chain} />
      )}

      {/* ── 6. Top Sources with Credibility Shift ─────────── */}
      {report.sources?.slice(0, 3).map((s, i) => (
        <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-gray-100">
          <a href={s.url} target="_blank" rel="noreferrer"
             className="text-blue-600 hover:underline truncate max-w-[60%]">
            {s.name}
          </a>
          <CredibilityShiftBadge
            base={s.credibility_score}
            dynamic={s.dynamic_credibility_score}
          />
        </div>
      ))}

      {/* ── 7. Secondary CTAs ─────────────────────────────── */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => setShowGraph(g => !g)}
          className="flex-1 text-xs border border-gray-300 rounded-md py-1.5 hover:bg-white transition">
          {showGraph ? "Hide" : "View"} Evidence Graph
        </button>
        <button
          onClick={() => setShowTimeline(t => !t)}
          className="flex-1 text-xs border border-gray-300 rounded-md py-1.5 hover:bg-white transition">
          {showTimeline ? "Hide" : "View"} Timeline
        </button>
      </div>

      {showGraph    && <EvidenceGraph  graphData={report.evidence_graph} />}
      {showTimeline && <SourceTimeline sources={report.sources} />}
    </div>
  );
}

function SupportBarRow({ label, pct, color }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 shrink-0">{label}</span>
      <div className="flex-1 bg-gray-200 rounded-full h-3">
        <div className={`${color} h-3 rounded-full transition-all duration-500`}
             style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-gray-700">{pct}%</span>
    </div>
  );
}
```

---

### 23.4 Mutation Alert — Inline Component (`frontend/src/components/MutationAlert.jsx`)

```jsx
export function MutationAlert({ chain }) {
  if (!chain || chain.variant_count < 2) return null;

  const variants = chain.similar_claims ?? [];
  const years    = variants.map(v => new Date(v.first_seen).getFullYear());
  const minYear  = Math.min(...years, new Date(chain.first_seen ?? Date.now()).getFullYear());

  return (
    <div className="bg-amber-50 border border-amber-400 rounded-lg p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-amber-600 text-lg">⚠️</span>
        <p className="text-sm font-bold text-amber-800">
          Misinformation Pattern Detected
        </p>
      </div>
      <p className="text-xs text-amber-700">
        This claim is part of a spreading pattern with{" "}
        <strong>{chain.variant_count} known variants</strong> since {minYear}.
      </p>

      {/* Compact timeline */}
      <div className="space-y-1 pl-2 border-l-2 border-amber-300">
        {variants.slice(0, 3).map((v, i) => (
          <div key={i} className="text-xs text-amber-700">
            <span className="font-mono text-amber-500 mr-2">
              {new Date(v.first_seen).getFullYear()}
            </span>
            {v.text.length > 55 ? v.text.slice(0, 55) + "…" : v.text}
          </div>
        ))}
        <div className="text-xs font-semibold text-amber-800">
          {new Date().getFullYear()} ── <em>this claim ← you are here</em>
        </div>
      </div>

      <a href={`/report/${chain.chain_id}`}
         className="text-xs text-amber-600 underline hover:text-amber-800">
        View Full Evolution Timeline →
      </a>
    </div>
  );
}
```

---

### 23.5 Credibility Shift Badge (`frontend/src/components/CredibilityShiftBadge.jsx`)

```jsx
export function CredibilityShiftBadge({ base, dynamic }) {
  // Only show delta if scores differ by >= 0.03
  const delta = dynamic - base;
  const showDelta = Math.abs(delta) >= 0.03;

  if (!showDelta) {
    return (
      <span className="text-xs font-mono text-gray-500">
        {base.toFixed(2)}
      </span>
    );
  }

  const improved = delta > 0;
  return (
    <div className="flex items-center gap-1 text-xs font-mono">
      <span className="text-gray-400">{base.toFixed(2)}</span>
      <span className="text-gray-400">→</span>
      <span className={improved ? "text-green-600 font-semibold" : "text-red-500 font-semibold"}>
        {dynamic.toFixed(2)}
      </span>
      <span title={improved ? "Improved reliability based on feedback" : "Trust declined based on accuracy history"}>
        {improved ? "↑" : "↓"}
      </span>
    </div>
  );
}
```

---

### 23.6 Extension Popup — Killer Layout (`extension/popup.js` additions)

```javascript
// Main render function — v5.1 killer layout
function renderKillerResult(data) {
  const container = document.querySelector('#result');
  container.innerHTML = `
    ${renderVerdictBadge(data.verdict, data.confidence)}
    ${renderSupportBar(data.support_bar)}
    ${renderReasonTag(data.verdict_reason_tag)}
    ${renderTopInsight(data.top_insight)}
    ${renderMutationAlert(data.mutation_chain)}
    ${renderTopSources(data.sources?.slice(0, 3))}
    ${renderSubClaimBreakdown(data.sub_claims)}
    ${renderSecondaryActions()}
  `;
}

function renderReasonTag(tag) {
  if (!tag) return '';
  return `
    <div class="reason-tag">
      <span class="reason-quote">"${tag}"</span>
    </div>
  `;
}

function renderTopInsight(insight) {
  if (!insight) return '';
  return `
    <div class="top-insight-box">
      <span class="insight-label">Top Insight</span>
      <p class="insight-text">${insight}</p>
    </div>
  `;
}

function renderMutationAlert(chain) {
  if (!chain || chain.variant_count < 2) return '';
  const years = (chain.similar_claims || [])
    .map(v => new Date(v.first_seen).getFullYear());
  const minYear = Math.min(...years, new Date().getFullYear());

  const variants = (chain.similar_claims || []).slice(0, 3)
    .map(v => `<div class="mut-row">
      <span class="mut-year">${new Date(v.first_seen).getFullYear()}</span>
      <span class="mut-text">${truncate(v.text, 55)}</span>
    </div>`).join('');

  return `
    <div class="mutation-alert">
      <div class="mut-header">⚠️ <strong>Misinformation Pattern Detected</strong></div>
      <p class="mut-desc">Part of a spreading pattern —
         <strong>${chain.variant_count} variants</strong> since ${minYear}.</p>
      <div class="mut-timeline">
        ${variants}
        <div class="mut-row mut-current">
          <span class="mut-year">${new Date().getFullYear()}</span>
          <em>this claim ← you are here</em>
        </div>
      </div>
    </div>
  `;
}

function renderTopSources(sources) {
  if (!sources?.length) return '';
  const rows = sources.map(s => {
    const delta     = (s.dynamic_credibility_score ?? s.credibility_score) - s.credibility_score;
    const showDelta = Math.abs(delta) >= 0.03;
    const scoreHtml = showDelta
      ? `<span class="cred-base">${s.credibility_score.toFixed(2)} →</span>
         <span class="cred-dynamic ${delta > 0 ? 'cred-up' : 'cred-down'}">
           ${(s.dynamic_credibility_score).toFixed(2)} ${delta > 0 ? '↑' : '↓'}
         </span>`
      : `<span class="cred-score">${s.credibility_score.toFixed(2)}</span>`;
    return `
      <div class="source-row">
        <a href="${s.url}" target="_blank" class="source-name">${s.name}</a>
        <span class="source-stance ${s.stance.toLowerCase()}">${s.stance}</span>
        <span class="source-cred">${scoreHtml}</span>
      </div>
    `;
  }).join('');
  return `<div class="sources-list">${rows}</div>`;
}

function renderSecondaryActions() {
  return `
    <div class="action-row">
      <button id="btn-graph"    class="action-btn">View Evidence Graph</button>
      <button id="btn-timeline" class="action-btn">View Timeline</button>
    </div>
  `;
}
```

---

### 23.7 API Response — New Fields (v5.1)

The following fields are added to the report response JSON:

```json
{
  "verdict_reason_tag": "Widely debunked by credible sources",
  "top_insight":        "3 Tier-1 sources (Reuters, BBC, AP) contradict this claim.",
  "support_bar": {
    "support_pct":    8,
    "contradict_pct": 92
  },
  "mutation_chain": {
    "chain_id":       "uuid-v4",
    "variant_count":  3,
    "similar_claims": [
      { "text": "COVID vaccines have tracking chips",
        "similarity": 0.88, "first_seen": "2021-01-15" }
    ]
  },
  "sources": [
    {
      "name":                      "NDTV",
      "credibility_score":         0.78,
      "dynamic_credibility_score": 0.82,
      "stance":                    "CONTRADICTING",
      "url":                       "https://..."
    }
  ]
}
```

---

## 24. Hardening Design (v5.2)

### 24.1 asyncio.gather() Runaway Timeout (`pipeline.py`)

Every `asyncio.gather()` call in the pipeline is wrapped with a deadline. A hanging TCP connection can no longer permanently lock a Celery worker.

```python
import asyncio

# Per-request HTTP timeout — set on every httpx.AsyncClient
HTTP_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=2.0)

async def fetch_sources_safe(claim: ParsedClaim) -> list[Evidence]:
    """
    Gathers all source scrapers with a hard outer deadline.
    Returns whatever arrived before the timeout — never raises.
    """
    tasks = [
        search_scraper.search_all(claim),
        news_scraper.fetch_all(claim),
        factcheck_scraper.check_all(claim),
        knowledge_scraper.fetch(claim),
    ]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=15.0    # absolute ceiling — no single task can exceed this
        )
        gather_timeout = False
    except asyncio.TimeoutError:
        results = []
        gather_timeout = True

    valid = [r for r in results if not isinstance(r, Exception)]
    evidence = flatten(valid)
    return evidence, gather_timeout
```

Integration in pipeline:

```python
evidence, gather_timeout = await fetch_sources_safe(claim)
result.trace.gather_timeout_triggered = gather_timeout
```

---

### 24.2 Sybil Attack Protection (`api_router.py` + `dynamic_credibility.py`)

```python
# api_router.py — rate limit on /feedback
@app.post("/v1/feedback")
@limiter.limit("5/hour")   # per IP — max 5 feedback submissions per hour
async def submit_feedback(request: Request, body: FeedbackRequest):
    user_trust = 1.0 if request.state.authenticated else 0.2
    await dynamic_credibility_scorer.update_from_feedback(
        body.report_id, body.rating,
        trust_weight=user_trust
    )
    return {"status": "received"}
```

```python
# dynamic_credibility.py — trust-weighted update
async def update_from_feedback(self, report_id: str,
                                rating: str,
                                trust_weight: float = 1.0):
    if os.getenv("FREEZE_CREDIBILITY") == "true":
        return    # safe for demo — writes disabled, reads still work

    # Max per-IP contribution capped at ±0.05 total shift
    # enforced by trust_weight: anonymous = 0.2 × weight = ~0.02 per submission
    sources = await db.fetch("SELECT name FROM sources WHERE report_id=$1", report_id)
    for source in sources:
        domain = extract_domain(source["name"])
        delta  = trust_weight * (1 if rating == "correct" else -1)
        await db.execute("""
            UPDATE source_credibility_dynamic
            SET correct_feedback   = correct_feedback   + $2,
                incorrect_feedback = incorrect_feedback + $3,
                updated_at         = NOW()
            WHERE domain = $1
        """, domain,
             max(delta, 0),   # correct increment
             max(-delta, 0),  # incorrect increment
        )
        await self._recalculate_adjustment(domain)
```

---

### 24.3 UNVERIFIED Null-State UI (`frontend/src/components/KillerScreen.jsx`)

```jsx
// Replace the SupportBarRow block with null-state awareness

function SupportBarSection({ report }) {
  const { verdict, support_bar, algorithm_trace } = report;

  // Null state: UNVERIFIED with zero evidence
  if (verdict === "UNVERIFIED" && algorithm_trace?.total_evidence_items === 0) {
    return (
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-3 text-center">
        <p className="text-sm text-gray-400 italic">No evidence collected</p>
        <p className="text-xs text-gray-300 mt-0.5">
          Sources may cover this later — check back
        </p>
      </div>
    );
  }

  // Normal state: render bars as usual
  return (
    <div className="space-y-1.5">
      <SupportBarRow label="Support"
        pct={support_bar?.support_pct ?? 0} color="bg-green-500" />
      <SupportBarRow label="Contradict"
        pct={support_bar?.contradict_pct ?? 0} color="bg-red-500" />
    </div>
  );
}
```

And in the extension `popup.js`:

```javascript
function renderSupportBar(data) {
  // Guard: UNVERIFIED with zero evidence
  if (data.verdict === "UNVERIFIED" && data.algorithm_trace?.total_evidence_items === 0) {
    return `<div class="bar-empty">
      <span class="bar-empty-text">No evidence collected</span>
    </div>`;
  }
  // Normal render (existing code)
  return renderSupportBarNormal(data.support_bar);
}
```

---

### 24.4 WSL 2 + LM Studio Architecture (Windows Development)

```
Windows Host
│
├── LM Studio (Windows app)
│     └── Local server at http://localhost:1234/v1
│         Model: qwen3-4b-2507 (or llama-3.2-3b)
│         GPU layers: set in LM Studio UI (max that fits below BART VRAM budget)
│
├── WSL 2 — Ubuntu 22.04
│     ├── FastAPI backend         (python uvicorn)
│     ├── Celery worker           (python celery)
│     ├── Docker Desktop (WSL2 backend)
│     │     ├── postgres container  → localhost:5432
│     │     └── redis container     → localhost:6379
│     │
│     └── GPU access
│           nvidia-smi   → sees RTX 4050 natively (CUDA via WSL driver)
│           BART-MNLI    → device=0 (GPU)
│           LM Studio    → partial GPU offload configured in app UI
│
└── Chrome (Windows)
      └── Extension → http://localhost:8000/v1
                      (WSL 2 port auto-forwarded to Windows localhost)
```

**Key WSL 2 addresses:**

```python
# From WSL 2, reach Windows host services:
LM_STUDIO_BASE_URL = "http://host.docker.internal:1234/v1"

# From WSL 2, reach Docker containers:
DATABASE_URL = "postgresql://osint:pass@localhost:5432/osint_verify"
REDIS_URL    = "redis://localhost:6379/0"
```

**VRAM split on RTX 4050 (6GB) with LM Studio GPU offload:**

```
BART-large-MNLI (locked to GPU)      ~1,600 MB
CUDA overhead                          ~500 MB
LM Studio — Qwen3 4B 2507 (partial) ~1,200-1,500 MB  ← adjust layers in LM Studio
─────────────────────────────────────────────────
Total GPU                             ~3,300 MB  ✅ (2.7 GB free)

System RAM
LM Studio CPU layers (remainder)    ~1,500 MB
MiniLM + spaCy                        ~550 MB
FastAPI + Celery                    ~1,000 MB
─────────────────────────────────────────────────
Total RAM                            ~3,050 MB  ✅ (12.9 GB free on 16GB)
```

---

### 24.5 Key Design Decisions Table (v5.2 additions)

| Decision                | Choice                                       | Reason                                                                           |
| ----------------------- | -------------------------------------------- | -------------------------------------------------------------------------------- |
| Local LLM model         | Qwen3 4B 2507 or Llama 3.2 3B                | Small local models keep the 120-token explanation path within the latency budget |
| Explanation deadline    | max_tokens=120 + TTFT fallback at 5s         | Physically caps latency; TTFT streaming hides remainder                          |
| Echo chamber detection  | Pairwise MiniLM similarity >0.90             | Domain check misses syndicated wire copy                                         |
| Sybil protection        | IP rate-limit 5/hr + trust weight 0.2× anon | Prevents review bombing without requiring login                                  |
| Demo credibility lock   | FREEZE_CREDIBILITY=true env flag             | Clean demo scores; dynamic logic still runs in code                              |
| Gather timeout          | asyncio.wait_for(gather, 15s) + httpx 5s     | No runaway scraper can lock a Celery worker                                      |
| UNVERIFIED bar          | Dashed empty state when 0 evidence           | 0%/0% bar looks broken to judges                                                 |
| Windows dev environment | WSL 2 + LM Studio                            | VirtualBox has no GPU passthrough; WSL 2 is native CUDA                          |
| LM Studio integration   | LMStudioProvider (same OpenAI client shape)  | Primary local runtime; GPU layer tuning via GUI not code                         |

---

*SDD v5.2.0 — OSINT Rumor Verification Platform — Radio Frequency — VIT Code Apex 2.0*
