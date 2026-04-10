"""
backend/pipeline/claim_parser.py
----------------------------------
Upgraded claim parser: spaCy NLP + entity extraction + compound splitting.
Returns a structured ParsedClaim dataclass.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── spaCy lazy load ───────────────────────────────────────────────────────────
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
            logger.info("[Parser] spaCy en_core_web_sm loaded ✅")
        except Exception as e:
            logger.warning(f"[Parser] spaCy unavailable ({e}), using fallback")
            _nlp = False
    return _nlp


# ── Claim type detection ──────────────────────────────────────────────────────
_BREAKING_KW = re.compile(
    r"\b(breaks?|breaking|just in|alert|urgent|developing|exclusive)\b", re.I
)
_SCIENTIFIC_KW = re.compile(
    r"\b(study|research|scientist|vaccine|virus|data|trial|experiment|survey|lab|genome|mutation|cancer)\b",
    re.I,
)
_POLITICAL_KW = re.compile(
    r"\b(government|president|minister|election|parliament|senate|congress|policy|law|bill|vote|sanction|treaty)\b",
    re.I,
)
_HEALTH_KW = re.compile(
    r"\b(hospital|patient|drug|dose|symptoms|disease|pandemic|epidemic|outbreak)\b", re.I
)

# Conjunction patterns for compound detection
_COMPOUND_SEPS = re.compile(
    r"\s+(?:and|but|while|also|moreover|furthermore|additionally)\s+", re.I
)


@dataclass
class ParsedClaim:
    text: str
    entities: List[dict] = field(default_factory=list)   # [{text, label}, ...]
    intent: str = "assertion"                              # assertion, question, speculation
    claim_type: str = "general"
    sub_claims: List[str] = field(default_factory=list)
    is_compound: bool = False
    keywords: List[str] = field(default_factory=list)


def detect_claim_type(text: str, hint: str = "general") -> str:
    """Return best-guess claim type label."""
    if hint and hint not in ("general", "auto"):
        return hint
    if _BREAKING_KW.search(text):
        return "breaking_news"
    if _SCIENTIFIC_KW.search(text):
        return "scientific"
    if _POLITICAL_KW.search(text):
        return "political"
    if _HEALTH_KW.search(text):
        return "health"
    return "general"


def split_compound_claim(claim: str) -> List[str]:
    """
    Split compound claims into atomic sub-claims.

    Example:
        "Iran lost the war and Russia surrendered"
        → ["Iran lost the war", "Russia surrendered"]
    """
    # Phase 1: sentence-boundary split
    parts = [claim]
    for sep in [". ", "; "]:
        new_parts = []
        for part in parts:
            split = part.split(sep)
            if len(split) > 1 and all(len(s.strip()) > 12 for s in split):
                new_parts.extend([s.strip() for s in split])
            else:
                new_parts.append(part)
        parts = new_parts

    # Phase 2: conjunction split
    final = []
    for part in parts:
        matches = _COMPOUND_SEPS.split(part)
        if len(matches) > 1 and all(len(m.strip()) > 12 for m in matches):
            final.extend([m.strip() for m in matches])
        else:
            final.append(part)

    return [p for p in final if len(p.strip()) > 5]


def detect_intent(text: str) -> str:
    """Detect whether the claim is an assertion, question, or speculation."""
    stripped = text.strip()
    if stripped.endswith("?"):
        return "question"
    if re.search(r"\b(allegedly|reportedly|claimed|rumoured|might|could|may|possibly)\b", stripped, re.I):
        return "speculation"
    return "assertion"


def parse_claim(text: str, claim_type_hint: str = "general") -> ParsedClaim:
    """
    Full claim parsing pipeline:
      1. spaCy NER — extract entities
      2. Claim type detection
      3. Intent detection
      4. Compound splitting
      5. Keyword extraction
    """
    text = text.strip()
    entities = []
    keywords = []

    nlp = _get_nlp()
    if nlp:
        doc = nlp(text)

        # Named entities
        entities = [
            {"text": ent.text, "label": ent.label_}
            for ent in doc.ents
            if ent.label_ in {
                "PERSON", "ORG", "GPE", "LOC", "NORP",
                "EVENT", "FAC", "LAW", "DATE",
            }
        ]

        # Keywords: nouns, proper nouns, verbs (lemmatized)
        keywords = list({
            token.lemma_.lower()
            for token in doc
            if token.pos_ in {"NOUN", "PROPN", "VERB"}
            and not token.is_stop
            and len(token.text) > 2
        })[:10]

    else:
        # Minimal fallback without spaCy
        keywords = [
            w.lower() for w in text.split()
            if len(w) > 4 and w.isalpha()
        ][:10]

    sub_claims = split_compound_claim(text)
    is_compound = len(sub_claims) > 1

    return ParsedClaim(
        text=text,
        entities=entities,
        intent=detect_intent(text),
        claim_type=detect_claim_type(text, claim_type_hint),
        sub_claims=sub_claims if is_compound else [],
        is_compound=is_compound,
        keywords=keywords,
    )


# ── Backwards-compat shim for old pipeline.py ─────────────────────────────────
def is_compound(claim: str) -> bool:
    return len(split_compound_claim(claim)) > 1
