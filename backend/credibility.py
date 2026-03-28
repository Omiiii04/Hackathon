# backend/credibility.py  credibility scroring logic
# Domain → credibility score range from (0.0 to 1.0)

DOMAIN_SCORES = {
    # Tier 1 — 0.90+ (Major news + gov bodies)
    "reuters.com":    0.97,
    "apnews.com":     0.97,
    "bbc.com":        0.95,
    "bbc.co.uk":      0.95,
    "who.int":        0.95,
    "un.org":         0.95,
    "cdc.gov":        0.95,
    "nih.gov":        0.95,
    "nasa.gov":       0.95,
    "nytimes.com":    0.90,
    "theguardian.com":0.90,
    "washingtonpost.com": 0.90,
    "snopes.com":     0.92,
    "politifact.com": 0.92,
    "factcheck.org":  0.92,

    # Tier 2 — 0.70–0.89 (Respected media + encyclopedias)
    "ndtv.com":       0.80,
    "aljazeera.com":  0.80,
    "bloomberg.com":  0.82,
    "thehindu.com":   0.80,
    "timesofindia.com": 0.72,
    "wikipedia.org":  0.65,

    # Tier 3 — 0.50–0.69 (Social media + blogs)
    "medium.com":     0.40,
    "reddit.com":     0.30,
}


def get_credibility_score(url: str, source_name: str) -> float:
    """Return credibility score for a URL/source. Default 0.40 for unknown."""
    url_lower    = url.lower()
    source_lower = source_name.lower()

    # Check domain database
    for domain, score in DOMAIN_SCORES.items():
        if domain in url_lower:
            return score

    # TLD-based heuristics for unknown domains
    if ".gov" in url_lower:   return 0.90
    if ".edu" in url_lower:   return 0.80
    if ".int" in url_lower:   return 0.90
    if ".org" in url_lower:   return 0.55

    # Known fact-checker names
    if any(name in source_lower for name in ["reuters", "bbc", "ap news", "associated press"]):
        return 0.90

    return 0.40  # unknown source


def get_credibility_label(score: float) -> str:
    """Convert score to human-readable label."""
    if score >= 0.85: return "HIGH"
    if score >= 0.55: return "MEDIUM"
    return "LOW"
