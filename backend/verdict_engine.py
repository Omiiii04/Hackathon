# backend/verdict_engine.py
import math
from typing import List
from models import EvidenceItem, VerdictResult
from credibility import get_credibility_score, get_credibility_label

# ─────────────────────────────────────────────
# STANCE CLASSIFIER
# ─────────────────────────────────────────────
CONTRADICTING_KEYWORDS = [
    "false", "debunked", "misleading", "misinformation",
    "no evidence", "incorrect", "wrong", "unfounded",
    "fact check", "not true", "disproven", "myth", "hoax",
    "conspiracy", "misidentified", "out of context",
    "misattributed", "manipulated", "doctored", "fabricated",
    "fake news", "baseless", "unsubstantiated", "claim is false",
    "verdict: false", "rating: false", "pants on fire","vaccine misinformation", "health misinformation",
"spread of false", "viral false", "contain no", "no chip",
"no microchip", "does not contain", "scientists say false"
]

SUPPORTING_KEYWORDS = [
    "confirmed", "verified", "true", "accurate", "correct",
    "evidence shows", "study shows", "researchers found",
    "officials confirmed", "announced", "launched successfully",
    "report confirms", "data shows", "science confirms",
    "verdict: true", "rating: true", "mostly true","mission accomplished", "successfully launched",
"confirmed launch", "took off", "lifted off"
]

def classify_stance(snippet: str, title: str) -> str:
    """
    Classifies evidence as SUPPORTING, CONTRADICTING, or NEUTRAL.
    """
    text = f"{snippet} {title}".lower()

    contra_hits  = sum(1 for kw in CONTRADICTING_KEYWORDS if kw in text)
    support_hits = sum(1 for kw in SUPPORTING_KEYWORDS if kw in text)

    if contra_hits > support_hits:   return "CONTRADICTING"
    if support_hits > contra_hits:   return "SUPPORTING"
    return "NEUTRAL"

# ─────────────────────────────────────────────
# RECENCY FACTOR
# ─────────────────────────────────────────────
def recency_factor(published_days_ago: int = 30) -> float:
    """
    More recent = more weight.
    We don't always have publish date, so default to 30 days.
    """
    if published_days_ago <= 1:    return 1.00
    if published_days_ago <= 7:    return 0.90
    if published_days_ago <= 30:   return 0.75
    if published_days_ago <= 365:  return 0.50
    return 0.30

# ─────────────────────────────────────────────
# MAIN VERDICT COMPUTATION
# ─────────────────────────────────────────────
def compute_verdict(evidence: List[EvidenceItem], claim: str) -> VerdictResult:
    # ── Step 1: Not enough evidence ─────────────────────────────────
    if not evidence or len(evidence) < 2:
        return VerdictResult(
            verdict="UNVERIFIED",
            confidence=0.0,
            explanation="",
            support_ratio=0.5,
            evidence_count=0,
            sources=[],
            algorithm_trace={"reason": "insufficient_evidence"}
        )

    # ── Step 2: Score and classify each item ────────────────────────
    for item in evidence:
        item.credibility = get_credibility_score(item.url, item.source)
        item.stance      = classify_stance(item.snippet, item.title)
        
        # FIX: Dynamically fetch days_ago if it exists on the item, else default to 30
        days_ago = getattr(item, 'published_days_ago', 30) 
        item.score = item.credibility * recency_factor(days_ago)

    # ── Step 3: Separate by stance ──────────────────────────────────
    supporting    = [e for e in evidence if e.stance == "SUPPORTING"]
    contradicting = [e for e in evidence if e.stance == "CONTRADICTING"]
    neutral       = [e for e in evidence if e.stance == "NEUTRAL"]

    sup_weight = sum(e.score for e in supporting)
    con_weight = sum(e.score for e in contradicting)
    neu_weight = sum(e.score for e in neutral)

    # ── Step 4: Support ratio ───────────────────────────────────────
    active = sup_weight + con_weight
    ratio  = sup_weight / active if active > 0 else 0.5

    # ── Step 5: Count high-credibility (Tier 1) sources ────────────
    tier1_count = sum(1 for e in evidence if e.credibility >= 0.85)

    # ── Step 6 & 7: Decision table ──────────────────────────────────
    if all(e.credibility < 0.50 for e in evidence):
        verdict = "UNVERIFIED"
    elif active == 0: 
        # FIX: If there is no supporting or contradicting evidence, it's unverified.
        verdict = "UNVERIFIED"
    elif ratio >= 0.75 and tier1_count >= 1:
        verdict = "TRUE"
    elif ratio <= 0.25 and tier1_count >= 1:
        verdict = "FALSE"
    elif 0.40 <= ratio <= 0.60: 
        # FIX: A ~50/50 split implies conflicting data, regardless of tier 1 counts.
        verdict = "CONFLICTING"
    elif 0.25 < ratio < 0.75:
        verdict = "MISLEADING"
    else:
        verdict = "UNVERIFIED"

    # ── Step 8: Confidence (bounded sigmoid) ────────────────────────
    n          = len(evidence)
    avg_cred   = sum(e.credibility for e in evidence) / n
    scale      = 1 - math.exp(-n / 10)   
    confidence = avg_cred * (0.60 + 0.40 * scale)
    confidence = round(min(confidence, 0.95), 2)

    # ── Step 9: Top 3 sources (highest credibility first) ──────────
    top3 = sorted(evidence, key=lambda x: x.credibility, reverse=True)[:3]
    sources_out = [
        {
            "title":       e.title[:100],
            "url":         e.url,
            "source":      e.source,
            "credibility": get_credibility_label(e.credibility),
            "stance":      e.stance
        }
        for e in top3
    ]

    # ── Step 10: Algorithm trace (for judges) ──────────────────────
    trace = {
        "support_ratio":        round(ratio, 3),
        "evidence_count":       n,
        "tier1_count":          tier1_count,
        "supporting_count":     len(supporting),
        "contradicting_count":  len(contradicting),
        "neutral_count":        len(neutral),
        "supporting_weight":    round(sup_weight, 3),
        "contradicting_weight": round(con_weight, 3),
        "avg_credibility":      round(avg_cred, 3),
        "confidence_final":     confidence
    }

    return VerdictResult(
        verdict=verdict,
        confidence=confidence,
        explanation="",         # filled by explainer.py
        support_ratio=round(ratio, 3),
        evidence_count=n,
        sources=sources_out,
        algorithm_trace=trace
    )

# ─────────────────────────────────────────────
# TEST: Run directly
# python verdict_engine.py
# ─────────────────────────────────────────────
# if __name__ == "__main__":
#     from models import EvidenceItem
#     # Mock evidence for testing
#     test_evidence = [
#         EvidenceItem("Reuters: COVID vaccine chips false", "No evidence of microchips", "https://reuters.com/fact-check/1", "Reuters"),
#         EvidenceItem("BBC: Vaccine misinformation", "Claims are debunked by scientists", "https://bbc.com/news/1", "BBC"),
#         EvidenceItem("Wikipedia: COVID-19 vaccine", "mRNA vaccines contain no microchips", "https://en.wikipedia.org/wiki/COVID-19_vaccine", "Wikipedia"),
#     ]
#     result = compute_verdict(test_evidence, "COVID vaccines contain microchips")
#     print(f"Verdict: {result.verdict}")
#     print(f"Confidence: {result.confidence}")
#     print(f"Support ratio: {result.support_ratio}")
#     print(f"Trace: {result.algorithm_trace}")
