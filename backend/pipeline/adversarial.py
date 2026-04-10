"""
backend/pipeline/adversarial.py
---------------------------------
Deterministic adversarial-risk heuristics.
"""
from __future__ import annotations

import re
from typing import List


_SENSATIONAL_RE = re.compile(
    r"\b(breaking|bombshell|shocking|urgent|must see|media won't|they don't want you|exposed|proof)\b",
    re.I,
)
_HEDGE_RE = re.compile(
    r"\b(allegedly|reportedly|sources say|people are saying|rumou?r|unverified|claims? that|anonymous sources?)\b",
    re.I,
)
_ALL_CAPS_RE = re.compile(r"\b[A-Z]{4,}\b")
_PUNCT_RE = re.compile(r"([!?])\1{1,}")


def compute_claim_style_risk(claim: str) -> float:
    """Score sensational phrasing, hedging, and visual urgency cues."""
    if not claim:
        return 0.0

    sensational = min(len(_SENSATIONAL_RE.findall(claim)) * 0.22, 0.45)
    hedges = min(len(_HEDGE_RE.findall(claim)) * 0.16, 0.30)
    all_caps = min(len(_ALL_CAPS_RE.findall(claim)) * 0.08, 0.16)
    punctuation = 0.12 if _PUNCT_RE.search(claim) else 0.0
    return round(min(1.0, sensational + hedges + all_caps + punctuation), 4)


def compute_evidence_noise(evidence: List) -> float:
    """Noise rises with neutral, low-similarity, and short evidence."""
    if not evidence:
        return 1.0

    n = len(evidence)
    neutral_share = sum(1 for item in evidence if getattr(item, "stance", "NEUTRAL") == "NEUTRAL") / n
    low_similarity_share = sum(
        1 for item in evidence if getattr(item, "semantic_similarity", 0.0) < 0.40
    ) / n
    short_share = sum(
        1 for item in evidence if len(getattr(item, "snippet", "").strip()) < 80
    ) / n
    return round(
        min(1.0, 0.50 * neutral_share + 0.35 * low_similarity_share + 0.15 * short_share),
        4,
    )


def compute_adversarial_risk(
    claim: str,
    evidence: List,
    top_domain_share: float,
    opinionated_count: int,
) -> dict:
    """Return explainable adversarial-risk components."""
    focus = evidence if evidence else []
    denom = max(opinionated_count, len(focus), 1)
    low_credibility_share = sum(
        1 for item in focus if getattr(item, "credibility", 0.0) < 0.55
    ) / denom
    evidence_noise = compute_evidence_noise(focus)
    claim_style_risk = compute_claim_style_risk(claim)
    domain_concentration = max(0.0, min(1.0, top_domain_share))
    adversarial_risk = (
        0.35 * claim_style_risk
        + 0.25 * low_credibility_share
        + 0.20 * domain_concentration
        + 0.20 * evidence_noise
    )

    return {
        "claim_style_risk": round(claim_style_risk, 4),
        "low_credibility_share": round(low_credibility_share, 4),
        "domain_concentration": round(domain_concentration, 4),
        "evidence_noise": round(evidence_noise, 4),
        "adversarial_risk": round(min(1.0, adversarial_risk), 4),
    }
