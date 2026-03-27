# backend/pipeline.py
import asyncio
import time
from typing import Optional
from models import VerdictResult
from scraper import collect_all_evidence
from verdict_engine import compute_verdict
from explainer import generate_explanation
# Add to pipeline.py
from claim_parser import split_compound_claim, is_compound

async def run_pipeline(claim: str) -> VerdictResult:
    # Check if compound
    if is_compound(claim):
        return await run_compound_pipeline(claim)
    # ... rest of pipeline ...


async def run_compound_pipeline(claim: str) -> VerdictResult:
    """Verify each sub-claim separately, then aggregate."""
    from verdict_engine import VERDICT_AGGREGATION

    sub_claims = split_compound_claim(claim)
    print(f"[Pipeline] Compound claim — {len(sub_claims)} sub-claims")

    sub_results = []
    for sub in sub_claims:
        result = await run_pipeline(sub)
        sub_results.append({
            "text":       sub,
            "verdict":    result.verdict,
            "confidence": result.confidence
        })

    # Aggregate: any FALSE → MISLEADING, mix → MISLEADING, all same → that verdict
    verdicts = [r["verdict"] for r in sub_results]
    if all(v == "TRUE"        for v in verdicts): agg = "TRUE"
    elif all(v == "FALSE"     for v in verdicts): agg = "FALSE"
    elif "UNVERIFIED" in verdicts:                agg = "UNVERIFIED"
    else:                                         agg = "MISLEADING"

    # Run overall pipeline for the full claim too
    overall = await run_pipeline.__wrapped__(claim)   # bypass compound check
    overall.verdict    = agg
    overall.sub_claims = sub_results
    return overall

async def run_pipeline(claim: str) -> VerdictResult:
    """
    Main pipeline — called by your teammate's FastAPI endpoint.

    Flow:
    1. Collect evidence from Wikipedia + NewsAPI + Fact Check (parallel)
    2. Compute verdict using deterministic algorithm
    3. Generate 2-sentence explanation via Gemini (locked at temp=0.0)
    4. Return VerdictResult

    This function is async — your teammate wraps it in asyncio.run()
    inside their Celery task, or calls it directly in FastAPI.
    """
    start_ms = time.time() * 1000

    print(f"\n{'='*60}")
    print(f"PIPELINE START: {claim[:60]}")
    print(f"{'='*60}")

    # ── Step 1: Collect Evidence ─────────────────────────────────
    print("[1/3] Collecting evidence...")
    evidence = await collect_all_evidence(claim)

    if not evidence:
        print("[Pipeline] No evidence found — returning UNVERIFIED")
        return VerdictResult(
            verdict="UNVERIFIED",
            confidence=0.0,
            explanation=("We could not find any sources to verify this claim. "
                        "This does not necessarily mean it is false."),
            support_ratio=0.5,
            evidence_count=0,
            processing_time_ms=int(time.time() * 1000 - start_ms)
        )

    # ── Step 2: Compute Verdict ──────────────────────────────────
    print(f"[2/3] Computing verdict from {len(evidence)} evidence items...")
    result = compute_verdict(evidence, claim)

    print(f"[Pipeline] Verdict: {result.verdict} | "
          f"Confidence: {result.confidence} | "
          f"Ratio: {result.support_ratio}")

    # ── Step 3: Generate Explanation ─────────────────────────────
    print("[3/3] Generating explanation via Gemini...")
    result.explanation = await generate_explanation(
        claim=claim,
        verdict=result.verdict,
        top_sources=result.sources,
        algorithm_trace=result.algorithm_trace
    )

    result.processing_time_ms = int(time.time() * 1000 - start_ms)

    print(f"[Pipeline] Done in {result.processing_time_ms}ms")
    print(f"[Pipeline] Explanation: {result.explanation[:80]}...")

    return result


# ─────────────────────────────────────────────
# TEST: Run the full pipeline
# python pipeline.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    async def test_all():
        test_claims = [
            ("Iran lost the war in 2025",                    "FALSE"),
            ("NASA confirmed alien life",             "UNVERIFIED"),
            ("COVID vaccines contain microchips",     "FALSE"),
            ("Artemis mission launched in 2022",      "TRUE"),
            ("New virus outbreak started in India",   "MISLEADING"),
        ]
        print("\n" + "="*70)
        print("TESTING ALL BENCHMARK CLAIMS")
        print("="*70 + "\n")

        for claim, expected in test_claims:
            result = await run_pipeline(claim)
            match  = "✅" if result.verdict == expected else "❌"
            print(f"{match} '{claim}'")
            print(f"   Got: {result.verdict} | Expected: {expected}")
            print(f"   Confidence: {result.confidence} | Time: {result.processing_time_ms}ms")
            print(f"   Explanation: {result.explanation[:80]}...")
            print()
            await asyncio.sleep(2)   # avoid rate limits between tests

    asyncio.run(test_all())
