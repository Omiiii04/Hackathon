# backend/precache.py
"""
Pre-loads benchmark claims into the in-memory cache.
Run this BEFORE the demo so benchmark claims return instantly.
Usage: python precache.py
"""
import asyncio
import httpx

API_URL = "http://localhost:8000"

BENCHMARK_CLAIMS = [
    {"claim": "Iran lost the war",                  "expected": "FALSE"},
    {"claim": "NASA confirmed alien life",           "expected": "UNVERIFIED"},
    {"claim": "COVID vaccines contain microchips",   "expected": "FALSE"},
    {"claim": "Artemis mission launched in 2022",    "expected": "TRUE"},
    {"claim": "New virus outbreak started in India", "expected": "MISLEADING"},
]


async def precache():
    print("Pre-caching benchmark claims...")
    print("Make sure the backend is running: uvicorn main:app --reload\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for item in BENCHMARK_CLAIMS:
            claim    = item["claim"]
            expected = item["expected"]
            print(f"Verifying: {claim}")
            try:
                resp = await client.post(
                    f"{API_URL}/verify",
                    json={"claim": claim}
                )
                data  = resp.json()
                match = "✅" if data["verdict"] == expected else "❌"
                print(f"  {match} {data['verdict']} (expected {expected})")
                print(f"     Confidence: {data.get('confidence', 0):.0%}")
                print(f"     Time: {data.get('processing_time_ms', 0)}ms")
            except Exception as e:
                print(f"  ❌ Error: {e}")
            print()
            await asyncio.sleep(3)   # avoid API rate limits

    print("Pre-caching complete!")
    print("Second call to any of these will be instant (from cache).")


asyncio.run(precache())
