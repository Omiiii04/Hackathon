"""
backend/pipeline/aggregator.py
--------------------------------
Evidence aggregation: weighted support/contradiction ratios, early-exit rules,
diversity/temporal/adversarial enrichment.

FIX LOG:
  - aggregate() now accepts optional `claim: str` second argument so all
    call-sites (runtime.py, tasks.py, tests) are consistent.
  - AggregationResult gained five fields that runtime.py/needs_stage2()
    was already reading but that never existed:
        opinionated_count, independent_domains, quality_score,
        adversarial_risk, temporal_penalty
  - Early-exit now requires independent_domains >= 2 (prevents a single
    high-credibility domain from triggering early TRUE/FALSE).
  - Diversity, temporal-alignment, and adversarial-risk modules are
    integrated here so the full enriched result is available downstream.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import List

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    # ── core ratios ───────────────────────────────────────────────────────────
    support_ratio: float = 0.5
    contradiction_ratio: float = 0.5
    support_weight: float = 0.0
    contradiction_weight: float = 0.0
    neutral_weight: float = 0.0
    # ── counts ────────────────────────────────────────────────────────────────
    evidence_count: int = 0
    supporting_count: int = 0
    contradicting_count: int = 0
    neutral_count: int = 0
    tier1_count: int = 0
    # ── quality signals ───────────────────────────────────────────────────────
    avg_credibility: float = 0.0
    agreement: float = 0.0
    # ── NEW fields (previously missing → AttributeError in runtime.py) ───────
    opinionated_count: int = 0          # supporting + contradicting items
    independent_domains: int = 0        # unique root-domains in evidence
    quality_score: float = 0.0          # composite 0-1 quality signal
    adversarial_risk: float = 0.0       # 0-1; high = sensational/low-cred
    temporal_penalty: float = 0.0       # 0-1; high = stale / pre-dating
    # ── early exit ────────────────────────────────────────────────────────────
    early_exit: bool = False
    early_exit_reason: str = ""
    verdict_hint: str = "UNVERIFIED"


def _recency_factor(published_days_ago: int = 30) -> float:
    """Weight recent evidence more heavily."""
    if published_days_ago <= 1:
        return 1.00
    if published_days_ago <= 7:
        return 0.90
    if published_days_ago <= 30:
        return 0.75
    if published_days_ago <= 365:
        return 0.50
    return 0.30


def aggregate(evidence: list, claim: str = "") -> AggregationResult:
    """
    Step 6 of the pipeline: compute weighted support/contradiction ratios,
    enrich with diversity / temporal / adversarial metrics, and apply
    early-exit rules.

    Parameters
    ----------
    evidence : list[EvidenceItem]
    claim    : str  (optional; forwarded to adversarial/temporal helpers)

    Weighting formula per item:
        weight = credibility × recency × (1 + semantic_similarity)/2
                 × stance_confidence × independence_factor × temporal_alignment
    """
    result = AggregationResult()

    if not evidence:
        return result

    result.evidence_count = len(evidence)

    # ── Diversity enrichment (domain counts + independence_factor) ────────────
    try:
        from pipeline.diversity import (
            dedupe_evidence,
            apply_independence_factors,
            compute_diversity_metrics,
        )
        apply_independence_factors(evidence)
        diversity = compute_diversity_metrics(evidence)
        result.independent_domains = diversity["independent_domains"]
    except Exception as e:
        logger.warning(f"[Aggregator] Diversity module error: {e}")
        result.independent_domains = len({getattr(e, "url", "").split("/")[2] for e in evidence if getattr(e, "url", "")})

    # ── Temporal enrichment ───────────────────────────────────────────────────
    temporal_info: dict = {}
    if claim:
        try:
            from pipeline.temporal import annotate_temporal_alignment
            temporal_info = annotate_temporal_alignment(evidence, claim)
            result.temporal_penalty = temporal_info.get("temporal_penalty", 0.0)
        except Exception as e:
            logger.warning(f"[Aggregator] Temporal module error: {e}")

    # ── Per-item weighting ────────────────────────────────────────────────────
    supporting = []
    contradicting = []
    neutral = []

    for item in evidence:
        cred = getattr(item, "credibility", 0.40)
        days_ago = getattr(item, "published_days_ago", 30)
        semantic_sim = getattr(item, "semantic_similarity", 0.5)
        stance_conf = getattr(item, "stance_confidence", 0.5)
        stance = getattr(item, "stance", "NEUTRAL")
        indep = getattr(item, "independence_factor", 1.0)
        t_align = getattr(item, "temporal_alignment", 1.0)

        recency = _recency_factor(days_ago)
        weight = cred * recency * ((1 + semantic_sim) / 2) * stance_conf * indep * t_align
        item.score = round(weight, 4)

        if stance == "SUPPORTING":
            supporting.append(item)
        elif stance == "CONTRADICTING":
            contradicting.append(item)
        else:
            neutral.append(item)

    sup_weight = sum(e.score for e in supporting)
    con_weight = sum(e.score for e in contradicting)
    neu_weight = sum(e.score for e in neutral)
    active = sup_weight + con_weight

    ratio = sup_weight / active if active > 0 else 0.5
    agreement = abs(sup_weight - con_weight) / active if active > 0 else 0.0

    n = len(evidence)
    avg_cred = sum(getattr(e, "credibility", 0.4) for e in evidence) / n
    tier1_count = sum(1 for e in evidence if getattr(e, "credibility", 0) >= 0.85)
    opinionated_count = len(supporting) + len(contradicting)

    result.support_ratio = round(ratio, 4)
    result.contradiction_ratio = round(1 - ratio, 4)
    result.support_weight = round(sup_weight, 4)
    result.contradiction_weight = round(con_weight, 4)
    result.neutral_weight = round(neu_weight, 4)
    result.avg_credibility = round(avg_cred, 4)
    result.agreement = round(agreement, 4)
    result.tier1_count = tier1_count
    result.supporting_count = len(supporting)
    result.contradicting_count = len(contradicting)
    result.neutral_count = len(neutral)
    result.opinionated_count = opinionated_count

    # ── Adversarial risk ──────────────────────────────────────────────────────
    if claim:
        try:
            from pipeline.adversarial import compute_adversarial_risk
            from pipeline.diversity import compute_diversity_metrics
            div = compute_diversity_metrics(evidence)
            adv = compute_adversarial_risk(
                claim,
                evidence,
                top_domain_share=div["top_domain_share"],
                opinionated_count=opinionated_count,
            )
            result.adversarial_risk = adv["adversarial_risk"]
        except Exception as e:
            logger.warning(f"[Aggregator] Adversarial module error: {e}")

    # ── Quality score (composite) ─────────────────────────────────────────────
    diversity_score = min(result.independent_domains / 4.0, 1.0)
    result.quality_score = round(
        0.40 * avg_cred
        + 0.30 * agreement
        + 0.20 * diversity_score
        + 0.10 * min(1.0, n / 10),
        4,
    )

    # ── Early exit rules (SDD §6.4) ───────────────────────────────────────────
    # Requires BOTH tier-1 sources AND independent domains to avoid
    # a single publisher gaming the early-exit path.
    high_t = settings.early_exit_ratio_high
    low_t = settings.early_exit_ratio_low
    tier1_t = settings.early_exit_tier1_threshold

    if (
        ratio >= high_t
        and tier1_count >= tier1_t
        and result.independent_domains >= 2
        and agreement >= 0.6
    ):
        result.early_exit = True
        result.early_exit_reason = (
            f"ratio={ratio:.2f}>={high_t} | "
            f"tier1={tier1_count} | domains={result.independent_domains}"
        )
        result.verdict_hint = "TRUE"
        logger.info(f"[Aggregator] Early exit TRUE — {result.early_exit_reason}")

    elif (
        ratio <= low_t
        and tier1_count >= tier1_t
        and result.independent_domains >= 2
        and agreement >= 0.6
    ):
        result.early_exit = True
        result.early_exit_reason = (
            f"ratio={ratio:.2f}<={low_t} | "
            f"tier1={tier1_count} | domains={result.independent_domains}"
        )
        result.verdict_hint = "FALSE"
        logger.info(f"[Aggregator] Early exit FALSE — {result.early_exit_reason}")

    else:
        result.verdict_hint = "CONTINUE"

    return result