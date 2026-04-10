"""
backend/tasks.py
-----------------
Celery task queue for async claim verification.

Task: verify_claim_task
  1. Check Redis cache (instant return if hit)
  2. Parse claim (spaCy)
  3. Embed claim (MiniLM)
  4. Collect evidence (parallel scraping)
  5. Rank evidence by semantic similarity
  6. Classify stance (BART-MNLI)
  7. Aggregate + early exit logic
  8. Compute verdict
  9. Generate explanation (LM Studio → Gemini → template)
  10. Detect mutations (pgvector)
  11. Persist to PostgreSQL
  12. Cache in Redis
  13. Publish WebSocket stage events

Windows note: Use --pool=solo when running the worker on Windows.
"""
import asyncio
import json
import logging
import platform
import time
import uuid
from typing import Optional

from celery import Celery
from celery.utils.log import get_task_logger

from config import settings

logger = get_task_logger(__name__)

# ── Celery app ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "osint_verify",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=120,   # 2-min soft kill
    task_time_limit=180,        # 3-min hard kill
    result_expires=3600,        # 1h retention
    # Windows compatibility
    worker_pool="solo" if platform.system() == "Windows" else "prefork",
)


# ── Async helper ──────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine from synchronous Celery task context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Pipeline publish helper ───────────────────────────────────────────────────

async def _publish(job_id: str, stage: str, message: str, progress: int = 0, data: dict = None):
    from cache.redis_client import publish_stage, set_job_status
    event = {
        "type": "stage",
        "stage": stage,
        "message": message,
        "progress": progress,
        "data": data or {},
    }
    await publish_stage(job_id, event)
    await set_job_status(job_id, stage, data=data, ttl=3600)


# ── Main task ─────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.verify_claim_task",
    max_retries=2,
    default_retry_delay=5,
)
def verify_claim_task(self, job_id: str, claim: str, claim_type: str = "general"):
    """
    Full async verification pipeline wrapped as a Celery task.
    Publishes WebSocket events at each stage.
    """
    logger.info(f"[Task] Starting job {job_id} for claim: '{claim[:60]}'")

    try:
        result = _run_async(_run_full_pipeline(job_id, claim, claim_type))
        return result
    except Exception as exc:
        logger.error(f"[Task] FAILED job {job_id}: {exc}", exc_info=True)
        _run_async(_publish(job_id, "error", str(exc)))
        _run_async(_set_failed(job_id, str(exc)))
        raise self.retry(exc=exc, countdown=5)


async def _set_failed(job_id: str, error: str):
    from cache.redis_client import set_job_status, publish_stage
    await set_job_status(job_id, "failed", data={"error": error})
    await publish_stage(job_id, {"type": "error", "error": error})


async def _run_full_pipeline(job_id: str, claim: str, claim_type: str) -> dict:
    """
    Full 9-step pipeline with WebSocket stage broadcasting.
    """
    from cache.redis_client import get_cached_result, cache_result, publish_stage, set_job_status
    from pipeline.claim_parser import parse_claim
    from pipeline.embedder import embed, rank_evidence, embedding_to_list
    from pipeline.stance import classify_stance_bulk
    from pipeline.aggregator import aggregate
    from pipeline.verdict import compute_verdict
    from pipeline.mutation import detect_mutation
    from sources.collector import collect_all_evidence
    from services.llm_service import generate_explanation
    from db.database import get_pool
    from db.repository import upsert_claim, save_report, log_nli
    from models import VerdictResult

    start_ms = int(time.time() * 1000)

    # ── Step 0: Cache check ───────────────────────────────────────────────────
    cached = await get_cached_result(claim)
    if cached:
        logger.info(f"[Pipeline] Cache HIT for '{claim[:40]}'")
        cached["cached"] = True
        cached["processing_ms"] = int(time.time() * 1000) - start_ms
        await set_job_status(job_id, "complete", data=cached)
        await publish_stage(job_id, {"type": "complete", "result": cached})
        return cached

    # ── Step 1: Claim Parsing ─────────────────────────────────────────────────
    await _publish(job_id, "parsing", "Analysing claim structure…", progress=10)
    parsed = parse_claim(claim, claim_type)
    logger.info(
        f"[Pipeline] Parsed: type={parsed.claim_type}, "
        f"entities={len(parsed.entities)}, compound={parsed.is_compound}"
    )

    # ── Step 2+3: Embedding ───────────────────────────────────────────────────
    await _publish(job_id, "parsing", "Computing semantic embedding…", progress=18)
    claim_embedding = embed(claim)
    embedding_list = embedding_to_list(claim_embedding)

    # ── Step 4: Evidence Retrieval ────────────────────────────────────────────
    await _publish(job_id, "searching", "Searching OSINT sources…", progress=25)
    evidence = await collect_all_evidence(claim)

    if not evidence:
        logger.warning("[Pipeline] No evidence found — UNVERIFIED")
        result = _build_unverified(claim, parsed, int(time.time() * 1000) - start_ms)
        await _persist_and_notify(job_id, claim, embedding_list, parsed, result, None)
        return result

    # ── Step 5: Semantic Ranking ──────────────────────────────────────────────
    await _publish(job_id, "searching", f"Ranking {len(evidence)} sources…", progress=40)
    evidence = rank_evidence(claim_embedding, evidence)
    # Keep top N for efficiency
    evidence = evidence[:settings.evidence_max_articles * 3]

    # ── Step 6: Stance Classification ────────────────────────────────────────
    await _publish(job_id, "scoring", "Classifying stance of each source…", progress=55)
    evidence = classify_stance_bulk(evidence, claim)

    # ── Step 7: Aggregation + Credibility Scoring ─────────────────────────────
    await _publish(job_id, "scoring", "Scoring evidence and computing ratios…", progress=68)
    agg = aggregate(evidence)

    # ── Step 8: Verdict ───────────────────────────────────────────────────────
    await _publish(job_id, "scoring", "Computing verdict…", progress=78)
    verdict, confidence, top_sources, trace = compute_verdict(agg, evidence)

    # ── Step 9: Explanation ───────────────────────────────────────────────────
    await _publish(job_id, "explaining", "Generating explanation…", progress=88)
    explanation, llm_provider = await generate_explanation(
        claim=claim,
        verdict=verdict,
        top_sources=top_sources,
        algorithm_trace=trace,
    )
    trace["llm_provider_used"] = llm_provider

    # ── Step 10: Mutation Detection ───────────────────────────────────────────
    try:
        pool = await get_pool()
        # Persist claim first to get claim_id
        claim_id = await upsert_claim(
            pool, claim, embedding_list,
            parsed.claim_type, parsed.entities, parsed.intent,
        )
        mutation = await detect_mutation(claim, embedding_list, claim_id, pool)
    except Exception as e:
        logger.warning(f"[Pipeline] DB/mutation error: {e}")
        claim_id = None
        mutation = None

    is_mutation = mutation.is_mutation if mutation else False
    mutation_chain = mutation.mutation_chain if mutation else []

    # ── Build result dict ─────────────────────────────────────────────────────
    proc_ms = int(time.time() * 1000) - start_ms
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
        "is_mutation": is_mutation,
        "mutation_chain": mutation_chain,
        "algorithm_trace": trace,
        "processing_ms": proc_ms,
        "cached": False,
        "claim_type": parsed.claim_type,
    }

    # ── Compound sub-claim processing ─────────────────────────────────────────
    if parsed.is_compound and parsed.sub_claims:
        sub_results = []
        for sub_text in parsed.sub_claims[:3]:  # max 3 sub-claims
            sub_ev = await collect_all_evidence(sub_text)
            if sub_ev:
                sub_ev = rank_evidence(embed(sub_text), sub_ev)
                sub_ev = classify_stance_bulk(sub_ev, sub_text)
                sub_agg = aggregate(sub_ev)
                sub_verdict, sub_conf, _, _ = compute_verdict(sub_agg, sub_ev)
            else:
                sub_verdict, sub_conf = "UNVERIFIED", 0.0
            sub_results.append({
                "text": sub_text,
                "verdict": sub_verdict,
                "confidence": sub_conf,
            })
        result["sub_claims"] = sub_results
        result["verdict"] = _aggregate_compound_verdicts(sub_results) or verdict

    await _persist_and_notify(job_id, claim, embedding_list, parsed, result, claim_id)
    return result


def _aggregate_compound_verdicts(sub_results: list) -> str:
    """Merge sub-claim verdicts into a single compound verdict."""
    verdicts = [s["verdict"] for s in sub_results]
    unique = set(verdicts)
    if unique == {"TRUE"}:
        return "TRUE"
    if unique == {"FALSE"}:
        return "FALSE"
    if unique == {"UNVERIFIED"}:
        return "UNVERIFIED"
    if "CONFLICTING" in unique:
        return "CONFLICTING"
    if "TRUE" in unique and "FALSE" in unique:
        return "MISLEADING"
    return "MISLEADING"


def _build_unverified(claim: str, parsed, proc_ms: int) -> dict:
    return {
        "verdict": "UNVERIFIED",
        "confidence": 0.0,
        "explanation": (
            "We could not find any sources to verify this claim. "
            "This does not necessarily mean it is false — "
            "it may be too recent or too niche to have online coverage."
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
        "processing_ms": proc_ms,
        "cached": False,
        "claim_type": parsed.claim_type,
    }


async def _persist_and_notify(
    job_id: str,
    claim: str,
    embedding_list: list,
    parsed,
    result: dict,
    claim_id: Optional[str],
):
    """Store to DB, cache in Redis, then broadcast completion event."""
    from cache.redis_client import cache_result, set_job_status, publish_stage
    from db.database import get_pool
    from db.repository import save_report

    # Persist to PostgreSQL
    try:
        pool = await get_pool()
        if claim_id is None:
            from db.repository import upsert_claim
            claim_id = await upsert_claim(
                pool, claim, embedding_list,
                parsed.claim_type, parsed.entities, parsed.intent,
            )
        await save_report(pool, claim_id, result)
    except Exception as e:
        logger.warning(f"[Pipeline] DB persist error: {e}")

    # Cache in Redis
    await cache_result(claim, result)

    # Notify WebSocket
    await set_job_status(job_id, "complete", data=result)
    await publish_stage(job_id, {"type": "complete", "result": result})

    logger.info(
        f"[Pipeline] Done — verdict={result['verdict']} "
        f"conf={result['confidence']} "
        f"time={result['processing_ms']}ms"
    )
