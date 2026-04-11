"""
backend/main.py  —  OSINT Engine — FastAPI entry point (v5.2)
==============================================================

Routes:
  POST  /v1/verify            → enqueue Celery task, return {job_id}
  GET   /v1/status/{job_id}   → poll job result
  WS    /ws/{job_id}          → real-time stage streaming
  GET   /v1/metrics           → system-wide stats
  GET   /v1/history           → last 30 verifications from DB

Compatibility shim (React frontend / no Celery):
  POST  /verify               → synchronous pipeline, returns result directly
  GET   /history              → last 30 from DB (or in-memory fallback)
  DELETE /history/clear
  GET   /health
  OPTIONS *                   → CORS preflight handled automatically by middleware
"""

import asyncio
import datetime
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP / SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: pre-load BART-MNLI, SentenceTransformer, DB pool, Redis pool.
    Shutdown: gracefully close connections.
    All startup failures are non-fatal — the server continues without that service.
    """
    print("\n" + "=" * 65)
    print("  OSINT Engine v5.2  -  Starting up")
    print("=" * 65)

    # 1. Database (Docker Postgres)
    try:
        from db.database import get_pool, create_all_tables, seed_credibility_data
        await get_pool()
        await create_all_tables()
        await seed_credibility_data()
        print("[Startup] [OK] PostgreSQL pool ready + tables verified")
    except Exception as e:
        print(f"[Startup] [WARN] PostgreSQL unavailable: {e}")
        print("[Startup]        Run: docker compose up -d   (from project root)")

    # 2. Redis
    try:
        from cache.redis_client import redis_ping
        ok = await redis_ping()
        if ok:
            print("[Startup] [OK] Redis ready")
        else:
            print("[Startup] [WARN] Redis unavailable - caching disabled")
    except Exception as e:
        print(f"[Startup] [WARN] Redis error: {e}")

    # 3. BART-MNLI (warm up in background thread — slow, don't crash if missing)
    try:
        from pipeline.stance import warmup
        import asyncio
        await asyncio.to_thread(warmup)
        print("[Startup] [OK] BART-MNLI warm-up complete")
    except Exception as e:
        print(f"[Startup] [WARN] BART-MNLI warm-up skipped: {e}")

    # 4. SentenceTransformer
    try:
        from pipeline.embedder import embed
        await asyncio.to_thread(embed, "warmup")
        print("[Startup] [OK] SentenceTransformer (MiniLM) ready")
    except Exception as e:
        print(f"[Startup] [WARN] SentenceTransformer skipped: {e}")

    print("=" * 65 + "\n")
    yield

    # Shutdown
    try:
        from db.database import close_pool
        await close_pool()
    except Exception:
        pass
    try:
        from cache.redis_client import close_redis
        await close_redis()
    except Exception:
        pass
    print("[Shutdown] OSINT Engine shut down cleanly.")


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OSINT Engine — API",
    description="Multimodal claim verification platform (OSINT + AI)",
    version="5.2.0",
    lifespan=lifespan,
)

# ── FIX 1: CORS — explicit origins covering all dev/prod scenarios ────────────
# allow_origins=["*"] conflicts with allow_credentials=True in some browsers.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # React dev server (default CRA port)
        "http://localhost:3001",       # alternate React port
        "http://localhost:5173",       # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://localhost:8080",       # serve / nginx dev
        "http://127.0.0.1:8080",
        "null",                        # file:// origin (index.html opened directly)
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,           # FIX: must be False when allow_origins includes "*"-style
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# ── FIX 2: Global OPTIONS handler — catches any preflight the middleware misses
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str, request: Request):
    """
    Explicit OPTIONS handler.  The CORSMiddleware should handle this, but
    some reverse-proxy / uvicorn configurations swallow preflight requests
    before they reach the middleware.  This is a belt-and-suspenders fix.
    """
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
            "Access-Control-Max-Age": "600",
        },
    )

# Serve the React frontend build at /  (optional — frontend runs dev server)
try:
    from fastapi.staticfiles import StaticFiles
    import os
    dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")
    if os.path.isdir(dist_path):
        app.mount("/static", StaticFiles(directory=dist_path), name="static")
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    claim: str = ""
    input_type: str = "text"          # text | url | image
    claim_type: str = "general"       # hint from UI type-selector
    image_url: Optional[str] = None
    image_base64: Optional[str] = None


class AsyncVerifyResponse(BaseModel):
    job_id: str
    status: str = "queued"
    websocket_url: str
    poll_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc or url
        return host.replace("www.", "").lower()
    except Exception:
        return url.lower()


_LABEL_TO_FLOAT = {"HIGH": 0.90, "MEDIUM": 0.65, "LOW": 0.35}

_BREAKING_KW = re.compile(r"\b(breaks?|breaking|just in|alert|urgent|developing)\b", re.I)
_SCIENTIFIC_KW = re.compile(r"\b(study|research|scientist|vaccine|virus|data|trial|experiment)\b", re.I)
_POLITICAL_KW = re.compile(r"\b(government|president|minister|election|parliament|senate|congress)\b", re.I)


def _detect_claim_type(claim: str, hint: str = "general") -> str:
    if hint and hint not in ("general", "auto"):
        return hint
    if _BREAKING_KW.search(claim):
        return "breaking_news"
    if _SCIENTIFIC_KW.search(claim):
        return "scientific"
    if _POLITICAL_KW.search(claim):
        return "political"
    return "general"


def _tier(cred_float: float) -> int:
    if cred_float >= 0.85:
        return 1
    if cred_float >= 0.55:
        return 2
    if cred_float >= 0.35:
        return 3
    return 4


def _format_for_ui(raw: dict, claim: str, claim_type_hint: str = "general") -> dict:
    """
    Normalise a raw pipeline result dict into the shape the React frontend expects.
    Merges new pipeline schema with old schema for backward compat.
    """
    verdict = raw.get("verdict", "UNVERIFIED")
    confidence = raw.get("confidence", 0.0)
    explanation = raw.get("explanation", "")
    support_ratio = raw.get("support_ratio", 0.5)
    evidence_count = raw.get("evidence_count", 0)
    is_compound = raw.get("is_compound", False)
    cached = raw.get("cached", False)
    proc_ms = raw.get("processing_ms", raw.get("processing_time_ms", 0))
    algo_trace = raw.get("algorithm_trace", {})
    llm_provider = raw.get("llm_provider", algo_trace.get("llm_provider_used", "local_llm"))

    # ── Sources ───────────────────────────────────────────────────────────────
    ui_sources = []
    for s in raw.get("sources", []):
        cred_raw = s.get("credibility_score", s.get("credibility", 0.65))
        # Handle string labels from old format
        if isinstance(cred_raw, str):
            cred_float = _LABEL_TO_FLOAT.get(cred_raw.upper(), 0.65)
        else:
            cred_float = float(cred_raw)

        ui_sources.append({
            "name": s.get("source", s.get("name", s.get("title", "Unknown")))[:40],
            "domain": _domain(s.get("url", "")),
            "tier": _tier(cred_float),
            "credibility": round(cred_float, 3),
            "stance": s.get("stance", "NEUTRAL"),
            "date": "recent",
            "shift": 0,
            "url": s.get("url", ""),
        })

    # ── Support bar ───────────────────────────────────────────────────────────
    support_pct = round(support_ratio * 100)
    support_bar = {"support_pct": support_pct, "contradict_pct": 100 - support_pct}

    # ── Claim type ────────────────────────────────────────────────────────────
    claim_type = raw.get("claim_type") or _detect_claim_type(claim, claim_type_hint)

    # ── Verdict tags ──────────────────────────────────────────────────────────
    verdict_tags = _build_verdict_tags(verdict, algo_trace, is_compound, evidence_count)

    # ── Evidence graph ────────────────────────────────────────────────────────
    evidence_graph = _build_evidence_graph(ui_sources)

    # ── UI trace ──────────────────────────────────────────────────────────────
    ui_trace = {
        "support_ratio": round(support_ratio, 3),
        "total_evidence_items": evidence_count,
        "tier1_sources_found": algo_trace.get("tier1_count", 0),
        "early_exit_triggered": algo_trace.get("early_exit", False),
        "early_exit_reason": algo_trace.get("early_exit_reason", ""),
        "event_date": "unknown",
        "utterance_date": datetime.date.today().isoformat(),
        "confidence_raw": round(confidence, 3),
        "confidence_final": round(confidence, 3),
        "claim_type": claim_type,
        "supporting_count": algo_trace.get("supporting_count", 0),
        "contradicting_count": algo_trace.get("contradicting_count", 0),
        "neutral_count": algo_trace.get("neutral_count", 0),
        "avg_credibility": algo_trace.get("avg_credibility", 0),
        "agreement": algo_trace.get("agreement", 0),
        "llm_provider_used": llm_provider,
        # FIX 3: include threshold fields the frontend trace tab expects
        "threshold_TRUE": algo_trace.get("threshold_TRUE", 0.75),
        "threshold_FALSE": algo_trace.get("threshold_FALSE", 0.25),
        "temporal_mismatch": algo_trace.get("temporal_mismatch", False),
        "echo_chamber_penalty": algo_trace.get("echo_chamber_penalty", False),
    }

    return {
        # Core
        "verdict": verdict,
        "localized_verdict": raw.get("localized_verdict"),
        "confidence": confidence,
        "explanation": explanation,
        "llm_provider": llm_provider,
        "claim_type": claim_type,
        # FIX 4: include claim_text so the frontend can display it in the
        # verdict card without needing to pass it separately
        "claim_text": claim,
        # Timing
        "processing_ms": proc_ms,
        "cached": cached,
        # Evidence
        "support_ratio": round(support_ratio, 3),
        "evidence_count": evidence_count,
        "support_bar": support_bar,
        # Decoration
        "verdict_tags": verdict_tags,
        "is_compound": is_compound,
        "is_mutation": raw.get("is_mutation", False),
        "adversarial": False,
        "adversarial_signal": "",
        # Detail
        "sources": ui_sources,
        "sub_claims": raw.get("sub_claims", []),
        "trace": ui_trace,
        "evidence_graph": evidence_graph,
        "mutation_chain": raw.get("mutation_chain", []),
        "algorithm_trace": algo_trace,
    }


def _build_verdict_tags(
    verdict: str,
    trace: dict,
    is_compound: bool,
    evidence_count: int,
) -> List[str]:
    tags: List[str] = []
    tier1 = trace.get("tier1_count", 0)
    agree = trace.get("agreement", 0)

    if tier1 >= 3:
        tags.append(f"{tier1} Tier-1 sources")
    elif tier1 >= 1:
        tags.append(f"{tier1} Tier-1 source{'s' if tier1 > 1 else ''}")

    if agree >= 0.7:
        tags.append("High agreement")
    elif agree < 0.3 and evidence_count >= 2:
        tags.append("Split evidence")

    if evidence_count >= 10:
        tags.append("Strong evidence base")
    elif evidence_count == 0:
        tags.append("Insufficient sources")

    if is_compound:
        tags.append("Compound claim")

    if verdict == "MISLEADING":
        tags.append("Context missing")
    elif verdict == "CONFLICTING":
        tags.append("Genuine disagreement")
    elif verdict == "UNVERIFIED":
        tags.append("Check back later")
    elif verdict == "FALSE":
        tags.append("Widely contradicted")
    elif verdict == "TRUE":
        tags.append("Well supported")

    return tags[:5]


def _build_evidence_graph(sources: List[dict]) -> Dict[str, Any]:
    nodes = [
        {
            "id": s.get("domain", "unknown"),
            "tier": s.get("tier", 3),
            "stance": s.get("stance", "NEUTRAL"),
            "score": round(s.get("credibility", 0.5), 2),
        }
        for s in sources
    ]
    edges = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            if a["stance"] == b["stance"]:
                overlap = round((a["score"] + b["score"]) / 2 * 0.85, 2)
                edges.append({
                    "source": a["id"],
                    "target": b["id"],
                    "claim_overlap": overlap,
                })
    return {"nodes": nodes, "edges": edges}


async def _extract_claim_from_request(body: VerifyRequest) -> str:
    """
    Handle text, URL, or image claim extraction.
    """
    claim = body.claim.strip()

    # URL input: extract text from URL
    if body.input_type == "url" and not claim:
        raise HTTPException(status_code=400, detail="URL input_type requires a claim URL.")

    # Image input
    if body.image_url or body.image_base64:
        from image_engine import extract_claim_from_image
        import base64
        import httpx as _httpx

        image_bytes = None
        if body.image_base64:
            b64 = body.image_base64
            if "," in b64:
                b64 = b64.split(",")[1]
            image_bytes = base64.b64decode(b64)
        elif body.image_url:
            async with _httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(body.image_url)
                if resp.status_code == 200:
                    image_bytes = resp.content

        if image_bytes:
            claim = await asyncio.to_thread(extract_claim_from_image, image_bytes)

    return claim


async def _sync_pipeline(claim: str, claim_type: str) -> dict:
    """
    Run the full verification pipeline synchronously (for /verify compat shim).
    No Celery, no WebSocket — just run and return.
    """
    import time as _time
    from pipeline.claim_parser import parse_claim
    from pipeline.embedder import embed, rank_evidence, embedding_to_list
    from pipeline.stance import classify_stance_bulk
    from pipeline.aggregator import aggregate
    from pipeline.verdict import compute_verdict
    from sources.collector import collect_all_evidence
    from services.llm_service import generate_explanation
    from cache.redis_client import get_cached_result, cache_result

    start_ms = int(_time.time() * 1000)

    # Cache check
    cached = await get_cached_result(claim)
    if cached:
        cached["cached"] = True
        cached["processing_ms"] = int(_time.time() * 1000) - start_ms
        return cached

    parsed = parse_claim(claim, claim_type)
    claim_emb = embed(claim)

    evidence = await collect_all_evidence(claim)
    if not evidence:
        result = {
            "verdict": "UNVERIFIED",
            "confidence": 0.0,
            "explanation": (
                "No sources could be found to verify this claim. "
                "This does not mean it is false."
            ),
            "llm_provider": "template",
            "support_ratio": 0.5,
            "evidence_count": 0,
            "sources": [],
            "sub_claims": [],
            "is_compound": parsed.is_compound,
            "is_mutation": False,
            "mutation_chain": [],
            "algorithm_trace": {"reason": "no_evidence_found"},
            "processing_ms": int(_time.time() * 1000) - start_ms,
            "cached": False,
            "claim_type": parsed.claim_type,
        }
        return result

    evidence = rank_evidence(claim_emb, evidence)
    evidence = evidence[:settings.evidence_max_articles * 3]
    evidence = classify_stance_bulk(evidence, claim)
    agg = aggregate(evidence)
    verdict, confidence, top_sources, trace = compute_verdict(agg, evidence)
    explanation, llm_provider = await generate_explanation(
        claim=claim,
        verdict=verdict,
        top_sources=top_sources,
        algorithm_trace=trace,
    )
    trace["llm_provider_used"] = llm_provider

    # Async DB operations (best-effort, don't fail the response)
    claim_id = None
    try:
        from db.database import get_pool
        from db.repository import upsert_claim, save_report
        pool = await get_pool()
        emb_list = embedding_to_list(claim_emb)
        claim_id = await upsert_claim(pool, claim, emb_list, parsed.claim_type, parsed.entities, parsed.intent)
        await save_report(pool, claim_id, {
            "verdict": verdict,
            "confidence": confidence,
            "explanation": explanation,
            "llm_provider": llm_provider,
            "support_ratio": agg.support_ratio,
            "evidence_count": agg.evidence_count,
            "sources": top_sources,
            "algorithm_trace": trace,
            "processing_ms": int(_time.time() * 1000) - start_ms,
            "cached": False,
        })
    except Exception as e:
        pass

    result = {
        "verdict": verdict,
        "confidence": confidence,
        "explanation": explanation,
        "llm_provider": llm_provider,
        "support_ratio": float(agg.support_ratio),
        "evidence_count": agg.evidence_count,
        "sources": top_sources,
        "sub_claims": [],
        "is_compound": parsed.is_compound,
        "is_mutation": False,
        "mutation_chain": [],
        "algorithm_trace": trace,
        "processing_ms": int(_time.time() * 1000) - start_ms,
        "cached": False,
        "claim_type": parsed.claim_type,
    }

    await cache_result(claim, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-COMPLIANT API ROUTES  (/v1/*)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/v1/verify", response_model=AsyncVerifyResponse)
async def v1_verify(body: VerifyRequest):
    """
    Async verification: enqueue Celery task, return job_id + WebSocket URL.
    Client should:
      1. Connect to ws://host/ws/{job_id} for real-time stages
      2. OR poll GET /v1/status/{job_id} every 2s
    """
    claim = await _extract_claim_from_request(body)
    if not claim:
        raise HTTPException(status_code=400, detail="No claim text could be extracted.")

    # Language translation
    try:
        from translator import detect_lang, translate_to_en
        src_lang = detect_lang(claim)
        if src_lang != "en":
            claim = translate_to_en(claim, src_lang)
    except Exception:
        pass

    job_id = str(uuid.uuid4())

    # Store initial status
    from cache.redis_client import set_job_status
    await set_job_status(job_id, "queued", ttl=3600)

    # Enqueue Celery task
    from tasks import verify_claim_task
    verify_claim_task.apply_async(
        args=[job_id, claim, body.claim_type or "general"],
        task_id=job_id,
    )

    return AsyncVerifyResponse(
        job_id=job_id,
        status="queued",
        websocket_url=f"ws://localhost:8000/ws/{job_id}",
        poll_url=f"/v1/status/{job_id}",
    )


@app.get("/v1/status/{job_id}", response_model=JobStatusResponse)
async def v1_status(job_id: str):
    """Poll for job result. Returns stage + result when complete."""
    from cache.redis_client import get_job_status
    job = await get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return JobStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        stage=job.get("status"),
        result=job.get("data") if job.get("status") == "complete" else None,
        error=job.get("data", {}).get("error") if job.get("status") == "failed" else None,
    )


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """Real-time WebSocket stage streaming for a verification job."""
    from ws.manager import listen_for_job
    await listen_for_job(job_id, websocket)


@app.get("/v1/history")
async def v1_history(limit: int = 30):
    """Return recent verification history from PostgreSQL."""
    try:
        from db.database import get_pool
        from db.repository import get_recent_reports
        pool = await get_pool()
        rows = await get_recent_reports(pool, limit)
        return {"history": rows}
    except Exception:
        # Fallback dummy history if Postgres is not running
        return {"history": [
            {
                "claim": "COVID-19 vaccines contain tracking microchips.",
                "verdict": "FALSE",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "confidence": 0.98,
                "mutation_chain": [
                  {"text": "Bill Gates put microchips in the COVID vaccine.", "similarity": 0.85, "verdict": "FALSE", "date": "10h ago"},
                  {"text": "The new vaccines have trackers in them.", "similarity": 0.72, "verdict": "FALSE", "date": "1d ago"}
                ]
            },
            {
                "claim": "Eating garlic prevents the flu.",
                "verdict": "MISLEADING",
                "timestamp": (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"),
                "confidence": 0.85
            }
        ]}

@app.get("/v1/mutation-chains")
async def v1_mutation_chains():
    """Return known mutation chains."""
    return {"chains": []}  # Handled by fallback to /v1/history in UI, but provided for completeness

@app.get("/v1/source-credibility")
async def v1_source_credibility():
    """Return source credibility list."""
    # Centralized source credibility ratings
    return {"sources": [
        {"name": "WHO", "domain": "who.int", "tier": 1, "credibility": 0.97, "category": "Health", "country": "International", "shift": 0.02, "notes": "Primary global health authority"},
        {"name": "CDC", "domain": "cdc.gov", "tier": 1, "credibility": 0.96, "category": "Health", "country": "USA", "shift": 0, "notes": "US public health agency"},
        {"name": "Reuters", "domain": "reuters.com", "tier": 1, "credibility": 0.93, "category": "News", "country": "UK", "shift": 0.01, "notes": "Wire service, strong editorial standards"},
        {"name": "AP News", "domain": "apnews.com", "tier": 1, "credibility": 0.95, "category": "News", "country": "USA", "shift": 0.01, "notes": "Non-profit wire service"},
        {"name": "BBC", "domain": "bbc.com", "tier": 1, "credibility": 0.94, "category": "News", "country": "UK", "shift": 0, "notes": "UK public broadcaster"},
        {"name": "Nature", "domain": "nature.com", "tier": 1, "credibility": 0.98, "category": "Science", "country": "International", "shift": 0.01, "notes": "Peer-reviewed scientific journal"},
        {"name": "PubMed", "domain": "pubmed.ncbi.nlm.nih.gov", "tier": 1, "credibility": 0.97, "category": "Science", "country": "USA", "shift": 0, "notes": "NIH biomedical literature index"},
        {"name": "The Guardian", "domain": "guardian.com", "tier": 2, "credibility": 0.82, "category": "News", "country": "UK", "shift": -0.01, "notes": "Independent news outlet"},
        {"name": "NYT", "domain": "nytimes.com", "tier": 2, "credibility": 0.85, "category": "News", "country": "USA", "shift": 0, "notes": "Legacy broadsheet"},
        {"name": "Snopes", "domain": "snopes.com", "tier": 2, "credibility": 0.84, "category": "Fact-check", "country": "USA", "shift": -0.02, "notes": "Dedicated fact-checking site"},
        {"name": "PolitiFact", "domain": "politifact.com", "tier": 2, "credibility": 0.83, "category": "Fact-check", "country": "USA", "shift": 0, "notes": "Political fact-checking"},
        {"name": "GDELT", "domain": "gdeltproject.org", "tier": 2, "credibility": 0.78, "category": "Data", "country": "International", "shift": 0.01, "notes": "Global event database"},
        {"name": "Wikipedia", "domain": "wikipedia.org", "tier": 3, "credibility": 0.72, "category": "Reference", "country": "International", "shift": 0.01, "notes": "Crowd-sourced, use with caution"},
        {"name": "The Daily Mail", "domain": "dailymail.co.uk", "tier": 3, "credibility": 0.45, "category": "News", "country": "UK", "shift": -0.03, "notes": "Tabloid, low accuracy history"},
        {"name": "InfoWars", "domain": "infowars.com", "tier": 4, "credibility": 0.08, "category": "Conspiracy", "country": "USA", "shift": -0.05, "notes": "Known misinformation source"},
        {"name": "Unknown Blog", "domain": "healthtruth.net", "tier": 4, "credibility": 0.28, "category": "Blog", "country": "Unknown", "shift": -0.03, "notes": "Unverified, no editorial oversight"}
    ]}

@app.get("/v1/metrics")
async def v1_metrics():
    """System-wide metrics for the dashboard."""
    from services.circuit_breaker import all_breaker_statuses
    from cache.redis_client import redis_ping

    metrics = {
        "version": "5.2.0",
        "redis_connected": False,
        "db_connected": False,
        "offline_mode": settings.offline_mode,
        "circuit_breakers": all_breaker_statuses(),
        "verdict_distribution": {},
        "total_reports": 0,
    }

    try:
        metrics["redis_connected"] = await redis_ping()
    except Exception:
        pass

    try:
        from db.database import get_pool, db_ping
        from db.repository import get_verdict_distribution
        metrics["db_connected"] = await db_ping()
        if metrics["db_connected"]:
            pool = await get_pool()
            dist = await get_verdict_distribution(pool)
            metrics["verdict_distribution"] = dist
            metrics["total_reports"] = sum(dist.values())
    except Exception:
        pass

    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# COMPATIBILITY SHIM  (React frontend uses these routes directly)
# ─────────────────────────────────────────────────────────────────────────────

# FIX 5: Accept both "claim" and "text" field names so old and new frontends work
class VerifyRequestCompat(BaseModel):
    claim: str = ""
    text: str = ""                    # alias used by some older frontend versions
    input_type: str = "text"
    claim_type: str = "general"
    image_url: Optional[str] = None
    image_base64: Optional[str] = None


@app.post("/verify")
async def verify_compat(body: VerifyRequestCompat):
    """
    Synchronous /verify shim for the React frontend.
    Runs the full pipeline inline (no Celery) and returns the formatted report.

    FIX 5 cont.: Accepts both { claim: "..." } and { text: "..." } JSON bodies.
    FIX 6: Returns JSON with Content-Type: application/json (FastAPI default).
    """
    # Resolve claim text — prefer "claim", fall back to "text"
    raw_body = body.dict()
    claim_text = (raw_body.get("claim") or raw_body.get("text") or "").strip()

    # Build a VerifyRequest for the shared extraction helper
    compat_body = VerifyRequest(
        claim=claim_text,
        input_type=body.input_type,
        claim_type=body.claim_type,
        image_url=body.image_url,
        image_base64=body.image_base64,
    )

    claim = await _extract_claim_from_request(compat_body)
    if not claim:
        raise HTTPException(status_code=400, detail="No claim text could be extracted.")

    # Translation
    source_lang = "en"
    try:
        from translator import detect_lang, translate_to_en, translate_verdict
        source_lang = detect_lang(claim)
        if source_lang != "en":
            claim = translate_to_en(claim, source_lang)
    except Exception:
        pass

    raw = await _sync_pipeline(claim, body.claim_type or "general")

    # Localise verdict if translated
    if source_lang != "en":
        try:
            from translator import translate_verdict
            raw["localized_verdict"] = translate_verdict(raw["verdict"], source_lang)
        except Exception:
            pass

    return _format_for_ui(raw, claim, body.claim_type or "general")


@app.get("/health")
async def health():
    """Health check — used by frontend and load balancers."""
    from cache.redis_client import redis_ping
    from db.database import db_ping

    redis_ok = False
    db_ok = False

    try:
        redis_ok = await redis_ping()
    except Exception:
        pass
    try:
        db_ok = await db_ping()
    except Exception:
        pass

    # Check BART is loaded
    try:
        from pipeline.stance import _classifier
        bart_ok = _classifier is not None
    except Exception:
        bart_ok = False

    return {
        "status": "ok",
        "version": "5.2.0",
        "message": "OSINT Engine is running",
        "models_loaded": bart_ok,
        "redis": redis_ok,
        "db": db_ok,
        "offline_mode": settings.offline_mode,
    }


@app.get("/history")
async def get_history():
    """Legacy history endpoint — reads from DB with fallback to empty."""
    try:
        from db.database import get_pool
        from db.repository import get_recent_reports
        pool = await get_pool()
        rows = await get_recent_reports(pool, 30)
        history = [
            {
                "timestamp": r["created_at"].strftime("%Y-%m-%d %H:%M") if hasattr(r["created_at"], "strftime") else str(r["created_at"]),
                "claim": (r.get("claim_text") or "")[:100],
                "verdict": r.get("verdict", "UNKNOWN"),
            }
            for r in rows
        ]
        return {"history": history}
    except Exception:
        return {"history": [{"claim": "Demo Claim", "verdict": "FALSE", "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}]}


@app.delete("/history/clear")
async def clear_history():
    return {"status": "success", "message": "History is stored in DB — clear via psql."}