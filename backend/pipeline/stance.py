"""
backend/pipeline/stance.py
----------------------------
BART-large-MNLI zero-shot stance classifier.

Model loaded from local path (config.BART_MODEL_PATH),
falling back to HuggingFace cache if local path is invalid.

Labels:
  SUPPORTING    — evidence supports the claim
  CONTRADICTING — evidence contradicts the claim
  NEUTRAL       — evidence is unrelated or ambiguous
"""
import logging
import os
from typing import Tuple

from config import settings

logger = logging.getLogger(__name__)

# ── Singleton stance classifier ───────────────────────────────────────────────
_classifier = None

CANDIDATE_LABELS = [
    "supports the claim",
    "contradicts the claim",
    "neutral or unrelated",
]

LABEL_MAP = {
    "supports the claim": "SUPPORTING",
    "contradicts the claim": "CONTRADICTING",
    "neutral or unrelated": "NEUTRAL",
}

# Confidence threshold: below this → force NEUTRAL
CONFIDENCE_THRESHOLD = 0.45


def _get_classifier():
    global _classifier
    if _classifier is None:
        from transformers import pipeline

        model_path = settings.bart_model_path
        device = settings.bart_device

        # Validate local path
        if not os.path.isdir(model_path):
            logger.warning(
                f"[Stance] Local model path not found: {model_path}. "
                "Falling back to facebook/bart-large-mnli from HuggingFace cache."
            )
            model_path = "facebook/bart-large-mnli"

        logger.info(f"[Stance] Loading BART-MNLI from: {model_path} (device={device})")
        _classifier = pipeline(
            "zero-shot-classification",
            model=model_path,
            device=device,
        )
        logger.info("[Stance] BART-MNLI loaded ✅")

    return _classifier


def warmup():
    """Pre-load BART-MNLI and run one warmup inference to JIT-compile."""
    clf = _get_classifier()
    clf(
        "This is a warmup sentence.",
        CANDIDATE_LABELS,
        hypothesis_template="This text {} that the sky is blue.",
    )
    logger.info("[Stance] Warmup inference complete ✅")


def classify_stance(snippet: str, title: str, claim: str) -> Tuple[str, float]:
    """
    Classify the stance of an evidence snippet with respect to a claim.

    Returns:
        (stance_label, confidence_score)
        stance_label: SUPPORTING | CONTRADICTING | NEUTRAL
        confidence_score: 0.0 – 1.0
    """
    clf = _get_classifier()

    # Combine title + snippet for richer context
    text = f"{title}. {snippet}" if title else snippet
    # Truncate to avoid BART's 1024-token limit (approx. 3800 chars)
    text = text[:1500]

    hypothesis_template = f"This text {{}} that {claim[:200]}."

    try:
        result = clf(text, CANDIDATE_LABELS, hypothesis_template=hypothesis_template)

        top_label = result["labels"][0]
        top_score = result["scores"][0]

        # Confidence too low → NEUTRAL
        if top_score < CONFIDENCE_THRESHOLD:
            return "NEUTRAL", top_score

        stance = LABEL_MAP.get(top_label, "NEUTRAL")
        return stance, round(top_score, 4)

    except Exception as e:
        logger.error(f"[Stance] Classification failed: {e}")
        return "NEUTRAL", 0.0


def classify_stance_bulk(evidence_list: list, claim: str) -> list:
    """
    Classify stance for all evidence items in-place.
    Also stores stance_confidence on each item.
    Returns the same list (mutated).
    """
    for item in evidence_list:
        snippet = getattr(item, "snippet", "")
        title = getattr(item, "title", "")
        stance, confidence = classify_stance(snippet, title, claim)
        item.stance = stance
        item.stance_confidence = confidence

    return evidence_list
