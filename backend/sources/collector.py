"""
backend/sources/collector.py
-------------------------------
Evidence collection from multiple FREE OSINT sources, in parallel.

Sources (in priority order):
  1. Wikipedia API          — free, no key, REQUIRED email in User-Agent
  2. Google Fact Check API  — free, key optional
  3. GDELT Project          — free, no key, global news
  4. NewsAPI                — free tier 100 req/day, key optional
  5. DuckDuckGo             — free, no key, HTML scrape
  6. Reddit JSON API        — free, no key, signal detection only
  7. SERP API               — optional paid fallback

Circuit breakers protect every external call.
Offline mode uses Wikipedia + Redis cache only.
"""

import asyncio
import hashlib
import logging
import re
import urllib.parse
from typing import List, Optional

import httpx

from config import settings
from models import EvidenceItem
from credibility import get_credibility_score
from services.circuit_breaker import get_breaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

# ── Wikipedia User-Agent (REQUIRED by ToS) ────────────────────────────────────
_WIKI_UA = settings.wikipedia_user_agent    # "(omapar0123@gmail.com)"

# ── Common browser-like headers for scraping ──────────────────────────────────
_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = settings.http_request_timeout_seconds


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
    return text.strip()


def _top_sentences(text: str, n: int = None) -> str:
    """Return the first N sentences of text."""
    n = n or settings.evidence_max_sentences
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:n]).strip()


def _dedup(items: List[EvidenceItem]) -> List[EvidenceItem]:
    """
    Remove duplicate URLs, keeping the item with highest credibility.
    Also dedup on snippet content (prevent same text from different URL paths).
    """
    by_url: dict = {}
    for item in sorted(items, key=lambda e: e.credibility, reverse=True):
        url_key = hashlib.md5(item.url.lower().strip("/").encode()).hexdigest()
        if url_key not in by_url:
            by_url[url_key] = item
    return list(by_url.values())


def _build_item(title: str, snippet: str, url: str, source: str, cred_override: float = None) -> EvidenceItem:
    """Build an EvidenceItem, computing credibility from URL if not overridden."""
    cred = cred_override if cred_override is not None else get_credibility_score(url, source)
    snippet = _top_sentences(_strip_html(snippet))
    return EvidenceItem(
        title=title[:200],
        snippet=snippet[:1000],
        url=url,
        source=source,
        credibility=cred,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1: Wikipedia API
# Mandatory User-Agent: "OSINT-Verify/1.0 (omapar0123@gmail.com)"
# ─────────────────────────────────────────────────────────────────────────────

async def _wikipedia(claim: str, max_results: int) -> List[EvidenceItem]:
    """
    Wikipedia OpenSearch + TextExtracts API.
    User-Agent is REQUIRED by Wikipedia ToS — uses email from config.
    """
    breaker = get_breaker("wikipedia", fail_max=5, reset_timeout=120)
    results: List[EvidenceItem] = []

    try:
        async with breaker:
            headers = {"User-Agent": _WIKI_UA}
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:

                # Step 1: Search for relevant pages
                search_resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action":   "query",
                        "list":     "search",
                        "srsearch": claim[:200],
                        "srlimit":  max_results,
                        "srwhat":   "text",
                        "format":   "json",
                    },
                )
                search_resp.raise_for_status()
                search_data = search_resp.json()
                hits = search_data.get("query", {}).get("search", [])

                if not hits:
                    return results

                # Step 2: Fetch page extracts for richer snippets
                page_ids = "|".join(str(h["pageid"]) for h in hits[:max_results])
                extract_resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action":      "query",
                        "pageids":     page_ids,
                        "prop":        "extracts|info",
                        "exintro":     True,
                        "explaintext": True,
                        "inprop":      "url",
                        "format":      "json",
                    },
                )
                extract_resp.raise_for_status()
                extract_data = extract_resp.json()
                pages = extract_data.get("query", {}).get("pages", {})

                for hit in hits[:max_results]:
                    pid = str(hit["pageid"])
                    page = pages.get(pid, {})
                    extract = page.get("extract", "") or hit.get("snippet", "")
                    url = page.get("fullurl") or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(hit['title'].replace(' ', '_'))}"
                    results.append(_build_item(
                        title=hit["title"],
                        snippet=extract[:2000],
                        url=url,
                        source="Wikipedia",
                        cred_override=0.65,
                    ))

    except CircuitBreakerOpenError:
        logger.warning("[Wikipedia] Circuit OPEN — skipping")
    except Exception as e:
        logger.warning(f"[Wikipedia] Error: {e}")

    logger.info(f"[Wikipedia] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2: Google Fact Check API
# ─────────────────────────────────────────────────────────────────────────────

async def _factcheck(claim: str, max_results: int) -> List[EvidenceItem]:
    api_key = settings.google_factcheck_api_key
    if not api_key:
        return []

    breaker = get_breaker("factcheck", fail_max=3, reset_timeout=60)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                    params={"query": claim[:200], "key": api_key, "pageSize": max_results},
                )
                data = resp.json()
                for ci in data.get("claims", []):
                    for review in ci.get("claimReview", []):
                        publisher = review.get("publisher", {}).get("name", "Fact Checker")
                        rating = review.get("textualRating", "Unknown")
                        url = review.get("url", "")
                        if not url:
                            continue
                        snippet = (
                            f"Fact-check by {publisher}: Rating = '{rating}'. "
                            f"Claim reviewed: {ci.get('text', '')[:200]}"
                        )
                        results.append(_build_item(
                            title=f"{publisher}: {rating}",
                            snippet=snippet,
                            url=url,
                            source=publisher,
                            cred_override=0.93,
                        ))
    except CircuitBreakerOpenError:
        logger.warning("[FactCheck] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[FactCheck] Error: {e}")

    logger.info(f"[FactCheck] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 3: GDELT Project (free, no key — global news monitoring)
# ─────────────────────────────────────────────────────────────────────────────

async def _gdelt(claim: str, max_results: int) -> List[EvidenceItem]:
    """
    GDELT 2.0 Article Search API — free, no API key required.
    Searches global multilingual news coverage with tone/source metadata.
    """
    if not settings.gdelt_enabled:
        return []

    breaker = get_breaker("gdelt", fail_max=3, reset_timeout=60)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            query = urllib.parse.quote(claim[:200])
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_SCRAPE_HEADERS) as client:
                resp = await client.get(
                    "https://api.gdeltproject.org/api/v2/doc/doc",
                    params={
                        "query":      claim[:200],
                        "mode":       "artlist",
                        "maxrecords": max_results,
                        "format":     "json",
                        "sort":       "DateDesc",
                        "sourcelang": "english",
                    },
                )
                if resp.status_code != 200:
                    return results

                data = resp.json()
                for article in (data.get("articles") or [])[:max_results]:
                    url = article.get("url", "")
                    title = article.get("title", "")
                    source = article.get("domain", "GDELT")
                    if not url or not title:
                        continue

                    # Derive snippet from seendate + socialimage alt text
                    seen = article.get("seendate", "")
                    snippet = f"{title}. Reported by {source}. Indexed: {seen[:8]}."

                    results.append(_build_item(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source=source,
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[GDELT] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[GDELT] Error: {e}")

    logger.info(f"[GDELT] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 4: NewsAPI (free tier — 100 req/day)
# ─────────────────────────────────────────────────────────────────────────────

async def _newsapi(claim: str, max_results: int) -> List[EvidenceItem]:
    api_key = settings.news_api_key
    if not api_key:
        return []

    breaker = get_breaker("newsapi", fail_max=3, reset_timeout=60)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q":        claim[:100],
                        "language": "en",
                        "sortBy":   "relevancy",
                        "pageSize": max_results,
                        "apiKey":   api_key,
                    },
                )
                data = resp.json()
                if data.get("status") != "ok":
                    logger.warning(f"[NewsAPI] Error: {data.get('message')}")
                    return []

                for article in (data.get("articles") or [])[:max_results]:
                    url = article.get("url", "")
                    title = article.get("title", "")
                    if not url or not title or title == "[Removed]":
                        continue
                    snippet = article.get("description") or article.get("content") or ""
                    results.append(_build_item(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source=article.get("source", {}).get("name", "NewsAPI"),
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[NewsAPI] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[NewsAPI] Error: {e}")

    logger.info(f"[NewsAPI] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 5: DuckDuckGo HTML Search (no API key, no rate limit)
# ─────────────────────────────────────────────────────────────────────────────

async def _duckduckgo(claim: str, max_results: int) -> List[EvidenceItem]:
    """
    DuckDuckGo HTML results scraper — no API key needed.
    Parses the HTML results page to extract title + snippet + URL.
    """
    if not settings.ddg_enabled:
        return []

    breaker = get_breaker("duckduckgo", fail_max=5, reset_timeout=120)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                headers=_SCRAPE_HEADERS,
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": claim[:200], "kl": "us-en"},
                )

                if resp.status_code != 200:
                    return results

                html = resp.text

                # Extract result blocks  <div class="result__body">
                blocks = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
                    r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL,
                )

                for url_enc, title_html, snippet_html in blocks[:max_results]:
                    # DDG wraps URLs in redirects — extract the real URL
                    url = _extract_ddg_url(url_enc)
                    title = _strip_html(title_html)
                    snippet = _strip_html(snippet_html)
                    if not url or not title:
                        continue
                    results.append(_build_item(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source="DuckDuckGo",
                    ))

    except CircuitBreakerOpenError:
        logger.warning("[DDG] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[DDG] Error: {e}")

    logger.info(f"[DDG] {len(results)} items")
    return results


def _extract_ddg_url(raw: str) -> str:
    """Parse the uddg= param from DDG redirect URLs."""
    try:
        parsed = urllib.parse.urlparse(raw)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
        return urllib.parse.unquote(raw)
    except Exception:
        return raw


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 6: Reddit JSON API (public — no key needed)
# Used for social signal detection — NOT a truth source (credibility = 0.30)
# ─────────────────────────────────────────────────────────────────────────────

_REDDIT_SUBS = ["worldnews", "news", "factcheck", "skeptic", "science"]

async def _reddit(claim: str, max_results: int) -> List[EvidenceItem]:
    """
    Reddit public JSON API — signals what the crowd is discussing.
    Low credibility weight; useful for detecting viral/trending misinformation.
    """
    if not settings.reddit_enabled:
        return []

    # Reddit bars generic UA; use a descriptive one
    reddit_ua = f"OSINT-Verify/1.0 Python/httpx (research; contact {settings.wikipedia_email})"
    breaker = get_breaker("reddit", fail_max=3, reset_timeout=120)
    results: List[EvidenceItem] = []

    try:
        async with breaker:
            keywords = " ".join(claim.split()[:6])    # first 6 words
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                headers={"User-Agent": reddit_ua},
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    "https://www.reddit.com/search.json",
                    params={
                        "q":    keywords,
                        "sort": "relevance",
                        "t":    "month",
                        "limit": max_results * 2,
                    },
                )
                if resp.status_code != 200:
                    return results

                data = resp.json()
                for post in (data.get("data", {}).get("children", []))[:max_results]:
                    pd = post.get("data", {})
                    title = pd.get("title", "")
                    url = pd.get("url", "")
                    selftext = pd.get("selftext", "")[:300]
                    sub = pd.get("subreddit", "")
                    score = pd.get("score", 0)
                    if not title or not url:
                        continue
                    # Only include posts with some upvotes (noise filter)
                    if score < 5:
                        continue
                    snippet = (
                        f"Reddit r/{sub} — {title}. "
                        f"Upvotes: {score}. {selftext}"
                    )
                    results.append(_build_item(
                        title=f"[Reddit r/{sub}] {title}",
                        snippet=snippet,
                        url=f"https://reddit.com{pd.get('permalink', '')}",
                        source=f"Reddit r/{sub}",
                        cred_override=0.30,   # always low — social signal only
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[Reddit] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[Reddit] Error: {e}")

    logger.info(f"[Reddit] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 7: SERP API (optional paid fallback)
# ─────────────────────────────────────────────────────────────────────────────

async def _serpapi(claim: str, max_results: int) -> List[EvidenceItem]:
    api_key = settings.serp_api_key
    if not api_key:
        return []

    breaker = get_breaker("serpapi", fail_max=3, reset_timeout=60)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q":       claim[:100],
                        "api_key": api_key,
                        "engine":  "google",
                        "num":     max_results,
                        "hl":      "en",
                    },
                )
                data = resp.json()
                for r in (data.get("organic_results") or [])[:max_results]:
                    url = r.get("link", "")
                    snippet = r.get("snippet", "")
                    title = r.get("title", "")
                    if not url or not snippet:
                        continue
                    results.append(_build_item(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source=r.get("source") or urllib.parse.urlparse(url).netloc,
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[SERP] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[SERP] Error: {e}")

    logger.info(f"[SERP] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE FALLBACK — Redis cache
# ─────────────────────────────────────────────────────────────────────────────

async def _offline_fallback(claim: str) -> List[EvidenceItem]:
    """
    When OFFLINE_MODE=true, reconstruct EvidenceItems from the
    last cached result for this claim.
    """
    try:
        from cache.redis_client import get_cached_result
        cached = await get_cached_result(claim)
        if not cached:
            return []
        items = []
        for s in cached.get("sources", [])[:5]:
            items.append(EvidenceItem(
                title=s.get("name", "Cached source"),
                snippet=cached.get("explanation", "Cached evidence.")[:500],
                url=s.get("url", ""),
                source=s.get("name", "cache"),
                credibility=float(s.get("credibility", 0.5)),
            ))
        logger.info(f"[Offline] {len(items)} items from cache")
        return items
    except Exception as e:
        logger.warning(f"[Offline] Cache fallback error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

async def collect_all_evidence(
    claim: str,
    max_per_source: Optional[int] = None,
) -> List[EvidenceItem]:
    """
    Gather evidence from all free OSINT sources in parallel.

    Source priority:
      Tier 1: Wikipedia + FactCheck → highest credibility
      Tier 2: GDELT + NewsAPI       → medium credibility  
      Tier 3: DuckDuckGo            → general web
      Tier 4: Reddit                → social signal only (low credibility)

    Offline mode: Wikipedia + Redis cache only.
    """
    max_r = max_per_source or settings.evidence_max_articles

    logger.info(
        f"[Collector] Claim: '{claim[:60]}' | "
        f"offline={settings.offline_mode} | max_per_source={max_r}"
    )

    if settings.offline_mode:
        logger.info("[Collector] OFFLINE MODE")
        wiki, cached = await asyncio.gather(
            _wikipedia(claim, max_r),
            _offline_fallback(claim),
            return_exceptions=True,
        )
        all_items: List[EvidenceItem] = []
        for r in [wiki, cached]:
            if isinstance(r, list):
                all_items.extend(r)
        return _dedup(all_items)

    # Run all sources in parallel
    tasks = [
        asyncio.create_task(_wikipedia(claim, max_r),    name="wikipedia"),
        asyncio.create_task(_factcheck(claim, max_r),    name="factcheck"),
        asyncio.create_task(_gdelt(claim, max_r),        name="gdelt"),
        asyncio.create_task(_newsapi(claim, max_r),      name="newsapi"),
        asyncio.create_task(_duckduckgo(claim, max_r),   name="duckduckgo"),
        asyncio.create_task(_reddit(claim, max_r),       name="reddit"),
        asyncio.create_task(_serpapi(claim, max_r),      name="serpapi"),
    ]

    # Wait with a total gather timeout
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=settings.gather_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[Collector] Gather timeout ({settings.gather_timeout_seconds}s)")
        results = [t.result() if not t.cancelled() and not t.exception() else [] for t in tasks]

    all_items = []
    for r in results:
        if isinstance(r, list):
            all_items.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"[Collector] Task error: {r}")

    deduped = _dedup(all_items)

    logger.info(
        f"[Collector] Total before dedup: {len(all_items)} | "
        f"After dedup: {len(deduped)}"
    )

    # Sort: Tier 1 first (highest credibility)
    deduped.sort(key=lambda e: e.credibility, reverse=True)

    return deduped
