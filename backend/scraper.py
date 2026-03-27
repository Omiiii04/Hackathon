# backend/scraper.py for scrapping sources in parallel from fact_checker, newsapi and wikipedia
import httpx
import asyncio
import os
from typing import List
from dotenv import load_dotenv
from models import EvidenceItem

load_dotenv()


# ─────────────────────────────────────────────
# SOURCE 01: Wikipedia (free, no API key needed)
# ─────────────────────────────────────────────

async def search_wikipedia(claim: str) -> List[EvidenceItem]:
    """
    Searches Wikipedia for articles related to the claim.
    Returns up to 3 evidence items.
    """
    results = []
    
    # Wikipedia requires authentication
    headers = {
        # Using persional email as verification
        "User-Agent": "MyFactCheckApp/1.0 (omapar22@gmail.com)"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action":   "query",
                    "list":     "search",
                    "srsearch": claim[:200],
                    "srlimit":  3, #Can increase the number of sources
                    "format":   "json"
                }
            )
            
            # raising an exception if we get an errors like 403, 404, 500, etc.
            resp.raise_for_status() 
            
            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                snippet = item["snippet"]
                snippet = snippet.replace('<span class="searchmatch">', '')
                snippet = snippet.replace('</span>', '')

                results.append(EvidenceItem(
                    title=item["title"],
                    snippet=snippet,
                    url=f"https://en.wikipedia.org/wiki/{item['title'].replace(' ', '_')}",
                    source="Wikipedia",
                    credibility=0.65
                ))
    except Exception as e:
        print(f"[Wikipedia] Error: {e}")
    return results


# ─────────────────────────────────────────────
# SOURCE 2: NewsAPI (API key is in .env file)
# ─────────────────────────────────────────────

async def search_newsapi(claim: str) -> List[EvidenceItem]:
    """
    Searches NewsAPI for recent news articles about the claim.
    Returns up to 5 evidence items.
    NOTE: Free tier = 100 requests/day. Use sparingly during testing.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("[NewsAPI] No API key — skipping")
        return []

    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":        claim[:100],
                    "language": "en",
                    "sortBy":   "relevancy",
                    "pageSize": 5,
                    "apiKey":   api_key
                }
            )
            data = resp.json()

            if data.get("status") != "ok":
                print(f"[NewsAPI] API error: {data.get('message')}")
                return []

            # High-credibility news domains
            HIGH_CRED_DOMAINS = [
                "reuters.com", "bbc.com", "apnews.com",
                "nytimes.com", "theguardian.com", "who.int",
                "cdc.gov", "un.org"
            ]

            for article in data.get("articles", []):
                if not article.get("title") or not article.get("url"):
                    continue
                url = article["url"].lower()
                cred = 0.90 if any(d in url for d in HIGH_CRED_DOMAINS) else 0.55

                results.append(EvidenceItem(
                    title=article["title"],
                    snippet=article.get("description", "") or "",
                    url=article["url"],
                    source=article.get("source", {}).get("name", "NewsAPI"),
                    credibility=cred
                ))
    except Exception as e:
        print(f"[NewsAPI] Error: {e}")
    return results


# ─────────────────────────────────────────────
# SOURCE 3: Google Fact Check API
# ─────────────────────────────────────────────

async def search_factcheck(claim: str) -> List[EvidenceItem]:
    """
    Searches Google's Fact Check database.
    This directly searches existing fact-checks from Snopes, PolitiFact, etc.
    Returns up to 3 evidence items.
    """
    api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY")
    if not api_key:
        print("[FactCheck] No API key — skipping")
        return []

    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={"query": claim[:200], "key": api_key}
            )
            data = resp.json()

            for claim_item in data.get("claims", []):
                for review in claim_item.get("claimReview", []):
                    publisher = review.get("publisher", {}).get("name", "Fact Checker")
                    rating    = review.get("textualRating", "Unknown")
                    url       = review.get("url", "")
                    if not url:
                        continue

                    results.append(EvidenceItem(
                        title=f"{publisher}: {rating}",
                        snippet=f"Fact check rating: {rating} — {claim_item.get('text', '')[:100]}",
                        url=url,
                        source=publisher,
                        credibility=0.90  # fact-checkers are always high credibility
                    ))
    except Exception as e:
        print(f"[FactCheck] Error: {e}")
    return results


# ─────────────────────────────────────────────
# MAIN: Collect from all sources in parallel
# ─────────────────────────────────────────────

async def collect_all_evidence(claim: str) -> List[EvidenceItem]:
    """
    Runs all three scrapers IN PARALLEL using asyncio.gather().
    Total time = slowest single scraper (not sum of all).
    """
    print(f"\n[Scraper] Collecting evidence for: {claim[:60]}...")

    wiki_results, news_results, fact_results = await asyncio.gather(
        search_wikipedia(claim),
        search_newsapi(claim),
        search_factcheck(claim),
        return_exceptions=True   # don't crash if one fails
    )

    # Handle any exceptions from gather
    all_evidence = []
    for result in [wiki_results, news_results, fact_results]:
        if isinstance(result, Exception):
            print(f"[Scraper] Source failed: {result}")
        elif isinstance(result, list):
            all_evidence.extend(result)

    print(f"[Scraper] Found {len(all_evidence)} evidence items total")
    return all_evidence


# ─────────────────────────────────────────────
# TEST: Run this file directly to test scrapers
# python scraper.py
# ─────────────────────────────────────────────

# if __name__ == "__main__":
#     async def test():
#         claim = "USA lost the war against Afghanistan in 2021"
#         results = await collect_all_evidence(claim)
#         print(f"\nTotal: {len(results)} items\n")
#         for r in results:
#             print(f"[{r.source}] {r.title[:70]}")
#             print(f"  URL: {r.url[:70]}")
#             print(f"  Credibility: {r.credibility}")
#             print()
#     asyncio.run(test())
