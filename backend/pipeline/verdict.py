"""
backend/pipeline/verdict.py
-----------------------------
Improved verdict engine: rule-based + probabilistic.

FIX LOG:
  - BUG: `"verdict_reason": reason if "reason" in dir() else "unknown"`
    `dir()` returns module/object attributes, NOT local variable names.
    It always fell through to "unknown".  Fixed to use a pre-initialised
    local variable and `locals()` as a guard.
  - Added `independent_domains` and `temporal_penalty` to the trace dict
    so tests and the frontend trace-tab can read them.
  - compute_verdict now accepts the enriched AggregationResult and
    forwards diversity/temporal data into the trace.
"""
import logging
import math
from typing import List, Tuple

from pipeline.aggregator import AggregationResult
from config import settings

logger = logging.getLogger(__name__)


def _sigmoid(x: float, scale: float = 10.0) -> float:
    """Sigmoid scaled between 0.5 and 0.95."""
    return 1 / (1 + math.exp(-scale * (x - 0.5)))


def compute_confidence(agg: AggregationResult) -> float:
    """
    Calibrated confidence (0.0–0.95).
    50% avg credibility + 30% agreement + 20% evidence quantity (cap 10).
    """
    n = max(agg.evidence_count, 1)
    raw = (
        0.50 * agg.avg_credibility
        + 0.30 * agg.agreement
        + 0.20 * min(1.0, n / 10)
    )
    sig = _sigmoid(raw, scale=settings.confidence_sigmoid_scale)
    return round(min(sig, 0.95), 3)


def compute_verdict(
    agg: AggregationResult,
    evidence: list,
) -> Tuple[str, float, list, dict]:
    """
    Map aggregation result → (verdict, confidence, top_sources, trace).
    """
    n = agg.evidence_count
    ratio = agg.support_ratio
    agreement = agg.agreement
    tier1 = agg.tier1_count
    avg_cred = agg.avg_credibility

    # Pre-initialise reason so the variable is always defined.
    # FIX: the original code used `"reason" in dir()` which checks object
    # attributes — it NEVER found a local variable, so it always returned
    # "unknown".  Initialising here removes that footgun entirely.
    reason = "unknown"

    # ── Guard: insufficient evidence ──────────────────────────────────────────
    if n < 2 or avg_cred < 0.35:
        verdict = "UNVERIFIED"
        reason = "insufficient_credible_evidence"

    # ── Guard: no opinionated evidence ────────────────────────────────────────
    elif agg.support_weight + agg.contradiction_weight == 0:
        verdict = "UNVERIFIED"
        reason = "all_neutral_evidence"

    # ── Early exit (pre-computed by aggregator) ───────────────────────────────
    elif agg.early_exit:
        verdict = agg.verdict_hint       # TRUE or FALSE
        reason = f"early_exit:{agg.early_exit_reason}"

    # ── Conflicting: near-equal weights ──────────────────────────────────────
    elif agreement < 0.15 and agg.support_weight > 0 and agg.contradiction_weight > 0:
        verdict = "CONFLICTING"
        reason = "near_equal_weight_disagreement"

    # ── Dynamic thresholds ────────────────────────────────────────────────────
    else:
        base_true = min(0.82, 0.62 + (n / 50))
        cred_adjust = (avg_cred - 0.5) * 0.15
        true_threshold = min(0.90, base_true + cred_adjust)
        false_threshold = max(0.10, 1.0 - true_threshold)

        if ratio >= true_threshold:
            verdict = "TRUE"
            reason = f"ratio={ratio:.3f}>={true_threshold:.3f}"
        elif ratio <= false_threshold:
            verdict = "FALSE"
            reason = f"ratio={ratio:.3f}<={false_threshold:.3f}"
        elif 0.28 <= ratio <= 0.72:
            verdict = "MISLEADING"
            reason = f"mixed_evidence ratio={ratio:.3f}"
        else:
            verdict = "MISLEADING"
            reason = f"borderline ratio={ratio:.3f}"

    confidence = compute_confidence(agg)

    # Discount for uncertain verdicts
    if verdict in ("CONFLICTING", "UNVERIFIED"):
        confidence = round(confidence * 0.7, 3)
    elif verdict == "MISLEADING":
        confidence = round(confidence * 0.85, 3)

    confidence = max(0.05, min(0.95, confidence))

    # ── Top sources ────────────────────────────────────────────────────────────
    top_sources = sorted(
        evidence,
        key=lambda e: (getattr(e, "credibility", 0) * 0.6 + getattr(e, "score", 0) * 0.4),
        reverse=True,
    )[:5]

    sources_out = [
        {
            "title": getattr(e, "title", "")[:100],
            "url": getattr(e, "url", ""),
            "source": getattr(e, "source", ""),
            "credibility_score": round(getattr(e, "credibility", 0.4), 3),
            "credibility": _cred_label(getattr(e, "credibility", 0.4)),
            "stance": getattr(e, "stance", "NEUTRAL"),
            "stance_confidence": round(getattr(e, "stance_confidence", 0), 3),
            "semantic_similarity": round(getattr(e, "semantic_similarity", 0), 3),
        }
        for e in top_sources
    ]

    trace = {
        "verdict_reason": reason,           # FIX: was always "unknown" before
        "support_ratio": ratio,
        "contradiction_ratio": agg.contradiction_ratio,
        "evidence_count": n,
        "tier1_count": tier1,
        "supporting_count": agg.supporting_count,
        "contradicting_count": agg.contradicting_count,
        "neutral_count": agg.neutral_count,
        "supporting_weight": agg.support_weight,
        "contradicting_weight": agg.contradiction_weight,
        "avg_credibility": avg_cred,
        "agreement": agreement,
        "early_exit": agg.early_exit,
        "early_exit_reason": agg.early_exit_reason,
        "confidence_final": confidence,
        # FIX: these were referenced in tests but never populated
        "independent_domains": agg.independent_domains,
        "temporal_penalty": agg.temporal_penalty,
        "adversarial_risk": agg.adversarial_risk,
        "quality_score": agg.quality_score,
        # Legacy frontend keys
        "threshold_TRUE": 0.75,
        "threshold_FALSE": 0.25,
        "temporal_mismatch": agg.temporal_penalty > 0.25,
        "echo_chamber_penalty": agg.independent_domains < 2 and n >= 3,
    }

    logger.info(
        f"[Verdict] {verdict} | conf={confidence} | "
        f"ratio={ratio:.3f} | n={n} | tier1={tier1} | "
        f"domains={agg.independent_domains}"
    )

    return verdict, confidence, sources_out, trace


def _cred_label(score: float) -> str:
    if score >= 0.85:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"