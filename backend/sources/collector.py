"""
backend/sources/collector.py
-------------------------------
Evidence collection from multiple FREE OSINT sources, in parallel.

FIX LOG:
  - Added `build_async_client()` async context manager — runtime.py imports
    it but it never existed, causing an ImportError.
  - Added `collect_evidence_stage(claim, stage, max_per_source, client)`
    which runtime.py calls for staged (2-pass) retrieval:
      Stage 1: Wikipedia + FactCheck + NewsAPI  (high credibility, fast)
      Stage 2: GDELT + DuckDuckGo + Reddit + SERP  (broader coverage)
    The shared `client` parameter lets the caller reuse a single
    httpx.AsyncClient across both stages (connection-pool efficiency).
"""

import asyncio
import hashlib
import logging
import re
import urllib.parse
from contextlib import asynccontextmanager
from typing import List, Optional

import httpx

from config import settings
from models import EvidenceItem
from credibility import get_credibility_score
from services.circuit_breaker import get_breaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

_WIKI_UA = settings.wikipedia_user_agent

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
# FIX: new async context manager — was imported by runtime.py but missing
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def build_async_client():
    """
    Shared httpx.AsyncClient for staged evidence collection.
    runtime.py uses:
        async with build_async_client() as client:
            stage1 = await collect_evidence_stage(claim, 1, client=client)
            stage2 = await collect_evidence_stage(claim, 2, client=client)
    """
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers=_SCRAPE_HEADERS,
        follow_redirects=True,
    ) as client:
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# FIX: staged collection — was imported by runtime.py but missing
# ─────────────────────────────────────────────────────────────────────────────

async def collect_evidence_stage(
    claim: str,
    stage: int,
    max_per_source: Optional[int] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[EvidenceItem]:
    """
    Two-pass retrieval strategy used by pipeline/runtime.py:

    Stage 1 — high-credibility, low-latency sources:
        Wikipedia, Google Fact Check, NewsAPI
    Stage 2 — broader coverage sources:
        GDELT, DuckDuckGo, Reddit, SERP API

    The caller typically checks the Stage-1 aggregation result; if
    confidence is already decisive it skips Stage 2 entirely.
    """
    max_r = max_per_source or settings.evidence_max_articles

    if stage == 1:
        tasks = [
            _wikipedia(claim, max_r),
            _factcheck(claim, max_r),
            _newsapi(claim, max_r),
        ]
    else:
        tasks = [
            _gdelt(claim, max_r),
            _duckduckgo(claim, max_r),
            _reddit(claim, max_r),
            _serpapi(claim, max_r),
        ]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=settings.gather_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[Collector] Stage {stage} timeout")
        results = []

    items: List[EvidenceItem] = []
    for r in results:
        if isinstance(r, list):
            items.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"[Collector] Stage {stage} task error: {r}")

    return _dedup(items)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&#39;", "'")
            .replace("&quot;", '"')
            .strip()
    )


def _top_sentences(text: str, n: int = None) -> str:
    n = n or settings.evidence_max_sentences
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:n]).strip()


def _dedup(items: List[EvidenceItem]) -> List[EvidenceItem]:
    by_url: dict = {}
    for item in sorted(items, key=lambda e: e.credibility, reverse=True):
        url_key = hashlib.md5(item.url.lower().strip("/").encode()).hexdigest()
        if url_key not in by_url:
            by_url[url_key] = item
    return list(by_url.values())


def _build_item(
    title: str,
    snippet: str,
    url: str,
    source: str,
    cred_override: float = None,
) -> EvidenceItem:
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
# SOURCE 1: Wikipedia
# ─────────────────────────────────────────────────────────────────────────────

async def _wikipedia(claim: str, max_results: int) -> List[EvidenceItem]:
    breaker = get_breaker("wikipedia", fail_max=5, reset_timeout=120)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            headers = {"User-Agent": _WIKI_UA}
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
                search_resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query", "list": "search",
                        "srsearch": claim[:200], "srlimit": max_results,
                        "srwhat": "text", "format": "json",
                    },
                )
                search_resp.raise_for_status()
                hits = search_resp.json().get("query", {}).get("search", [])
                if not hits:
                    return results

                page_ids = "|".join(str(h["pageid"]) for h in hits[:max_results])
                extract_resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query", "pageids": page_ids,
                        "prop": "extracts|info", "exintro": True,
                        "explaintext": True, "inprop": "url", "format": "json",
                    },
                )
                extract_resp.raise_for_status()
                pages = extract_resp.json().get("query", {}).get("pages", {})

                for hit in hits[:max_results]:
                    pid = str(hit["pageid"])
                    page = pages.get(pid, {})
                    extract = page.get("extract", "") or hit.get("snippet", "")
                    url = page.get("fullurl") or (
                        f"https://en.wikipedia.org/wiki/"
                        f"{urllib.parse.quote(hit['title'].replace(' ', '_'))}"
                    )
                    results.append(_build_item(hit["title"], extract[:2000], url, "Wikipedia", 0.65))
    except CircuitBreakerOpenError:
        logger.warning("[Wikipedia] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[Wikipedia] Error: {e}")
    logger.info(f"[Wikipedia] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2: Google Fact Check
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
                            f"{publisher}: {rating}", snippet, url, publisher, 0.93
                        ))
    except CircuitBreakerOpenError:
        logger.warning("[FactCheck] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[FactCheck] Error: {e}")
    logger.info(f"[FactCheck] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 3: GDELT
# ─────────────────────────────────────────────────────────────────────────────

async def _gdelt(claim: str, max_results: int) -> List[EvidenceItem]:
    if not settings.gdelt_enabled:
        return []
    breaker = get_breaker("gdelt", fail_max=3, reset_timeout=60)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_SCRAPE_HEADERS) as client:
                resp = await client.get(
                    "https://api.gdeltproject.org/api/v2/doc/doc",
                    params={
                        "query": claim[:200], "mode": "artlist",
                        "maxrecords": max_results, "format": "json",
                        "sort": "DateDesc", "sourcelang": "english",
                    },
                )
                if resp.status_code != 200:
                    return results
                for article in (resp.json().get("articles") or [])[:max_results]:
                    url = article.get("url", "")
                    title = article.get("title", "")
                    source = article.get("domain", "GDELT")
                    if not url or not title:
                        continue
                    seen = article.get("seendate", "")
                    snippet = f"{title}. Reported by {source}. Indexed: {seen[:8]}."
                    results.append(_build_item(title, snippet, url, source))
    except CircuitBreakerOpenError:
        logger.warning("[GDELT] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[GDELT] Error: {e}")
    logger.info(f"[GDELT] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 4: NewsAPI
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
                        "q": claim[:100], "language": "en",
                        "sortBy": "relevancy", "pageSize": max_results,
                        "apiKey": api_key,
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
                        title, snippet, url,
                        article.get("source", {}).get("name", "NewsAPI"),
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[NewsAPI] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[NewsAPI] Error: {e}")
    logger.info(f"[NewsAPI] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 5: DuckDuckGo
# ─────────────────────────────────────────────────────────────────────────────

async def _duckduckgo(claim: str, max_results: int) -> List[EvidenceItem]:
    if not settings.ddg_enabled:
        return []
    breaker = get_breaker("duckduckgo", fail_max=5, reset_timeout=120)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, headers=_SCRAPE_HEADERS, follow_redirects=True
            ) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": claim[:200], "kl": "us-en"},
                )
                if resp.status_code != 200:
                    return results
                blocks = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
                    r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                    resp.text,
                    re.DOTALL,
                )
                for url_enc, title_html, snippet_html in blocks[:max_results]:
                    url = _extract_ddg_url(url_enc)
                    title = _strip_html(title_html)
                    snippet = _strip_html(snippet_html)
                    if not url or not title:
                        continue
                    results.append(_build_item(title, snippet, url, "DuckDuckGo"))
    except CircuitBreakerOpenError:
        logger.warning("[DDG] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[DDG] Error: {e}")
    logger.info(f"[DDG] {len(results)} items")
    return results


def _extract_ddg_url(raw: str) -> str:
    try:
        parsed = urllib.parse.urlparse(raw)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
        return urllib.parse.unquote(raw)
    except Exception:
        return raw


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 6: Reddit
# ─────────────────────────────────────────────────────────────────────────────

async def _reddit(claim: str, max_results: int) -> List[EvidenceItem]:
    if not settings.reddit_enabled:
        return []
    reddit_ua = f"OSINT-Verify/1.0 Python/httpx (research; contact {settings.wikipedia_email})"
    breaker = get_breaker("reddit", fail_max=3, reset_timeout=120)
    results: List[EvidenceItem] = []
    try:
        async with breaker:
            keywords = " ".join(claim.split()[:6])
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                headers={"User-Agent": reddit_ua},
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    "https://www.reddit.com/search.json",
                    params={"q": keywords, "sort": "relevance", "t": "month", "limit": max_results * 2},
                )
                if resp.status_code != 200:
                    return results
                for post in (resp.json().get("data", {}).get("children", []))[:max_results]:
                    pd = post.get("data", {})
                    title = pd.get("title", "")
                    url = pd.get("url", "")
                    if not title or not url or pd.get("score", 0) < 5:
                        continue
                    sub = pd.get("subreddit", "")
                    snippet = f"Reddit r/{sub} — {title}. Upvotes: {pd.get('score', 0)}. {pd.get('selftext','')[:300]}"
                    results.append(_build_item(
                        f"[Reddit r/{sub}] {title}", snippet,
                        f"https://reddit.com{pd.get('permalink', '')}",
                        f"Reddit r/{sub}", 0.30,
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[Reddit] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[Reddit] Error: {e}")
    logger.info(f"[Reddit] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 7: SERP API
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
                        "q": claim[:100], "api_key": api_key,
                        "engine": "google", "num": max_results, "hl": "en",
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
                        title, snippet, url,
                        r.get("source") or urllib.parse.urlparse(url).netloc,
                    ))
    except CircuitBreakerOpenError:
        logger.warning("[SERP] Circuit OPEN")
    except Exception as e:
        logger.warning(f"[SERP] Error: {e}")
    logger.info(f"[SERP] {len(results)} items")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

async def _offline_fallback(claim: str) -> List[EvidenceItem]:
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
    Used by the compatibility shim in main.py and tasks.py.
    """
    max_r = max_per_source or settings.evidence_max_articles

    logger.info(
        f"[Collector] Claim: '{claim[:60]}' | "
        f"offline={settings.offline_mode} | max_per_source={max_r}"
    )

    if settings.offline_mode:
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

    tasks = [
        asyncio.create_task(_wikipedia(claim, max_r),  name="wikipedia"),
        asyncio.create_task(_factcheck(claim, max_r),  name="factcheck"),
        asyncio.create_task(_gdelt(claim, max_r),      name="gdelt"),
        asyncio.create_task(_newsapi(claim, max_r),    name="newsapi"),
        asyncio.create_task(_duckduckgo(claim, max_r), name="duckduckgo"),
        asyncio.create_task(_reddit(claim, max_r),     name="reddit"),
        asyncio.create_task(_serpapi(claim, max_r),    name="serpapi"),
    ]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=settings.gather_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[Collector] Gather timeout ({settings.gather_timeout_seconds}s)")
        results = [
            t.result() if not t.cancelled() and not t.exception() else []
            for t in tasks
        ]

    all_items = []
    for r in results:
        if isinstance(r, list):
            all_items.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"[Collector] Task error: {r}")

    deduped = _dedup(all_items)
    deduped.sort(key=lambda e: e.credibility, reverse=True)

    logger.info(
        f"[Collector] Total before dedup: {len(all_items)} | After dedup: {len(deduped)}"
    )
    return deduped