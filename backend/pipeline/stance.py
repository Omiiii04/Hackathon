"""
backend/pipeline/stance.py
----------------------------
BART-large-MNLI zero-shot stance classifier.

FIX LOG:
  - classify_stance_bulk() gained a `batch_size` parameter.
    The old code ran the BART pipeline once per evidence item (N calls).
    The fix passes ALL snippets as a list to the pipeline in batches,
    which (a) satisfies the test assertion about call count and
    (b) significantly reduces wall-clock time.
  - Monotonic batch logic: ceil(N / batch_size) invocations total.
"""
import logging
import math
import os
from typing import List, Optional, Tuple

from config import settings

logger = logging.getLogger(__name__)

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

CONFIDENCE_THRESHOLD = 0.45


def _get_classifier():
    global _classifier
    if _classifier is None:
        from transformers import pipeline

        model_path = settings.bart_model_path
        device = settings.bart_device

        if not os.path.isdir(model_path):
            logger.warning(
                f"[Stance] Local model path not found: {model_path}. "
                "Falling back to facebook/bart-large-mnli."
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
    clf = _get_classifier()
    clf(
        "This is a warmup sentence.",
        CANDIDATE_LABELS,
        hypothesis_template="This text {} that the sky is blue.",
    )
    logger.info("[Stance] Warmup inference complete ✅")


def classify_stance(snippet: str, title: str, claim: str) -> Tuple[str, float]:
    """
    Single-item stance classification.
    Returns (stance_label, confidence_score).
    """
    clf = _get_classifier()
    text = f"{title}. {snippet}" if title else snippet
    text = text[:1500]
    hypothesis_template = f"This text {{}} that {claim[:200]}."

    try:
        result = clf(text, CANDIDATE_LABELS, hypothesis_template=hypothesis_template)
        top_label = result["labels"][0]
        top_score = result["scores"][0]

        if top_score < CONFIDENCE_THRESHOLD:
            return "NEUTRAL", top_score

        stance = LABEL_MAP.get(top_label, "NEUTRAL")
        return stance, round(top_score, 4)

    except Exception as e:
        logger.error(f"[Stance] Classification failed: {e}")
        return "NEUTRAL", 0.0


def classify_stance_bulk(
    evidence_list: list,
    claim: str,
    batch_size: Optional[int] = None,
) -> list:
    """
    Classify stance for all evidence items in-place, using batched inference.

    FIX: previously called the pipeline N times (once per item).
    Now sends texts in batches of `batch_size`, reducing model invocations
    to ceil(N / batch_size).  The test asserts exactly this behaviour.

    Parameters
    ----------
    evidence_list : list[EvidenceItem]
    claim         : str
    batch_size    : int, default 8
    """
    if not evidence_list:
        return evidence_list

    batch_size = batch_size or 8
    clf = _get_classifier()
    hypothesis_template = f"This text {{}} that {claim[:200]}."

    # Build flat list of texts
    texts = [
        (
            f"{getattr(item, 'title', '')}. {getattr(item, 'snippet', '')}"
            if getattr(item, "title", "")
            else getattr(item, "snippet", "")
        )[:1500]
        for item in evidence_list
    ]

    # Batch inference
    n = len(texts)
    results: List[dict] = []
    for batch_start in range(0, n, batch_size):
        batch = texts[batch_start : batch_start + batch_size]
        try:
            # Transformers pipeline accepts a list → returns a list of dicts
            batch_results = clf(
                batch,
                CANDIDATE_LABELS,
                hypothesis_template=hypothesis_template,
            )
            # Normalise: single-item input returns a dict, not a list
            if isinstance(batch_results, dict):
                batch_results = [batch_results]
            results.extend(batch_results)
        except Exception as e:
            logger.error(f"[Stance] Batch classification failed: {e}")
            results.extend([None] * len(batch))

    # Assign back to items
    for item, result in zip(evidence_list, results):
        if result is None:
            item.stance = "NEUTRAL"
            item.stance_confidence = 0.0
            continue

        top_label = result["labels"][0]
        top_score = result["scores"][0]

        if top_score < CONFIDENCE_THRESHOLD:
            item.stance = "NEUTRAL"
        else:
            item.stance = LABEL_MAP.get(top_label, "NEUTRAL")

        item.stance_confidence = round(top_score, 4)

    return evidence_list