"""
backend/pipeline/runtime.py
-----------------------------
Shared deterministic verdict runtime for sync and async entry points.

FIX LOG:
  - needs_stage2() referenced five fields that did NOT exist on
    AggregationResult: opinionated_count, independent_domains,
    quality_score, adversarial_risk, temporal_penalty.
    These are now populated by the fixed aggregator.py, so the
    function works correctly.
  - aggregate() calls now pass `claim` as the second argument so
    temporal/diversity/adversarial enrichment runs inside the aggregator.
  - build_async_client and collect_evidence_stage are now imported from
    sources.collector where they are defined (were missing before).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pipeline.aggregator import AggregationResult, aggregate
from pipeline.diversity import dedupe_evidence
from pipeline.embedder import embed, rank_evidence
from pipeline.stance import classify_stance_bulk
from pipeline.verdict import compute_verdict
from sources.collector import build_async_client, collect_evidence_stage   # FIX: now exist


STAGE1_CLASSIFY_CAP = 8
TOTAL_CLASSIFY_CAP = 12


@dataclass
class DeterministicRunResult:
    claim_embedding: object
    evidence: list
    agg: AggregationResult
    verdict: str
    confidence: float
    top_sources: list
    trace: dict
    used_stage2: bool
    stage1_evidence_count: int
    stage2_evidence_count: int
    classified_candidates: int


def should_run_subclaims(parsed, verdict: str, confidence: float) -> bool:
    return bool(
        getattr(parsed, "is_compound", False)
        and getattr(parsed, "sub_claims", None)
        and (
            verdict in {"MISLEADING", "CONFLICTING", "UNVERIFIED"}
            or confidence < 0.70
        )
    )


async def run_subclaim_verification(
    sub_claims: list,
    max_subclaims: int = 2,
    max_per_source: int = 2,
) -> list:
    results = []
    for sub_text in sub_claims[:max_subclaims]:
        sub_run = await run_deterministic_verdict(sub_text, max_per_source=max_per_source)
        results.append({
            "text": sub_text,
            "verdict": sub_run.verdict,
            "confidence": sub_run.confidence,
        })
    return results


def aggregate_compound_verdicts(sub_results: list) -> str:
    verdicts = [item["verdict"] for item in sub_results]
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


def aggregate_compound_confidence(
    sub_results: list,
    base_confidence: float = 0.0,
) -> float:
    if not sub_results:
        return round(base_confidence, 3)
    avg = sum(item["confidence"] for item in sub_results) / len(sub_results)
    unique_verdicts = len({item["verdict"] for item in sub_results})
    penalty = max(0, unique_verdicts - 1) * 0.05
    blended = (avg + base_confidence) / 2 if base_confidence else avg
    return round(max(0.05, min(0.95, blended - penalty)), 3)


def needs_stage2(agg: AggregationResult) -> bool:
    """
    Decide whether to escalate to Stage-2 (broader) retrieval.

    FIX: the original function referenced five fields that never existed
    on AggregationResult.  They are now computed by the fixed aggregator.
    The logic is preserved — skip Stage 2 only when Stage 1 already
    gives a high-quality, low-risk, decisive signal.
    """
    # Always escalate after an early exit — the result is already decisive.
    if agg.early_exit:
        return False

    # Skip Stage 2 when all quality signals are strong.
    if (
        agg.opinionated_count >= 4          # enough opinionated evidence
        and agg.independent_domains >= 3    # from multiple independent sources
        and agg.quality_score >= 0.65       # high overall quality
        and agg.adversarial_risk <= 0.35    # low adversarial signal
        and agg.temporal_penalty <= 0.15    # evidence is recent
        and (
            agg.support_ratio >= 0.75       # decisive support
            or agg.support_ratio <= 0.25    # decisive contradiction
        )
    ):
        return False

    return True


async def run_deterministic_verdict(
    claim: str,
    claim_embedding=None,
    max_per_source: Optional[int] = None,
) -> DeterministicRunResult:
    """
    Run staged retrieval → ranking → stance → aggregation → verdict.
    """
    claim_embedding = claim_embedding if claim_embedding is not None else embed(claim)

    async with build_async_client() as client:
        stage1_evidence = await collect_evidence_stage(
            claim, 1, max_per_source=max_per_source, client=client,
        )
        ranked_stage1 = rank_evidence(claim_embedding, stage1_evidence)[:STAGE1_CLASSIFY_CAP]
        classified_stage1 = classify_stance_bulk(ranked_stage1, claim)
        # FIX: pass claim so aggregator enriches with temporal/diversity/adversarial
        agg_stage1 = aggregate(classified_stage1, claim)

        if not needs_stage2(agg_stage1):
            verdict, confidence, top_sources, trace = compute_verdict(agg_stage1, classified_stage1)
            trace.update({
                "retrieval_stage": "stage1",
                "used_stage2": False,
                "stage1_evidence_count": len(stage1_evidence),
                "stage2_evidence_count": 0,
                "classified_candidates": len(classified_stage1),
            })
            return DeterministicRunResult(
                claim_embedding=claim_embedding,
                evidence=classified_stage1,
                agg=agg_stage1,
                verdict=verdict,
                confidence=confidence,
                top_sources=top_sources,
                trace=trace,
                used_stage2=False,
                stage1_evidence_count=len(stage1_evidence),
                stage2_evidence_count=0,
                classified_candidates=len(classified_stage1),
            )

        stage2_evidence = await collect_evidence_stage(
            claim, 2, max_per_source=max_per_source, client=client,
        )

    combined = dedupe_evidence(stage1_evidence + stage2_evidence)
    ranked = rank_evidence(claim_embedding, combined)[:TOTAL_CLASSIFY_CAP]
    classified = classify_stance_bulk(ranked, claim)
    # FIX: pass claim
    agg = aggregate(classified, claim)
    verdict, confidence, top_sources, trace = compute_verdict(agg, classified)
    trace.update({
        "retrieval_stage": "stage2",
        "used_stage2": True,
        "stage1_evidence_count": len(stage1_evidence),
        "stage2_evidence_count": len(stage2_evidence),
        "classified_candidates": len(classified),
    })
    return DeterministicRunResult(
        claim_embedding=claim_embedding,
        evidence=classified,
        agg=agg,
        verdict=verdict,
        confidence=confidence,
        top_sources=top_sources,
        trace=trace,
        used_stage2=True,
        stage1_evidence_count=len(stage1_evidence),
        stage2_evidence_count=len(stage2_evidence),
        classified_candidates=len(classified),
    )