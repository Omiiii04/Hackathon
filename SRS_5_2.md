# Software Requirements Specification (SRS)

## OSINT Rumor Verification Platform

---

| Field          | Details                             |
| -------------- | ----------------------------------- |
| Document Title | Software Requirements Specification |
| Project Name   | OSINT Rumor Verification Platform   |
| Team           | Radio Frequency                     |
| Event          | VIT Code Apex 2.0 — PS ID 1.5      |
| Version        | 5.2.0                               |
| Status         | Final — All Reviews Incorporated   |
| Date           | April 2026                          |

---

## Revision History

| Version | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Date       |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| 1.0.0   | Initial draft                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | March 2026 |
| 2.0.0   | LLM explanation-only; deterministic verdict engine; Early Exit; neutral penalization; source diversity; temporal mismatch; log-scaled confidence; MVP boundary                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | March 2026 |
| 3.0.0   | CONFLICTING verdict; bounded sigmoid confidence; hnsw index; temperature=0.0; circuit breakers; GPU memory management; telemetry                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | March 2026 |
| 4.0.0   | Celery async fix (asyncio.run wrapper); UX cache buffering; utterance-date vs event-date disambiguation; sub-claim UI breakdown; explicit event loop requirement for Celery workers                                                                                                                                                                                                                                                                                                                                                                                                                                                            | March 2026 |
| 5.2.0   | **Local LLM latency fix** (smaller local model + max_tokens cap + TTFT streaming); **Echo chamber syndication loophole fix** (content-similarity check via MiniLM embeddings); **Feedback Sybil attack protection** (rate-limit + auth constraint on /feedback); **asyncio.gather() runaway timeout** (NFR for per-gather deadline); **UNVERIFIED null-state UI** (empty-state bar + "Awaiting credible coverage" tag); **LM Studio as PRIMARY local LLM runtime**; **Gemini + Grok fallback chain**; **WSL 2 GPU setup path** (replaces VirtualBox anti-pattern)                              | April 2026 |
| 5.1.0   | **Killer Screen** (single-screen result impact layout); **Verdict Reason Tags** (human-readable 1-line verdict summary); **Mutation as Headline Feature** (misinformation pattern alert — surface-level not buried); **Dynamic Credibility Shift Display** (show score change per source)                                                                                                                                                                                                                                                                                                                             | April 2026 |
| 5.0.0   | **Explainability UI 2.0** (evidence graph, support/contradict bar, source timeline); **Dynamic source credibility** (feedback-adjusted scores); **Rumor Evolution Tracking** (claim mutation lineage via pgvector); **BART-MNLI batching + embedding cache** (performance); **Context-aware thresholds** (breaking news vs scientific); **User personalization** (journalist vs general vs researcher); **Local LLM as primary** (Ollama first — zero API cost); **Standalone verdict pipeline** for independent batch tracking; ARQ post-hackathon path; adversarial robustness requirements | April 2026 |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [MVP Boundary Definition](#3-mvp-boundary-definition)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [External Interface Requirements](#6-external-interface-requirements)
7. [System Constraints](#7-system-constraints)
8. [Use Cases](#8-use-cases)
9. [Data Requirements](#9-data-requirements)
10. [Verdict Algorithm Specification](#10-verdict-algorithm-specification)
11. [Glossary](#11-glossary)

---

## 1. Introduction

### 1.1 Purpose

This document specifies all functional and non-functional requirements for the OSINT Rumor Verification Platform — an AI-powered, multi-source fact-checking system that verifies social media claims, viral messages, and image-based rumors in near real-time.

The platform uses **deterministic weighted scoring for verdict decisions** and restricts LLM usage exclusively to explanation generation — eliminating hallucination risk while maintaining full auditability.

### 1.2 Core Design Philosophy

> "We use deterministic scoring for verdicts and LLM only for explanation — not for deciding truth."

- Verdicts are **auditable** — every decision traces to weighted evidence math
- The system is **defensible** — no black-box LLM deciding what is true
- The system is **hallucination-resistant** — LLM cannot fabricate a verdict
- The system is **semantically precise** — CONFLICTING evidence is distinguished from MISLEADING framing
- The system is **psychologically trustworthy** — cache hits simulate pipeline progress to build user trust
- The system is **visually transparent** — users see evidence graphs, support bars, and source timelines, not just a badge
- The system is **adaptive** — source credibility improves from feedback; thresholds adapt to claim type
- The system is **cost-light to operate** — local LM Studio LLM is primary; cloud LLMs are optional fallbacks
- The verdict engine is **independently deployable** — can run standalone for rumor tracking without the full backend

### 1.3 Scope

The platform provides:

- Automated verification of text claims, image-based claims, and URL content
- Evidence collection from global OSINT sources in parallel with Early Exit and circuit breaker protection
- **Deterministic weighted scoring** for 5 verdict classes: TRUE / FALSE / MISLEADING / CONFLICTING / UNVERIFIED
- **LLM-generated explanation only** — temperature=0.0, receives pre-computed verdict
- Chrome browser extension with right-click verification and inline highlighting
- Multilingual support — translation at boundaries only; all internal processing in English
- **UX cache buffering** — cache hits simulate 1.5–2.0s progress stream to build user trust
- **Sub-claim breakdown UI** — compound claims show per-part verdicts in popup and dashboard
- Utterance-date vs event-date disambiguation in temporal parsing
- **Explainability UI 2.0** — evidence graph, support/contradict ratio bar, source publication timeline
- **Dynamic credibility scoring** — source reputation updates from user feedback and consistency history
- **Rumor Evolution Tracker** — tracks how a claim mutates over time (variants, spread, first appearance)
- **Context-aware verdict thresholds** — breaking news claims allow more uncertainty; scientific claims require higher tier1 weight
- **User personalization** — journalist vs general user vs researcher modes with different explanation depth
- **Local-first LLM** — LM Studio runs locally as primary; zero API key cost in offline/local mode
- **Standalone verdict pipeline** — verdict engine deployable independently for batch tracking use cases
- **Adversarial robustness** — mutation detector and paraphrase resistance

### 1.4 Definitions and Acronyms

| Term                    | Definition                                                                                      |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| OSINT                   | Open Source Intelligence — intelligence from publicly available sources                        |
| OCR                     | Optical Character Recognition                                                                   |
| NER                     | Named Entity Recognition                                                                        |
| NLI                     | Natural Language Inference                                                                      |
| LLM                     | Large Language Model — used ONLY for explanation, temperature=0.0                              |
| Verdict                 | TRUE / FALSE / MISLEADING / CONFLICTING / UNVERIFIED — determined by algorithm only            |
| CONFLICTING             | Evidence genuinely divided between ≥ 2 Tier-1 sources                                          |
| MISLEADING              | Temporal mismatch, low-credibility noise, or deceptive framing — NOT divided credible evidence |
| Evidence Score          | credibility × relevance × recency                                                             |
| Support Ratio           | supporting_weight ÷ (supporting_weight + contradicting_weight)                                 |
| Early Exit              | Stop fetching when verdict strongly determined — saves 40–60% time                            |
| UX Buffering            | Artificial 1.5–2.0s simulated progress on cache hits — prevents "instant answer distrust"     |
| Utterance Date          | The date the claim was written or shared — NOT the event it describes                          |
| Event Date              | The date the claim's subject actually occurred — what temporal parsing should extract          |
| Circuit Breaker         | Pattern skipping failed API sources instantly after M consecutive failures                      |
| hnsw                    | Hierarchical Navigable Small World — pgvector index that builds dynamically                    |
| OOM                     | Out of Memory — GPU VRAM exhaustion                                                            |
| asyncio.run()           | Python function that creates a new event loop — required for async code inside Celery tasks    |
| Claim Mutation          | A semantically similar but textually modified variant of an original claim                      |
| Rumor Evolution         | The tracked lineage of mutations a claim undergoes as it spreads                                |
| Dynamic Credibility     | A source credibility score that adjusts over time based on user feedback and accuracy history   |
| Context-Aware Threshold | Verdict thresholds that vary based on inferred claim type (breaking news, science, politics)    |
| User Profile            | A stored preference set controlling explanation depth and UI mode for a given user              |
| Standalone Pipeline     | The verdict engine packaged as an independent importable module without FastAPI/Celery          |
| ARQ                     | Async Redis Queue — a native-async task queue, planned post-hackathon Celery replacement       |
| Adversarial Claim       | A deliberately modified or paraphrased version of a false claim designed to evade detection     |

---

## 2. Overall Description

### 2.1 Product Perspective

Full-stack system:

- Python FastAPI backend — async pipeline orchestration
- Celery task queue with explicit `asyncio.run()` wrapper — enables async scrapers inside sync workers
- Chrome Browser Extension — right-click verification + sub-claim breakdown UI + explainability visuals
- React web dashboard — full report, sub-claim breakdown, evidence graph, rumor timeline, user profile
- PostgreSQL + pgvector (hnsw) — persistent storage + semantic similarity + mutation lineage
- Redis — multi-layer caching + circuit breaker state + UX buffer timing + embedding cache
- **LM Studio (local OpenAI-compatible server) — PRIMARY LLM provider, zero local API cost, no internet required**
- **`verdict_pipeline/` — standalone importable module, no FastAPI/Celery dependency**

### 2.2 Product Functions

1. Accept claims as text, image, URL, or selected webpage text
2. Detect language → translate to English at input boundary only
3. Parse claims — extract entities, **event dates (not utterance dates)**, split compound claims
4. Collect evidence in parallel with Early Exit + circuit breaker protection
5. Score evidence: `evidence_score = credibility × relevance × recency`
6. Classify stance via BART-MNLI (GPU) in **batched mode**: SUPPORTING / CONTRADICTING / NEUTRAL
7. Apply neutral penalization, source diversity check, temporal mismatch detection
8. Compute verdict via **context-aware** deterministic algorithm — 5 possible verdicts
9. Calibrate confidence using bounded sigmoid — no artificial inflation
10. Call **local LM Studio LLM** at temperature=0.0 — explanation generation only, verdict pre-determined (Gemini and Grok as fallback only)
11. Translate explanation back at output boundary
12. Simulate pipeline progress on cache hits (1.5–2.0s UX buffer)
13. Render sub-claim breakdown in popup and dashboard when is_compound=true
14. **Render Explainability UI 2.0**: evidence graph + support/contradict bar + source timeline
15. Stream live progress via WebSocket (real or simulated)
16. Log telemetry for NLP drift monitoring
17. **Track claim mutations and rumor evolution** via pgvector lineage chain
18. **Update dynamic source credibility** based on user feedback and accuracy history
19. **Adapt verdict thresholds** to claim type (breaking news, scientific, political)
20. **Serve personalized UI** based on user profile (journalist / researcher / general public)

### 2.3 User Classes

| Class          | Interface            | Primary Need                                                       |
| -------------- | -------------------- | ------------------------------------------------------------------ |
| General Public | Chrome Extension     | Quick WhatsApp forward check — simple explanation + support bar   |
| Journalist     | Web Dashboard        | Traceable source-cited evidence + full evidence graph              |
| Researcher     | REST API + Dashboard | Raw data, mutation lineage, batch tracking via standalone pipeline |
| Policy Analyst | Web Dashboard        | Trend tracking + rumor evolution timeline                          |
| Developer      | REST API             | API integration + standalone pipeline import                       |

### 2.4 Operating Environment

- Browser: Google Chrome v100+
- Backend OS: Ubuntu 22.04 LTS or POSIX
- Python: 3.11+
- GPU: RTX 4050 (6GB VRAM) — BART-MNLI on GPU; LM Studio may partially offload the local LLM if VRAM headroom remains
- RAM: 16GB system RAM
- Database: PostgreSQL 16+ with pgvector
- Cache: Redis 7+
- Deployment: Docker on Railway / Render / Fly.io (free tiers)
- **Local LLM: LM Studio local server — runs without any API key or internet**

---

## 3. MVP Boundary Definition

### 3.1 Demo MVP — Must Work Perfectly

| Feature                                                                           | Status    |
| --------------------------------------------------------------------------------- | --------- |
| Text claim input via Chrome Extension                                             | LIVE DEMO |
| Right-click "Verify Claim" on any webpage                                         | LIVE DEMO |
| NewsAPI + Wikipedia + Google Fact Check                                           | LIVE DEMO |
| BART-MNLI stance classification (batched)                                         | LIVE DEMO |
| Deterministic verdict engine (5 verdicts, context-aware thresholds)               | LIVE DEMO |
| **LM Studio local LLM explanation at temperature=0.0 — no API key needed** | LIVE DEMO |
| Live WebSocket progress stream                                                    | LIVE DEMO |
| UX buffer on cache hits (1.5s simulated progress)                                 | LIVE DEMO |
| Verdict card: 5-color badge + confidence + top 3 sources                          | LIVE DEMO |
| Sub-claim breakdown (show if compound claim)                                      | LIVE DEMO |
| **Support/Contradict ratio bar**                                            | LIVE DEMO |
| Circuit breaker demo (graceful skip on dead API)                                  | LIVE DEMO |
| 5 pre-cached benchmark claims                                                     | LIVE DEMO |

### 3.2 Architecture Features — Shown in Slides

| Feature                                               | Shown As                  |
| ----------------------------------------------------- | ------------------------- |
| OCR + reverse image search                            | Architecture + code       |
| Multilingual (Hindi, Marathi, Tamil, Telugu)          | Architecture + screenshot |
| pgvector mutation detection + rumor evolution lineage | Architecture slide        |
| Full HTML report                                      | Screenshot                |
| Telemetry dashboard                                   | Architecture slide        |
| Evidence graph (node-edge SVG)                        | Screenshot                |
| Dynamic credibility scoring formula                   | Architecture slide        |
| Standalone verdict pipeline CLI                       | Code snippet              |
| Context-aware threshold table                         | Algorithm table           |
| User personalization (journalist vs general)          | Screenshot                |

### 3.3 Golden Rule

> The demo must never fail. Pre-load 5 benchmark claims. Test on venue internet. **LM Studio runs locally — no internet or API key required for the primary LLM path.** Rule-based is the final safety net.

### 3.4 Benchmark Claims (Pre-Cached)

| Claim                                 | Expected Verdict |
| ------------------------------------- | ---------------- |
| "Iran lost the war in 2026"           | FALSE            |
| "NASA confirmed alien life"           | UNVERIFIED       |
| "COVID vaccines contain microchips"   | FALSE            |
| "Artemis 1 mission launched in 2022" | TRUE             |
| "New virus outbreak started in India" | MISLEADING       |

---

## 4. Functional Requirements

### 4.1 Input Handling

| ID    | Requirement                                                                       |
| ----- | --------------------------------------------------------------------------------- |
| FR-01 | System SHALL accept free-text claim input up to 2000 characters                   |
| FR-02 | System SHALL accept image uploads — JPEG, PNG, WEBP, max 10MB                    |
| FR-03 | System SHALL accept a URL and extract the main article text                       |
| FR-04 | System SHALL support text selection via Chrome Extension right-click menu         |
| FR-05 | System SHALL auto-detect input language using langdetect                          |
| FR-06 | System SHALL translate non-English input to English before processing             |
| FR-07 | System SHALL process ALL claims internally in English only                        |
| FR-08 | System SHALL translate the final explanation back to the user's original language |
| FR-09 | System SHALL sanitize all inputs against injection attacks                        |

### 4.2 Claim Analysis

| ID    | Requirement                                                                           |
| ----- | ------------------------------------------------------------------------------------- |
| FR-10 | System SHALL extract named entities: persons, organizations, locations, dates         |
| FR-11 | System SHALL detect compound claims and split into atomic sub-claims                  |
| FR-12 | System SHALL extract the EVENT date from claim text — not the utterance/request date |
| FR-13 | System SHALL only fall back to current timestamp if no explicit event date is present |
| FR-14 | System SHALL generate 2–4 targeted search queries from extracted entities            |
| FR-15 | System SHALL detect semantically similar previously verified claims via pgvector hnsw |

### 4.3 Temporal Date Disambiguation

| ID    | Requirement                                                                        |
| ----- | ---------------------------------------------------------------------------------- |
| FR-16 | System SHALL distinguish between utterance date and event date                     |
| FR-17 | System SHALL prioritize explicitly stated historical dates over current timestamp  |
| FR-18 | Example: "Look at this 2011 tsunami photo" → event_date = 2011, NOT 2026          |
| FR-19 | Example: "A new outbreak started yesterday" → event_date = datetime.now() - 1 day |
| FR-20 | System SHALL use event_date for temporal mismatch comparison in image verification |

### 4.4 Data Acquisition

| ID    | Requirement                                                                        |
| ----- | ---------------------------------------------------------------------------------- |
| FR-21 | System SHALL query at least 2 search engines per claim in parallel                 |
| FR-22 | System SHALL query at least 1 news aggregator                                      |
| FR-23 | System SHALL check at least 1 fact-checking database                               |
| FR-24 | System SHALL query Wikipedia for entity background                                 |
| FR-25 | System SHALL deduplicate sources by URL MD5 hash                                   |
| FR-26 | System SHALL apply temporal filtering using event_date                             |
| FR-27 | System SHALL respect robots.txt for all scraped domains                            |
| FR-28 | System SHALL run all fetches in parallel via asyncio.gather() inside asyncio.run() |
| FR-29 | System SHALL cap evidence at top 5 articles × top 5 sentences per article         |

### 4.5 Celery + asyncio Integration

| ID    | Requirement                                                                  |
| ----- | ---------------------------------------------------------------------------- |
| FR-30 | All Celery task functions SHALL wrap async pipeline calls with asyncio.run() |
| FR-31 | System SHALL NOT use `await` directly inside a Celery task body            |
| FR-32 | asyncio.run() SHALL create a new event loop per task execution               |
| FR-33 | All async scraper functions SHALL remain fully async                         |

### 4.6 Early Exit

| ID    | Requirement                                                                        |
| ----- | ---------------------------------------------------------------------------------- |
| FR-34 | System SHALL trigger Early Exit when ≥ 2 Tier-1 sources AND support_ratio ≤ 0.20 |
| FR-35 | System SHALL trigger Early Exit when ≥ 2 Tier-1 sources AND support_ratio ≥ 0.80 |
| FR-36 | System SHALL log Early Exit trigger in algorithm_trace                             |
| FR-37 | System SHALL continue fetching if verdict remains borderline                       |

### 4.7 Circuit Breaker

| ID    | Requirement                                                                        |
| ----- | ---------------------------------------------------------------------------------- |
| FR-38 | System SHALL implement a circuit breaker for every external API                    |
| FR-39 | Circuit SHALL open after 3 consecutive timeouts or errors from the same source     |
| FR-40 | Open circuit SHALL skip that source instantly for 60 seconds                       |
| FR-41 | Circuit breaker state SHALL be stored in Redis — shared across all Celery workers |
| FR-42 | System SHALL log circuit breaker events in algorithm_trace                         |

### 4.8 OCR and Image Verification

| ID    | Requirement                                                                                 |
| ----- | ------------------------------------------------------------------------------------------- |
| FR-43 | System SHALL extract text from images using EasyOCR (primary) and Tesseract (fallback)      |
| FR-44 | System SHALL perform reverse image search via Google Vision API                             |
| FR-45 | System SHALL compare image's original publication date against the claim's EVENT date       |
| FR-46 | System SHALL flag CONTEXT_MISMATCH when image predates event_date by 30+ days → MISLEADING |

### 4.9 Evidence Extraction and Scoring

| ID      | Requirement                                                                                                                                            |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-47   | System SHALL run MiniLM on CPU to extract top 5 semantically relevant sentences per article                                                            |
| FR-48   | **System SHALL run BART-MNLI on GPU in batches of up to 25 sentences per call — NOT one sentence at a time**                                    |
| FR-49   | System SHALL run spaCy en_core_web_sm on CPU only                                                                                                      |
| FR-50   | System SHALL reserve GPU headroom for BART-MNLI; LM Studio GPU layer offload SHALL be configured externally and kept within the documented VRAM budget |
| FR-51   | System SHALL compute evidence_score = credibility × relevance × recency_factor                                                                       |
| FR-52-P | **System SHALL cache MiniLM embeddings per article URL hash in Redis (TTL 12h) — reuse on repeat articles**                                     |

### 4.10 Verdict Generation — Deterministic, Context-Aware Algorithm

| ID                | Requirement                                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------ |
| FR-52             | System SHALL compute support_ratio = supporting_weight ÷ (supporting_weight + contradicting_weight)                     |
| FR-53             | System SHALL include NEUTRAL evidence at 30% weight in total_weight                                                      |
| FR-54             | System SHALL classify TRUE when support_ratio ≥ T_TRUE AND ≥ T_TIER1 Tier-1 sources                                    |
| FR-55             | System SHALL classify FALSE when support_ratio ≤ T_FALSE AND ≥ T_TIER1 Tier-1 sources                                  |
| FR-56             | System SHALL classify CONFLICTING when support_ratio 0.40–0.60 AND tier1_count ≥ 2                                     |
| FR-57             | System SHALL classify MISLEADING when support_ratio in other mixed ranges OR temporal mismatch                           |
| FR-58             | System SHALL classify UNVERIFIED when fewer than 3 sources OR all Tier-4/5                                               |
| FR-59             | System SHALL reduce confidence by 20% when all evidence from same domain                                                 |
| FR-60             | System SHALL compute confidence using bounded sigmoid formula                                                            |
| FR-61             | System SHALL cap confidence at 0.99                                                                                      |
| **FR-61-A** | **System SHALL detect claim type (breaking_news / scientific / political / general) from claim text and entities** |
| **FR-61-B** | **For breaking_news claims: T_TRUE=0.70, T_FALSE=0.30, T_TIER1=2 (more uncertainty tolerated)**                          |
| **FR-61-C** | **For scientific claims: T_TRUE=0.75, T_FALSE=0.25, T_TIER1=3 (higher evidence bar required)**                           |
| **FR-61-D** | **Threshold values SHALL be logged in algorithm_trace.claim_type and algorithm_trace.threshold_used**              |

### 4.11 LLM Usage — Local-First, Explanation Only

| ID                | Requirement                                                                                                                                            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-62             | System SHALL use LLM ONLY for explanation — NOT for verdict                                                                                           |
| FR-63             | LLM SHALL receive: pre-computed verdict, top 5 evidence sentences, source names                                                                        |
| FR-64             | System SHALL set temperature=0.0 on ALL providers                                                                                                      |
| **FR-65**   | **System SHALL use LM Studio (local OpenAI-compatible server) as PRIMARY LLM — no API key or internet required for the local explanation path** |
| **FR-65-A** | **LLM fallback chain SHALL be: LM Studio (local) → Gemini Flash-Lite → Grok Fast Non-Reasoning → rule-based**                                 |
| **FR-65-B** | **System SHALL support OFFLINE_MODE=true: only LM Studio + free/local sources — zero cloud dependency**                                         |
| FR-66             | System SHALL cache LLM responses for 6 hours by prompt hash                                                                                            |

### 4.12 UX Cache Buffering

| ID    | Requirement                                                                                                        |
| ----- | ------------------------------------------------------------------------------------------------------------------ |
| FR-67 | System SHALL NOT return cached results instantly — users distrust instant answers                                 |
| FR-68 | On a cache hit, system SHALL stream simulated WebSocket progress events over 1.5–2.0 seconds                      |
| FR-69 | Simulated stages: "Parsing claim…", "Checking knowledge graph…", "Cross-referencing sources…", "Verdict ready." |
| FR-70 | Actual result data SHALL be sent at the end of the 1.5–2.0s buffer                                                |
| FR-71 | System SHALL include `"cached": true` in the JSON report                                                         |
| FR-72 | The UX buffer duration SHALL be configurable via UX_BUFFER_MS env var (default: 1800ms)                            |

### 4.13 Sub-Claim Breakdown UI

| ID    | Requirement                                                                                                   |
| ----- | ------------------------------------------------------------------------------------------------------------- |
| FR-73 | When is_compound=true, system SHALL include per-sub-claim verdicts in the report JSON                         |
| FR-74 | Chrome Extension popup SHALL render a sub-claim breakdown section below the main verdict                      |
| FR-75 | Each sub-claim SHALL display: short claim text + verdict badge + confidence                                   |
| FR-76 | Sub-claim breakdown SHALL use visual icons: ✅ TRUE, ❌ FALSE, ⚠️ MISLEADING, 🔀 CONFLICTING, ❓ UNVERIFIED |
| FR-77 | Web dashboard SHALL render the same sub-claim breakdown with full evidence links per sub-claim                |
| FR-78 | If is_compound=false, sub-claim section SHALL not render                                                      |

### 4.14 Explainability UI 2.0

| ID                | Requirement                                                                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **FR-79-A** | **System SHALL render a Support vs Contradict ratio bar for every verdict**                                                          |
| **FR-79-B** | **Format: `Support: ████████░░ (62%)` / `Contradict: ████░░░░░░ (38%)` — shown in extension and dashboard** |
| **FR-79-C** | **System SHALL render a source timeline: each source plotted by published_at date, colored by stance**                               |
| **FR-79-D** | **System SHALL render an evidence graph: nodes=sources, edges=claim overlap, colored by stance (green/red)**                               |
| **FR-79-E** | **Evidence graph SHALL be interactive SVG in dashboard; support bar SHALL appear in both extension and dashboard**                   |
| **FR-79-F** | **API response SHALL include `evidence_graph` (nodes + edges) and `support_bar` (support_pct, contradict_pct) keys**             |

### 4.15 Report Generation

| ID    | Requirement                                                                                                                                                                                                                              |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-79 | System SHALL return structured JSON: verdict, confidence, top_3_sources, explanation, algorithm_trace, sub_claims,**evidence_graph, support_bar**                                                                                  |
| FR-80 | Verdict card SHALL show: 5-color badge + confidence meter + top 3 sources + sub-claim breakdown if compound +**support/contradict bar**                                                                                            |
| FR-81 | Full HTML report SHALL be accessible via "View Full Report"                                                                                                                                                                              |
| FR-82 | System SHALL allow feedback: correct / incorrect / partial                                                                                                                                                                               |
| FR-83 | algorithm_trace SHALL include: support_ratio, tier1_count, early_exit, circuit_breakers_opened, temporal_mismatch, confidence_raw, confidence_final, cached,**claim_type, threshold_used, adversarial_signals, llm_provider_used** |

### 4.16 Chrome Extension

| ID                | Requirement                                                                           |
| ----------------- | ------------------------------------------------------------------------------------- |
| FR-84             | Extension SHALL add "Verify Claim" to right-click context menu                        |
| FR-85             | Extension SHALL stream live (or UX-buffered) WebSocket progress                       |
| FR-86             | Extension SHALL display 5-color verdict badges                                        |
| FR-87             | Extension SHALL render sub-claim breakdown section when is_compound=true              |
| FR-88             | Extension SHALL highlight misinformation inline on active webpage                     |
| FR-89             | Extension SHALL store last 20 verifications locally                                   |
| **FR-89-A** | **Extension SHALL render Support/Contradict ratio bar below the verdict badge** |

### 4.17 Caching and Telemetry

| ID    | Requirement                                                                                         |
| ----- | --------------------------------------------------------------------------------------------------- |
| FR-90 | System SHALL cache claim results 24h, search 1h, articles 12h, LLM 6h                               |
| FR-91 | System SHALL detect similar claims via pgvector (cosine > 0.85)                                     |
| FR-92 | System SHALL log BART-MNLI classifications to telemetry_nli table                                   |
| FR-93 | System SHALL expose /metrics endpoint: verdict distribution, cache hit rate, circuit breaker counts |

### 4.18 Dynamic Source Credibility

| ID               | Requirement                                                                                                      |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| **FR-94**  | **System SHALL maintain a dynamic credibility score per source domain in PostgreSQL**                      |
| **FR-95**  | **Dynamic score: `final = base + (feedback_adj × 0.3) + (consistency × 0.2)` — clamped [0.05, 1.00]** |
| **FR-96**  | **feedback_adjustment = (correct_count - incorrect_count) / max(total_feedback, 1) — rolling all-time**   |
| **FR-97**  | **consistency_score = stance_aligned_with_majority / total_reports_citing_source (rolling 30 days)**       |
| **FR-98**  | **Dynamic scores SHALL update asynchronously after feedback submission — not on critical path**           |
| **FR-99**  | **Dynamic scores SHALL NOT exceed Tier-1 max (1.00) or fall below Tier-5 min (0.05)**                      |
| **FR-100** | **System SHALL expose GET /credibility/{domain} returning base_score and dynamic_score**                   |

### 4.19 Rumor Evolution Tracking

| ID               | Requirement                                                                                                                |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **FR-101** | **System SHALL use pgvector cosine similarity to detect claims with similarity > 0.75 as mutation variants**         |
| **FR-102** | **Each claim record SHALL link to a mutation_chain_id grouping all variants of the same original claim**             |
| **FR-103** | **System SHALL store per mutation: original_claim_id, variant_text, similarity_score, first_seen_at, variant_count** |
| **FR-104** | **Web dashboard SHALL render a Rumor Evolution Timeline: original → variants sorted by first_seen_at**              |
| **FR-105** | **Example chain: "COVID vaccine has microchips" → "5G microchips in vaccine" → "Bill Gates tracking vaccine"**     |
| **FR-106** | **GET /mutation/{claim_id} SHALL return the full mutation chain**                                                    |
| **FR-107** | **Mutation chain SHALL be included in the full HTML report when variants exist**                                     |

### 4.20 User Personalization

| ID               | Requirement                                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------------------------- |
| **FR-108** | **System SHALL support user profiles: general / journalist / researcher**                                |
| **FR-109** | **General profile: simple 2-sentence explanation + verdict badge + support bar only**                    |
| **FR-110** | **Journalist profile: full explanation + evidence graph + all sources + algorithm trace summary**        |
| **FR-111** | **Researcher profile: raw JSON trace + mutation lineage + all telemetry + confidence formula breakdown** |
| **FR-112** | **Profile SHALL be stored in localStorage (extension) and user account (dashboard)**                     |
| **FR-113** | **Profile toggle SHALL be accessible in extension popup settings and dashboard settings panel**          |

### 4.21 Adversarial Robustness

| ID               | Requirement                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------- |
| **FR-114** | **System SHALL detect paraphrased variants of known false claims via pgvector (threshold > 0.70)**      |
| **FR-115** | **System SHALL flag coordinated source spam: same claim from >3 Tier-4/5 domains in <1h as suspicious** |
| **FR-116** | **System SHALL apply extra skepticism weight when Tier-4/5 sources form the majority of evidence**      |
| **FR-117** | **algorithm_trace SHALL include `adversarial_signals`: list of detected adversarial indicators**      |

### 4.22 Standalone Verdict Pipeline

| ID               | Requirement                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| **FR-118** | **System SHALL provide a `verdict_pipeline/` module importable without FastAPI or Celery**                   |
| **FR-119** | **Standalone pipeline SHALL accept: claim_text + pre-collected evidence list → return VerdictResult**         |
| **FR-120** | **Standalone pipeline SHALL support batch processing: list[claim_text] → list[VerdictResult]**                |
| **FR-121** | **Standalone pipeline SHALL include SQLite storage option for independent tracking — no PostgreSQL required** |
| **FR-122** | **Standalone pipeline SHALL work as CLI: `python -m verdict_pipeline verify "claim text"`**                  |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID                 | Requirement                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------------- |
| NFR-01             | Cold-start claim verification SHALL complete in ≤ 10 seconds (p90)                                     |
| NFR-02             | Cache hit UX buffer SHALL complete in 1.5–2.0 seconds                                                  |
| NFR-03             | System SHALL support 50 concurrent verification requests                                                |
| NFR-04             | Early Exit SHALL reduce processing time by 40–60% on strong claims                                     |
| NFR-05             | Circuit breaker SHALL eliminate full 5s timeout wait on dead sources                                    |
| **NFR-05-A** | **BART-MNLI batching SHALL reduce stance classification time by ≥ 50% vs single-sentence calls** |
| **NFR-05-B** | **Embedding cache SHALL achieve >60% hit rate after 24h warmup, eliminating re-encoding cost**    |

### 5.2 Reliability

| ID                 | Requirement                                                                                                 |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| NFR-06             | System SHALL degrade gracefully if any source is unavailable                                                |
| NFR-07             | System SHALL always return a verdict even with fewer sources                                                |
| NFR-08             | System SHALL target 99% uptime during demo period                                                           |
| **NFR-08-A** | **System SHALL operate fully offline using LM Studio + pre-cached claims when no internet available** |

### 5.3 Memory Management (GPU)

| ID     | Requirement                                                                       |
| ------ | --------------------------------------------------------------------------------- |
| NFR-09 | Total GPU VRAM SHALL not exceed 5.5GB (500MB headroom on RTX 4050)                |
| NFR-10 | spaCy en_core_web_sm SHALL run on CPU only                                        |
| NFR-11 | MiniLM SHALL run on CPU only                                                      |
| NFR-12 | BART-large-MNLI SHALL run on GPU (~1.6GB VRAM)                                    |
| NFR-13 | LM Studio GPU layer offload SHALL stay within the documented VRAM headroom budget |
| NFR-14 | All models SHALL be loaded once at startup — not per-request                     |

### 5.4 Celery Async Correctness

| ID                 | Requirement                                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| NFR-15             | No `await` SHALL appear directly in a Celery task body                                                         |
| NFR-16             | All async pipeline calls SHALL be wrapped with asyncio.run() at the Celery task boundary                         |
| NFR-17             | Celery workers SHALL use prefork or thread pool — NOT celery[gevent]                                            |
| **NFR-17-A** | **Post-hackathon: ARQ (native async Redis Queue) SHALL replace Celery — no asyncio.run() wrapper needed** |

### 5.5 Security

| ID                 | Requirement                                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| NFR-18             | All API keys SHALL be in .env, never in source code                                                              |
| NFR-19             | All inputs SHALL be sanitized against injection                                                                  |
| NFR-20             | API SHALL enforce 30 requests/minute per IP                                                                      |
| NFR-21             | User images SHALL be deleted within 60 seconds                                                                   |
| NFR-22             | HTTPS SHALL be enforced                                                                                          |
| **NFR-22-A** | **System SHALL operate with ZERO external API keys in local/offline mode (LM Studio + free data sources)** |

### 5.6 Usability

| ID                 | Requirement                                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ |
| NFR-23             | Extension SHALL require ≤ 3 clicks from selection to verdict                                                      |
| NFR-24             | UX buffer SHALL make cache hits feel fast but credible — not instant                                              |
| NFR-25             | Sub-claim breakdown SHALL be visually distinct but not overwhelming                                                |
| NFR-26             | CONFLICTING verdict SHALL include tooltip: "High-credibility sources disagree on this claim"                       |
| NFR-27             | All 5 verdict colors SHALL follow WCAG 2.1 contrast standards                                                      |
| **NFR-27-A** | **Support/Contradict bar SHALL use green fill for support, red fill for contradict, with percentage labels** |
| **NFR-27-B** | **Evidence graph SHALL render as interactive SVG — clicking a node shows the source card**                  |

### 5.7 Auditability

| ID                 | Requirement                                                                                           |
| ------------------ | ----------------------------------------------------------------------------------------------------- |
| NFR-28             | Every verdict SHALL be traceable to specific evidence scores                                          |
| NFR-29             | algorithm_trace SHALL be present in every report                                                      |
| NFR-30             | cached=true SHALL be visible in JSON when result came from cache                                      |
| **NFR-30-A** | **claim_type, threshold_used, and llm_provider_used SHALL be present in every algorithm_trace** |

---

## 6. External Interface Requirements

### 6.1 Software Interfaces

| System                                      | Purpose                                                                                                   | Cost                                |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| **LM Studio + Qwen3 4B 2507 (LOCAL)** | **PRIMARY LLM — explanation, temp=0.0 — local OpenAI-compatible server, no API key, no internet** | **Free after model download** |
| Gemini 3 Flash-preview                     | LLM fallback #1, temp=0.0                                                                                 | Provider pricing                    |
| `grok-4.20-reasoning`                     | LLM fallback #2, temp=0.0                                                                                 | Provider pricing                    |
| SerpAPI                                    | Web search                                                                                                | Free tier                           |
| NewsAPI                                     | News articles                                                                                             | Free — 100 req/day                 |
| Google Fact Check                           | Fact-check results                                                                                        | Free                                |
| Wikipedia API                               | Entity background                                                                                         | Free                                |
| Google Vision API                           | Reverse image search                                                                                      | Free tier                           |

### 6.2 Communication

- HTTPS for all client-server communication
- WebSocket (wss://) for live and UX-buffered progress streaming
- JSON as primary data interchange

---

## 7. System Constraints

- LLM used ONLY for explanation at temperature=0.0
- **LM Studio is the PRIMARY local LLM runtime — cloud LLMs are optional fallbacks, not requirements**
- Celery tasks MUST use asyncio.run() — no bare await in task bodies
- VRAM budget: BART-MNLI stays on GPU; LM Studio may offload only a bounded subset of layers and must leave headroom
- Evidence capped at 5 × 5 = 25 items per claim
- pgvector index MUST be hnsw — ivfflat degrades on empty tables
- Chrome Extension requires Manifest V3
- LM Studio GPU layer offload must stay within the documented VRAM headroom budget
- Event date extraction must prioritize explicit historical dates over utterance timestamp
- **BART-MNLI stance classification MUST be batched — all sentences in one call, not per-sentence**
- **Embedding cache MUST use article URL hash as key (not content hash) — faster lookup**
- **Standalone verdict pipeline MUST NOT import FastAPI, Celery, or Redis**

---

## 8. Use Cases

### UC-01: Verify Text Claim (Cold Start)

1. User highlights text → right-click → "Verify Claim"
2. WebSocket streams real progress: Parsing → Searching → Early Exit → Scoring → Explaining
3. Algorithm: support_ratio = 0.08, tier1 = 3 → FALSE, confidence 0.84
4. **LM Studio local LLM** at temperature=0.0 explains using only provided evidence — no API key used
5. Popup: RED FALSE badge + confidence bar + 3 source cards + **Support/Contradict bar (8% / 92%)**

### UC-02: Cache Hit with UX Buffer

1. Judge types a previously verified claim
2. Redis cache hit → result retrieved in 50ms
3. WebSocket streams simulated progress over 1.8 seconds — not instant
4. Popup shows verdict + `"cached": true` in JSON tab

### UC-03: Compound Claim Breakdown

1. User submits: "Iran lost the war and Russia surrendered"
2. Parsed as compound → 2 sub-claims: FALSE (0.87) + UNVERIFIED (0.0)
3. Aggregate → MISLEADING
4. Popup: MISLEADING badge + breakdown: ❌ Iran claim | ❓ Russia claim

### UC-04: Utterance vs Event Date

1. User submits: "Look at this incredible 2011 tsunami photo"
2. event_date = 2011 (explicit) → image from 2011 → NO temporal mismatch → NOT MISLEADING
3. Without fix: compare 2011 image to utterance_date 2026 → false MISLEADING

### UC-05: Circuit Breaker Live Demo

1. NewsAPI is down at venue → times out on first request
2. Second request: circuit open → skipped instantly
3. algorithm_trace: `"circuit_breakers_opened": ["newsapi"]`

### UC-06: CONFLICTING Verdict

1. Reuters (tier1) supports; BBC (tier1) contradicts → support_ratio = 0.51 → CONFLICTING
2. ORANGE badge + tooltip: "High-credibility sources disagree"

### UC-07: Rumor Evolution Tracking

1. "COVID vaccine has microchips" first seen 2021
2. "5G microchips in COVID vaccine" detected as variant (similarity=0.81) → linked to chain
3. "Bill Gates using vaccine to track people" linked (similarity=0.74)
4. Dashboard Rumor Timeline shows: original → variant1 → variant2 with timestamps
5. GET /mutation/{claim_id} returns full lineage

### UC-08: Offline Mode — No API Key, No Internet

1. OFFLINE_MODE=true, no internet connection
2. LM Studio local LLM handles explanation — no cloud calls
3. Pre-cached benchmark claims return immediately from Redis
4. Zero API keys required for the entire flow

### UC-09: Context-Aware Breaking News

1. "Massive earthquake just hit Tokyo" → claim_type = breaking_news
2. Thresholds applied: T_TRUE=0.70 (not 0.75)
3. support_ratio = 0.72 → TRUE (would be MISLEADING at default 0.75 threshold)
4. algorithm_trace: `"claim_type": "breaking_news", "threshold_used": {"TRUE": 0.70}`
5. Journalist profile user sees full evidence graph + source timeline

### UC-10: Standalone Pipeline — Batch Tracking

1. Researcher installs only `verdict_pipeline/` (no FastAPI, no Celery)
2. `python -m verdict_pipeline verify "Iran lost the war"` → JSON verdict to stdout
3. Batch mode: 1000 claims processed, results in local SQLite

---

## 9. Data Requirements

### 9.1 Core Output Schema (v5.0)

```json
{
  "report_id":   "uuid-v4",
  "verdict":     "FALSE",
  "confidence":  0.84,
  "explanation": "4 high-credibility sources contradict this claim...",
  "cached":      false,
  "sources": [
    {
      "name": "Reuters", "url": "https://...",
      "credibility_score":         0.97,
      "dynamic_credibility_score": 0.96,
      "stance": "CONTRADICTING",
      "published_at": "2024-03-12T14:00:00Z"
    }
  ],
  "support_bar": {
    "support_pct":   8,
    "contradict_pct": 92
  },
  "evidence_graph": {
    "nodes": [
      {"id": "reuters.com", "tier": 1, "stance": "CONTRADICTING", "score": 0.97},
      {"id": "bbc.com",     "tier": 1, "stance": "CONTRADICTING", "score": 0.95}
    ],
    "edges": [
      {"source": "reuters.com", "target": "bbc.com", "claim_overlap": 0.82}
    ]
  },
  "mutation_chain": {
    "chain_id":    "uuid-v4",
    "variant_count": 3,
    "similar_claims": [
      {"text": "COVID vaccines have tracking chips", "similarity": 0.88, "first_seen": "2021-01-15"}
    ]
  },
  "sub_claims": [
    {
      "text": "Iran lost the war in 2026",
      "verdict": "FALSE", "confidence": 0.87,
      "sources": ["Reuters", "BBC"]
    }
  ],
  "algorithm_trace": {
    "support_ratio":           0.08,
    "total_evidence_items":    12,
    "tier1_sources_found":     3,
    "early_exit_triggered":    true,
    "echo_chamber_penalty":    false,
    "temporal_mismatch":       false,
    "circuit_breakers_opened": [],
    "event_date_extracted":    "2024-03-10",
    "utterance_date":          "2026-04-06",
    "confidence_raw":          0.88,
    "confidence_final":        0.84,
    "claim_type":              "political",
    "threshold_used":          {"TRUE": 0.75, "FALSE": 0.25},
    "adversarial_signals":     [],
    "llm_provider_used":       "lm_studio"
  },
  "processing_time_ms": 4200
}
```

### 9.2 Source Credibility Tiers

| Tier | Base Score | Examples                              |
| ---- | ---------- | ------------------------------------- |
| 1    | 0.90–1.00 | Reuters, AP, BBC, WHO, UN, .gov, .int |
| 2    | 0.75–0.89 | NYT, Guardian, NDTV, Al Jazeera       |
| 3    | 0.55–0.74 | Wikipedia, major regional newspapers  |
| 4    | 0.30–0.54 | Blogs, unverified sites               |
| 5    | 0.00–0.29 | Known misinformation domains          |

Dynamic adjustment: `final = base + (feedback_adj × 0.3) + (consistency × 0.2)` — clamped to [0.05, 1.00].

---

## 10. Verdict Algorithm Specification

### 10.1 Evidence Score

```
evidence_score = credibility × relevance × recency_factor

recency_factor:
  < 24h  → 1.0
  < 7d   → 0.9
  < 30d  → 0.75
  < 1yr  → 0.5
  > 1yr  → 0.3
```

### 10.2 Weight Calculation

```
sup_w  = Σ evidence_score [stance = SUPPORTING]
con_w  = Σ evidence_score [stance = CONTRADICTING]
neu_w  = Σ evidence_score [stance = NEUTRAL]

total  = sup_w + con_w + (neu_w × 0.3)
ratio  = sup_w / (sup_w + con_w)
```

### 10.3 Context-Aware Verdict Table

| Condition                                     | Verdict     | Color  | Default Thresholds      | Breaking News | Scientific |
| --------------------------------------------- | ----------- | ------ | ----------------------- | ------------- | ---------- |
| ratio ≥ T_TRUE AND tier1 ≥ T_TIER1          | TRUE        | Green  | T_TRUE=0.75, T_TIER1=2  | T_TRUE=0.70   | T_TIER1=3  |
| ratio ≤ T_FALSE AND tier1 ≥ T_TIER1         | FALSE       | Red    | T_FALSE=0.25, T_TIER1=2 | T_FALSE=0.30  | T_TIER1=3  |
| ratio 0.40–0.60 AND tier1 ≥ 2               | CONFLICTING | Orange | —                      | —            | —         |
| ratio 0.26–0.74 (other) OR temporal_mismatch | MISLEADING  | Amber  | —                      | —            | —         |
| count < 3 OR all Tier-4/5                     | UNVERIFIED  | Gray   | —                      | —            | —         |

### 10.4 Confidence — Bounded Sigmoid

```python
n     = len(evidence)
scale = 1 - math.exp(-n / 10)
conf  = conf_raw * (0.7 + 0.3 * scale)
if echo_chamber: conf *= 0.80
return round(min(conf, 0.99), 2)
```

### 10.5 Temporal Date Rule

```
event_date = first explicitly stated historical date in claim text
           OR datetime.now() if no explicit historical date present

temporal_mismatch = (image_original_date < event_date - 30 days)
```

### 10.6 Dynamic Credibility Formula

```
dynamic_score = base_score
              + (feedback_adjustment × 0.3)
              + (consistency_score × 0.2)

feedback_adjustment = (correct_count - incorrect_count) / max(total_feedback, 1)
                    # ∈ [-1, +1]

consistency_score   = stance_aligned_with_majority_count /
                      max(total_reports_citing_source_30d, 1)
                    # ∈ [0, 1]

dynamic_score = clamp(dynamic_score, 0.05, 1.00)
```

---

## 11. Demo Impact Requirements (v5.1)

### 11.1 Killer Screen Layout

> Judges don't read SRS. They feel the product. The result screen must communicate verdict in under 3 seconds.

The primary result view — in both the Chrome Extension popup and web dashboard — SHALL follow this exact layout priority order:

```
┌───────────────────────────────────────┐
│  [ FALSE ❌ ]     Confidence: 84%     │  ← verdict badge + confidence (always top)
│                                       │
│  Support vs Contradict:               │  ← support bar (always visible)
│  ████░░░░░░░░░  8%  Support           │
│  █████████████  92% Contradict        │
│                                       │
│  "Widely debunked by credible sources"│  ← verdict reason tag (1 line, human)
│                                       │
│  Top Insight:                         │  ← single strongest evidence line
│  "3 Tier-1 sources (Reuters, BBC,     │
│   AP) contradict this claim"          │
│                                       │
│  ⚠️ Part of spreading pattern (3 var.) │  ← mutation alert (if chain exists)
│                                       │
│  [ View Evidence Graph ]              │
│  [ View Source Timeline ]             │
└───────────────────────────────────────┘
```

| ID               | Requirement                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **FR-123** | **Verdict badge + confidence SHALL be the topmost element — always visible without scrolling**                     |
| **FR-124** | **Support/Contradict bar SHALL appear immediately below the badge on every result — no toggle or expand required** |
| **FR-125** | **Verdict Reason Tag SHALL appear as a single human-readable sentence below the bar**                               |
| **FR-126** | **Top Insight SHALL show a single generated sentence summarising the strongest evidence**                           |
| **FR-127** | **If mutation_chain exists, a compact mutation alert SHALL appear inline (not in a separate tab)**                  |
| **FR-128** | **"View Evidence Graph" and "View Source Timeline" SHALL be secondary CTAs — not primary content**                 |

### 11.2 Verdict Reason Tags

One-line psychological summaries that tell a non-technical user **why** the verdict was reached, without requiring them to understand the algorithm.

| Verdict     | Trigger Condition                    | Reason Tag                                       |
| ----------- | ------------------------------------ | ------------------------------------------------ |
| FALSE       | tier1 ≥ 2, ratio ≤ 0.25            | "Widely debunked by credible sources"            |
| FALSE       | all contradicting sources are Tier-1 | "Fact-checked and refuted by major news outlets" |
| TRUE        | tier1 ≥ 2, ratio ≥ 0.75            | "Confirmed by multiple credible sources"         |
| TRUE        | single Tier-1 + early_exit           | "Verified by a major news outlet"                |
| MISLEADING  | temporal_mismatch=true               | "Old content reused in a new context"            |
| MISLEADING  | echo_chamber=true                    | "Only reported by a single source"               |
| MISLEADING  | low-cred majority                    | "Primarily from unreliable sources"              |
| CONFLICTING | tier1 ≥ 2, ratio 0.40–0.60         | "Experts and credible outlets disagree"          |
| UNVERIFIED  | count < 3                            | "Not enough evidence found to decide"            |
| UNVERIFIED  | all Tier-4/5                         | "No reliable sources cover this claim"           |

| ID               | Requirement                                                                                                                      |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **FR-129** | **System SHALL generate a Verdict Reason Tag for every report using the table above**                                      |
| **FR-130** | **Reason tag selection SHALL be deterministic — based on algorithm_trace fields, not LLM**                                |
| **FR-131** | **Reason tag SHALL be included in API response as `verdict_reason_tag` string field**                                    |
| **FR-132** | **Reason tag SHALL be shown in extension popup and dashboard — same font size as explanation, above the LLM explanation** |

### 11.3 Mutation as Headline Feature

The Rumor Evolution Tracker SHALL be surfaced as a first-class alert, not buried as an extra tab.

```
If mutation_chain.variant_count >= 2:

  ┌─────────────────────────────────────────────┐
  │ ⚠️ MISINFORMATION PATTERN DETECTED          │
  │ This claim is part of a spreading pattern   │
  │ with 3 known variants since 2021.           │
  │                                             │
  │  2021 ── "COVID vaccine has microchips"     │
  │  2022 ── "5G microchips in vaccine"         │
  │  2026 ── [this claim] ← you are here        │
  │                                             │
  │  [ View Full Evolution Timeline ]           │
  └─────────────────────────────────────────────┘
```

| ID               | Requirement                                                                                                                         |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **FR-133** | **When mutation_chain.variant_count ≥ 2, system SHALL display a "Misinformation Pattern" alert INLINE on the result screen** |
| **FR-134** | **Alert SHALL show: original claim year, number of variants, and the current claim marked as "you are here"**                 |
| **FR-135** | **Alert SHALL appear between the verdict card and the evidence section — not in a separate tab**                             |
| **FR-136** | **Alert title SHALL use language like "Spreading Pattern Detected" — not "Mutation Chain"**                                  |
| **FR-137** | **"View Full Evolution Timeline" SHALL link to the /report/{id} full page mutation section**                                  |

### 11.4 Dynamic Credibility Shift Display

Users must be able to **feel** that the system learns. Each source card SHALL show the credibility shift.

```
Source Cards (in result):

  Reuters          ████████████ 0.97  Tier 1
  NDTV      0.78 → 0.82 ↑  (improved reliability based on past feedback)
  RandomBlog 0.32 → 0.21 ↓  (lower trust — past reports were inaccurate)
```

| ID               | Requirement                                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **FR-138** | **Each source card SHALL show both base_score and dynamic_score when they differ by ≥ 0.03**                      |
| **FR-139** | **Score change SHALL display as: `0.78 → 0.82 ↑` or `0.32 → 0.21 ↓`**                                      |
| **FR-140** | **A short tooltip SHALL explain the shift: "Improved based on user feedback" or "Accuracy declined over 30 days"** |
| **FR-141** | **When dynamic_score equals base_score (no feedback yet), display only the base score — no delta shown**          |
| **FR-142** | **The credibility shift indicator SHALL be subtle — secondary typography, not primary content**                   |

---

## 12. Edge-Case & Hardening Requirements (v5.2)

### 12.1 Local LLM Latency Budget

**Problem:** Llama 3.1 8B on a CPU generates ~5–10 tokens/sec. A 100-word explanation = ~130 tokens = up to 26 seconds — directly violating NFR-01 (≤10s cold-start).

**Solution set (all three applied together):**

| ID               | Requirement                                                                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-143** | **The local LLM model SHALL be Qwen3 4B 2507 or Llama 3.2 3B — NOT Llama 3.1 8B**                                                                        |
| **FR-144** | **All LM Studio API calls SHALL enforce `max_tokens=120` — physically caps generation time regardless of model speed**                                 |
| **FR-145** | **LLM explanation SHALL be streamed token-by-token to the WebSocket — the NFR-01 10s budget applies to Time to First Token (TTFT), not full completion** |
| **FR-146** | **The explanation streaming stage SHALL begin emitting to the client as soon as the first token arrives — before generation is complete**                |
| **FR-147** | **If TTFT exceeds 5 seconds on LM Studio, system SHALL immediately fall back to Gemini Flash-Lite without waiting for full LM Studio completion**         |

Streaming WebSocket event for explanation:

```json
{ "stage": "explaining", "progress": 87,
  "explanation_chunk": "4 Tier-1 sources, including Reuters" }
{ "stage": "explaining", "progress": 91,
  "explanation_chunk": " and BBC, directly contradict this claim." }
{ "stage": "complete", "progress": 100, "verdict": "FALSE" }
```

### 12.2 Echo Chamber — Syndication Loophole Fix

**Problem:** FR-59 checks for distinct domains, but syndicated wire copy (Reuters → Yahoo News, MSN, 40 local papers) appears as many domains with near-identical content — falsely inflating confidence.

**Fix:** Trigger echo chamber penalty on **content similarity**, not just domain count.

| ID               | Requirement                                                                                                                                                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-148** | **After evidence extraction, system SHALL compute pairwise cosine similarity between all extracted evidence sentences using the cached MiniLM embeddings**        |
| **FR-149** | **If the mean pairwise cosine similarity of the top-5 evidence sentences exceeds 0.90, the echo chamber flag SHALL be set to true — regardless of domain count** |
| **FR-150** | **algorithm_trace SHALL include `echo_chamber_reason`: `"single_domain"` or `"syndicated_content"` or `null`**                                            |
| **FR-151** | **Syndication detection SHALL reuse the embedding cache (TTL 12h) — no additional encoding cost**                                                                |

Detection rule:

```
syndication_score = mean(cosine_sim(sent_i, sent_j) for all pairs i≠j in top_5)
if syndication_score > 0.90:
    echo_chamber = True
    echo_chamber_reason = "syndicated_content"
```

### 12.3 Dynamic Credibility — Sybil Attack Protection

**Problem:** An unauthenticated `POST /feedback` endpoint lets anyone spam ratings to tank Tier-1 sources or elevate Tier-5 sources before a demo.

| ID               | Requirement                                                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-152** | **POST /feedback SHALL enforce IP-based rate limiting: max 5 feedback submissions per IP per hour**                                                |
| **FR-153** | **Credibility adjustment from feedback SHALL be weighted by user trust level: anonymous=0.2×, authenticated=1.0×**                                     |
| **FR-154** | **A single IP address SHALL never cause more than ±0.05 total shift in any source's dynamic_score**                                               |
| **FR-155** | **feedback_adjustment recalculation SHALL exclude submissions flagged as rate-limited spam**                                                       |
| **FR-156** | **For hackathon demo: a `FREEZE_CREDIBILITY=true` env flag SHALL disable all dynamic score updates, locking scores to their seeded base values** |

> **Hackathon fast path:** Set `FREEZE_CREDIBILITY=true` in `.env` for the demo. Dynamic scoring still runs in code — just writes are blocked. Scores stay clean for the presentation.

### 12.4 Celery asyncio.gather() Runaway Timeout

**Problem:** If one scraper's TCP connection hangs indefinitely inside `asyncio.gather()`, it can lock a Celery worker thread permanently — no result, no error, just silence.

| ID                 | Requirement                                                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| **NFR-18-A** | **Every `asyncio.gather()` call inside the pipeline SHALL be wrapped with `asyncio.wait_for(gather(...), timeout=15.0)`** |
| **NFR-18-B** | **Individual scraper calls SHALL have a per-request timeout of 5 seconds via `httpx.AsyncClient(timeout=5.0)`**             |
| **NFR-18-C** | **A timed-out gather SHALL return partial results — not raise an exception that kills the pipeline**                         |
| **NFR-18-D** | **algorithm_trace SHALL include `gather_timeout_triggered: bool`**                                                          |

Implementation pattern:

```python
try:
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=15.0
    )
except asyncio.TimeoutError:
    results = []   # proceed with zero evidence → UNVERIFIED
    trace["gather_timeout_triggered"] = True
```

### 12.5 UNVERIFIED — Null-State UI Specification

**Problem:** When verdict is `UNVERIFIED` with zero evidence, the Support/Contradict bar renders as `0% / 0%` — a broken-looking empty bar that confuses judges.

| ID               | Requirement                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-157** | **When verdict is UNVERIFIED AND total_evidence_items = 0, the Support/Contradict bar SHALL NOT render**                                                                |
| **FR-158** | **In its place, system SHALL render an empty-state placeholder: a dashed gray outline with centred text "No evidence collected"**                                       |
| **FR-159** | **The Verdict Reason Tag for this state SHALL be: "Awaiting credible coverage"**                                                                                        |
| **FR-160** | **When verdict is UNVERIFIED AND total_evidence_items > 0 (some sources found, all Tier-4/5), the bar SHALL render normally using the actual support/contradict split** |

Empty-state bar spec:

```
┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
      No evidence collected yet
└─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

### 12.6 LM Studio as Primary Local Runtime

LM Studio provides an OpenAI-compatible local server on `http://localhost:1234/v1`. It is the preferred local LLM runtime for this system, with GPU layer offloading configured in the LM Studio UI rather than application code.

| ID               | Requirement                                                                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **FR-161** | **The LLM provider abstraction SHALL use LM Studio via a standard OpenAI-compatible client — only `base_url` and `model` name are deployment-specific** |
| **FR-162** | **`LM_STUDIO_BASE_URL` and `LM_STUDIO_MODEL` env vars SHALL define the primary local LLM runtime**                                                       |
| **FR-163** | **When LM Studio is active, VRAM layer offload SHALL be configured in LM Studio UI, not in application code**                                                |

```python
class LMStudioProvider:
    """Primary local LLM runtime via LM Studio's OpenAI-compatible server."""
    async def generate(self, prompt: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            base_url=settings.lm_studio_base_url,   # http://localhost:1234/v1
            api_key="lm-studio"
        )
        r = await client.chat.completions.create(
            model=settings.lm_studio_model,          # e.g. "qwen3-4b-2507"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=120,                           # enforce latency cap
        )
        return r.choices[0].message.content
```

### 12.7 Platform Constraint — WSL 2 Required (Not VirtualBox)

**Problem:** VirtualBox on Windows does not support PCIe passthrough for consumer GPUs. Running the backend inside VirtualBox means BART-MNLI is forced to CPU — pipeline cold-start becomes 60+ seconds.

| ID              | Requirement / Constraint                                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **SC-01** | **The backend MUST NOT be run inside VirtualBox when GPU acceleration is required**                                          |
| **SC-02** | **On Windows development machines, WSL 2 (Ubuntu 22.04) is the required Linux environment**                                  |
| **SC-03** | **CUDA drivers SHALL be installed on the Windows host — WSL 2 exposes the host GPU natively via NVIDIA's WSL driver stack** |
| **SC-04** | **Docker Desktop on Windows SHALL use the WSL 2 backend — not Hyper-V — for GPU container access**                         |
| **SC-05** | **LM Studio SHALL run natively on Windows and be accessed from the WSL 2 backend via `host.docker.internal:1234`**         |

---

## 13. Glossary

| Term                    | Definition                                                                                                                                |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Killer Screen           | The single result view optimised for 3-second judge comprehension — badge, bar, tag, insight, mutation alert                             |
| Verdict Reason Tag      | A deterministic 1-line human-readable summary of WHY a verdict was reached (e.g. "Widely debunked")                                       |
| Top Insight             | A single auto-generated sentence summarising the strongest evidence item                                                                  |
| Mutation Alert          | Inline warning shown when a claim belongs to a known misinformation spread chain                                                          |
| TTFT                    | Time to First Token — the latency to first streamed token; NFR-01 applies to TTFT, not full completion                                   |
| Syndicated Content      | Wire copy republished identically across many domains — detected via high pairwise MiniLM embedding similarity (>0.90), not domain count |
| Sybil Attack            | Abuse of the feedback endpoint to spam ratings and corrupt dynamic credibility scores                                                     |
| FREEZE_CREDIBILITY      | Env flag that disables dynamic score writes — locks scores to base values for demo safety                                                |
| LM Studio               | GUI desktop app with OpenAI-compatible local LLM server — the primary local runtime in this design                                       |
| WSL 2                   | Windows Subsystem for Linux v2 — exposes host GPU natively to Linux; required on Windows for GPU acceleration                            |
| Gather Timeout          | asyncio.wait_for() deadline on asyncio.gather() — prevents runaway scrapers from locking Celery workers                                  |
| Credibility Shift       | The visual delta between base_score and dynamic_score shown on source cards                                                               |
| asyncio.run()           | Creates a new event loop — required wrapper for async code inside Celery tasks                                                           |
| ARQ                     | Async Redis Queue — native-async Celery replacement, planned post-hackathon                                                              |
| Adversarial Claim       | A paraphrased or mutated false claim designed to evade detection                                                                          |
| CONFLICTING             | Divided evidence between ≥ 2 Tier-1 sources — NOT deceptive framing                                                                     |
| Circuit Breaker         | Skips failed API source after 3 failures, resets after 60s                                                                                |
| Claim Type              | Inferred category: breaking_news / scientific / political / general — affects thresholds                                                 |
| Context-Aware Threshold | Verdict decision boundary that adjusts based on claim type                                                                                |
| Dynamic Credibility     | Source credibility score that updates from feedback and accuracy history                                                                  |
| Early Exit              | Stop fetching when verdict is strongly determined                                                                                         |
| Echo Chamber            | All evidence from same domain → 20% confidence penalty                                                                                   |
| Evidence Graph          | Visual node-edge diagram of sources and their stance relationships                                                                        |
| Event Date              | The date the claim's subject occurred — extracted from claim text                                                                        |
| hnsw                    | Hierarchical Navigable Small World — pgvector index that builds dynamically                                                              |
| MISLEADING              | Temporal mismatch, low-credibility noise, or deceptive framing                                                                            |
| Mutation Chain          | Group of semantically similar claims sharing a common ancestor                                                                            |
| OOM                     | Out-of-Memory — GPU VRAM exhaustion                                                                                                      |
| Ollama                  | Legacy local LLM server referenced by earlier revisions; not the recommended v5.2 deployment path                                         |
| Rumor Evolution         | The tracked lineage of mutations a claim undergoes as it spreads                                                                          |
| Standalone Pipeline     | verdict_pipeline/ importable module without FastAPI/Celery/Redis                                                                          |
| Support Bar             | Visual bar showing support_pct vs contradict_pct split                                                                                    |
| Support Ratio           | supporting_weight ÷ (supporting_weight + contradicting_weight)                                                                           |
| UX Buffering            | 1.5–2.0s simulated progress on cache hits — prevents instant-answer distrust                                                            |
| Utterance Date          | When the claim was written/shared — NOT what temporal parsing should use                                                                 |
| User Profile            | Stored preference: general / journalist / researcher — controls explanation depth                                                        |
| Verdict                 | TRUE / FALSE / CONFLICTING / MISLEADING / UNVERIFIED — by algorithm, NOT LLM                                                             |

---

*SRS v5.2.0 — OSINT Rumor Verification Platform — Radio Frequency — VIT Code Apex 2.0*
