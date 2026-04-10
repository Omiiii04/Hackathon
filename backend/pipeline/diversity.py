"""
backend/pipeline/diversity.py
--------------------------------
Helpers for deterministic domain diversity analysis.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Iterable, List
from urllib.parse import urlparse


_TEXT_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MULTI_PART_TLDS = {
    "co.uk",
    "org.uk",
    "gov.uk",
    "ac.uk",
    "co.in",
    "org.in",
    "gov.in",
    "co.jp",
    "com.au",
}


def extract_domain(url: str) -> str:
    """Return lower-cased hostname without common mobile prefixes."""
    if not url:
        return ""
    raw = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    raw = raw.split("@")[-1].split(":")[0]
    for prefix in ("www.", "m.", "mobile.", "amp."):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    return raw


def root_domain(domain: str) -> str:
    """Reduce a hostname to its registrable root in a lightweight, offline-safe way."""
    if not domain:
        return ""
    parts = [p for p in domain.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    tail = ".".join(parts[-2:])
    tail3 = ".".join(parts[-3:])
    if tail in _MULTI_PART_TLDS and len(parts) >= 3:
        return tail3
    return tail


def annotate_domains(evidence: Iterable) -> None:
    """Populate domain and root_domain fields in-place."""
    for item in evidence:
        domain = extract_domain(getattr(item, "url", ""))
        item.domain = domain
        item.root_domain = root_domain(domain)


def _fingerprint_text(text: str) -> str:
    tokens = _TEXT_TOKEN_RE.findall((text or "").lower())
    trimmed = " ".join(tokens[:40])
    return hashlib.md5(trimmed.encode("utf-8")).hexdigest()


def dedupe_evidence(items: List) -> List:
    """
    Remove duplicate URLs and near-duplicate same-domain snippets.
    Keeps the highest-credibility, longest-snippet candidate.
    """
    if not items:
        return []

    annotate_domains(items)
    best_by_key = {}
    for item in sorted(
        items,
        key=lambda ev: (
            getattr(ev, "credibility", 0.0),
            len(getattr(ev, "snippet", "")),
            len(getattr(ev, "title", "")),
        ),
        reverse=True,
    ):
        url_key = getattr(item, "url", "").lower().rstrip("/")
        text_key = _fingerprint_text(
            f"{getattr(item, 'title', '')} {getattr(item, 'snippet', '')}"
        )
        dedupe_key = (
            item.root_domain or item.domain or "unknown",
            url_key or text_key,
            text_key,
        )
        if dedupe_key not in best_by_key:
            best_by_key[dedupe_key] = item

    deduped = list(best_by_key.values())
    annotate_domains(deduped)
    apply_independence_factors(deduped)
    return deduped


def apply_independence_factors(evidence: Iterable) -> Counter:
    """Annotate each item with an independence factor based on root-domain repetition."""
    annotate_domains(evidence)
    counts = Counter(
        getattr(item, "root_domain", "") or getattr(item, "domain", "") or "unknown"
        for item in evidence
    )
    for item in evidence:
        root = getattr(item, "root_domain", "") or getattr(item, "domain", "") or "unknown"
        item.independence_factor = round(1.0 / math.sqrt(max(counts[root], 1)), 4)
    return counts


def compute_diversity_metrics(evidence: List) -> dict:
    """Return domain-diversity metrics for explainable verdicting."""
    if not evidence:
        return {
            "independent_domains": 0,
            "top_domain_share": 1.0,
            "diversity_score": 0.0,
            "domain_counts": {},
        }

    annotate_domains(evidence)
    counts = Counter(
        getattr(item, "root_domain", "") or getattr(item, "domain", "") or "unknown"
        for item in evidence
    )
    total = sum(counts.values()) or 1
    top_share = max(counts.values()) / total
    independent_domains = len(counts)
    return {
        "independent_domains": independent_domains,
        "top_domain_share": round(top_share, 4),
        "diversity_score": round(min(independent_domains / 4.0, 1.0), 4),
        "domain_counts": dict(counts),
    }
