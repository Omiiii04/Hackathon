"""
backend/pipeline/aggregator.py
--------------------------------
Evidence aggregation logic: computes weighted support/contradiction ratios,
applies early exit rules, and produces an intermediate verdict signal.

Thresholds (from SDD v5.2 + config):
  HIGH  = 0.80  → early TRUE signal
  LOW   = 0.20  → early FALSE signal
"""
import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    support_ratio: float = 0.5
    contradiction_ratio: float = 0.5
    support_weight: float = 0.0
    contradiction_weight: float = 0.0
    neutral_weight: float = 0.0
    early_exit: bool = False
    early_exit_reason: str = ""
    verdict_hint: str = "UNVERIFIED"
    tier1_count: int = 0
    avg_credibility: float = 0.0
    agreement: float = 0.0
    supporting_count: int = 0
    contradicting_count: int = 0
    neutral_count: int = 0
    evidence_count: int = 0


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


def aggregate(evidence: list) -> AggregationResult:
    """
    Step 6 of the pipeline: compute weighted support/contradiction ratios
    and apply early exit rules.

    Weighting formula per evidence item:
        weight = credibility × recency × (1 + semantic_similarity) / 2 × stance_confidence
    """
    result = AggregationResult()

    if not evidence:
        return result

    result.evidence_count = len(evidence)

    supporting = []
    contradicting = []
    neutral = []

    for item in evidence:
        cred = getattr(item, "credibility", 0.40)
        days_ago = getattr(item, "published_days_ago", 30)
        semantic_sim = getattr(item, "semantic_similarity", 0.5)
        stance_conf = getattr(item, "stance_confidence", 0.5)
        stance = getattr(item, "stance", "NEUTRAL")

        recency = _recency_factor(days_ago)

        # Composite weight
        weight = cred * recency * ((1 + semantic_sim) / 2) * stance_conf
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

    # Support ratio (only over opinionated evidence)
    ratio = sup_weight / active if active > 0 else 0.5

    # Agreement strength (how one-sided is the opinionated evidence)
    agreement = abs(sup_weight - con_weight) / active if active > 0 else 0.0

    # Stats
    n = len(evidence)
    avg_cred = sum(getattr(e, "credibility", 0.4) for e in evidence) / n
    tier1_count = sum(1 for e in evidence if getattr(e, "credibility", 0) >= 0.85)

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

    # ── Early exit rules (SDD §6.4) ───────────────────────────────────────────
    high_t = settings.early_exit_ratio_high
    low_t = settings.early_exit_ratio_low
    tier1_t = settings.early_exit_tier1_threshold

    if ratio >= high_t and tier1_count >= tier1_t and agreement >= 0.6:
        result.early_exit = True
        result.early_exit_reason = f"ratio={ratio:.2f} >= {high_t} with {tier1_count} Tier-1"
        result.verdict_hint = "TRUE"
        logger.info(f"[Aggregator] Early exit TRUE — {result.early_exit_reason}")

    elif ratio <= low_t and tier1_count >= tier1_t and agreement >= 0.6:
        result.early_exit = True
        result.early_exit_reason = f"ratio={ratio:.2f} <= {low_t} with {tier1_count} Tier-1"
        result.verdict_hint = "FALSE"
        logger.info(f"[Aggregator] Early exit FALSE — {result.early_exit_reason}")

    else:
        result.verdict_hint = "CONTINUE"

    return result
