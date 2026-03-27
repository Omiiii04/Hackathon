# backend/verdict_engine.py
import math
from typing import List
from transformers import pipeline
from models import EvidenceItem, VerdictResult
from credibility import get_credibility_score, get_credibility_label

# ─────────────────────────────────────────────
# STANCE CLASSIFIER (BART-MNLI)
# ─────────────────────────────────────────────
# Update this to the local folder path where your downloaded model is stored.
# If you used HuggingFace's default caching, you can keep it as "facebook/bart-large-mnli".
LOCAL_MODEL_PATH = r"C:\Users\Admin\Desktop\VIT_Hackathon\models\bart_mnli" 

print(f"[System] Loading BART-MNLI model from: {LOCAL_MODEL_PATH} ...")
stance_classifier = pipeline(
    "zero-shot-classification", 
    model=LOCAL_MODEL_PATH,
    device=-1 # Note: Change to 0 if you have a GPU and PyTorch configured for it
)

def classify_stance(snippet: str, title: str, claim: str) -> str:
    """
    Classifies evidence as SUPPORTING, CONTRADICTING, or NEUTRAL using Zero-Shot NLI.
    """
    text = f"{title}. {snippet}"
    candidate_labels = ["supports the claim", "contradicts the claim", "neutral or unrelated"]
    
    # Test the text against the specific claim
    result = stance_classifier(text, candidate_labels, hypothesis_template=f"This text {{}} that {claim}.")
    
    top_label = result['labels'][0]
    score = result['scores'][0]

    # Confidence threshold: fallback to NEUTRAL if the model isn't highly confident
    if score < 0.50 or "neutral" in top_label:
        return "NEUTRAL"
    elif "supports" in top_label:
        return "SUPPORTING"
    else:
        return "CONTRADICTING"

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
        # Pass the claim into the new BART classifier
        item.stance      = classify_stance(item.snippet, item.title, claim)
        
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
        verdict = "UNVERIFIED"
    elif ratio >= 0.75 and tier1_count >= 1:
        verdict = "TRUE"
    elif ratio <= 0.25 and tier1_count >= 1:
        verdict = "FALSE"
    elif 0.40 <= ratio <= 0.60: 
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

    # ── Step 10: Algorithm trace ──────────────────────
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