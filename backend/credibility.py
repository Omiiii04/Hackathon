"""
backend/credibility.py
------------------------
Source credibility scoring — static table + dynamic DB lookup.

Tier definitions:
  Tier 1  (>= 0.85): Major international news, gov/health bodies, fact-checkers
  Tier 2  (>= 0.55): Respected regional media, encyclopedias
  Tier 3  (>= 0.35): Aggregators, forums with editorial oversight
  Tier 4  (<  0.35): Social media, anonymous blogs
"""
from typing import Optional

# ── Static domain scores ──────────────────────────────────────────────────────
DOMAIN_SCORES: dict = {
    # --- Tier 1: International wire + authoritative bodies ---
    "reuters.com":          0.97,
    "apnews.com":           0.97,
    "bbc.com":              0.95,
    "bbc.co.uk":            0.95,
    "who.int":              0.96,
    "un.org":               0.96,
    "cdc.gov":              0.96,
    "nih.gov":              0.96,
    "nasa.gov":             0.96,
    "nytimes.com":          0.92,
    "theguardian.com":      0.91,
    "washingtonpost.com":   0.90,
    "economist.com":        0.90,
    "ft.com":               0.90,
    # --- Tier 1: Fact-checkers ---
    "snopes.com":           0.93,
    "politifact.com":       0.93,
    "factcheck.org":        0.93,
    "fullfact.org":         0.92,
    "afp.com":              0.94,
    "ap.org":               0.97,
    # --- Tier 1: Academic / Science ---
    "nature.com":           0.95,
    "science.org":          0.95,
    "thelancet.com":        0.94,
    "pubmed.ncbi.nlm.nih.gov": 0.94,
    "scholar.google.com":   0.85,
    # --- Tier 2: Respected regional/national media ---
    "ndtv.com":             0.80,
    "aljazeera.com":        0.80,
    "bloomberg.com":        0.85,
    "thehindu.com":         0.82,
    "timesofindia.com":     0.72,
    "scmp.com":             0.78,
    "dw.com":               0.85,
    "france24.com":         0.82,
    "channelnewsasia.com":  0.80,
    # --- Tier 2: Encyclopedias / Reference ---
    "wikipedia.org":        0.65,
    "britannica.com":       0.80,
    # --- Tier 3: Aggregators ---
    "medium.com":           0.40,
    "substack.com":         0.38,
    # --- Tier 4: Social / forums ---
    "reddit.com":           0.30,
    "twitter.com":          0.25,
    "x.com":                0.25,
    "facebook.com":         0.22,
    "youtube.com":          0.28,
    "tiktok.com":           0.20,
}

# ── Dynamic lookup (DB) ───────────────────────────────────────────────────────
_dynamic_cache: dict = {}   # in-process cache populated on first DB hit


async def get_dynamic_score(domain: str, pool) -> Optional[float]:
    """Fetch from DB, with in-process LRU-style cache."""
    if domain in _dynamic_cache:
        return _dynamic_cache[domain]
    try:
        from db.repository import get_dynamic_credibility
        score = await get_dynamic_credibility(pool, domain)
        if score is not None:
            _dynamic_cache[domain] = score
        return score
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_credibility_score(url: str, source_name: str = "") -> float:
    """
    Return credibility score for a URL/source name.
    Falls back to TLD heuristics, then source name matching.
    Default: 0.40 for unknown sources.
    """
    url_lower = url.lower()
    source_lower = (source_name or "").lower()

    # Domain table lookup
    for domain, score in DOMAIN_SCORES.items():
        if domain in url_lower:
            return score

    # TLD heuristics
    if ".gov" in url_lower:
        return 0.90
    if ".edu" in url_lower:
        return 0.82
    if ".int" in url_lower:
        return 0.90
    if ".org" in url_lower:
        return 0.58

    # Source name fallback
    HIGH_CRED_NAMES = [
        "reuters", "bbc", "ap news", "associated press", "france 24",
        "dw", "al jazeera", "npr", "pbs", "abc news",
    ]
    if any(name in source_lower for name in HIGH_CRED_NAMES):
        return 0.90

    return 0.40  # unknown source


def get_credibility_label(score: float) -> str:
    """Convert numeric score to human-readable label."""
    if score >= 0.85:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


def get_credibility_tier(score: float) -> int:
    """Return tier integer (1=best, 4=worst)."""
    if score >= 0.85:
        return 1
    if score >= 0.55:
        return 2
    if score >= 0.35:
        return 3
    return 4
