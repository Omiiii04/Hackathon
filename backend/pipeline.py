# backend/pipeline.py
import asyncio
import time
from typing import List, Optional
from models import VerdictResult
from scraper import collect_all_evidence
from verdict_engine import compute_verdict
from explainer import generate_explanation
from claim_parser import split_compound_claim, is_compound


# ─────────────────────────────────────────────
# INTERNAL: Single-claim pipeline (no compound check)
# ─────────────────────────────────────────────
async def _run_single_pipeline(claim: str) -> VerdictResult:
    """
    Verifies a single atomic claim end-to-end.
    Does NOT check for compound claims — callers must handle that.
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
            explanation=(
                "We could not find any sources to verify this claim. "
                "This does not necessarily mean it is false."
            ),
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
    print("[3/3] Generating explanation via LLM...")
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
# COMPOUND AGGREGATION
# ─────────────────────────────────────────────
def _aggregate_verdict(sub_results: List[dict]) -> str:
    """
    Derive a combined verdict from multiple subclaim verdicts.

    Rules (in priority order):
    1. All TRUE              → TRUE
    2. All FALSE             → FALSE
    3. All UNVERIFIED        → UNVERIFIED
    4. Mix of TRUE + FALSE   → MISLEADING  (contradictory parts)
    5. Any CONFLICTING       → CONFLICTING
    6. Majority TRUE but some UNVERIFIED → MISLEADING (incomplete picture)
    7. Majority FALSE but some UNVERIFIED → FALSE (lean false)
    8. Otherwise             → MISLEADING
    """
    verdicts = [r["verdict"] for r in sub_results]
    unique   = set(verdicts)

    if unique == {"TRUE"}:           return "TRUE"
    if unique == {"FALSE"}:          return "FALSE"
    if unique == {"UNVERIFIED"}:     return "UNVERIFIED"
    if "CONFLICTING" in unique:      return "CONFLICTING"
    if "TRUE" in unique and "FALSE" in unique: return "MISLEADING"

    # Majority rule for mixed TRUE/UNVERIFIED or FALSE/UNVERIFIED
    true_cnt  = verdicts.count("TRUE")
    false_cnt = verdicts.count("FALSE")
    unver_cnt = verdicts.count("UNVERIFIED")
    total     = len(verdicts)

    if true_cnt / total >= 0.6 and false_cnt == 0:   return "MISLEADING"
    if false_cnt / total >= 0.6 and true_cnt == 0:   return "FALSE"

    return "MISLEADING"


def _aggregate_confidence(sub_results: List[dict]) -> float:
    """
    Average confidence, penalised by disagreement among subclaims.
    """
    if not sub_results:
        return 0.0
    avg = sum(r["confidence"] for r in sub_results) / len(sub_results)
    unique_verdicts = len({r["verdict"] for r in sub_results})
    # each extra distinct verdict reduces overall confidence slightly
    penalty = (unique_verdicts - 1) * 0.05
    return round(max(0.0, min(0.95, avg - penalty)), 2)


# ─────────────────────────────────────────────
# COMPOUND PIPELINE
# ─────────────────────────────────────────────
async def _run_compound_pipeline(claim: str) -> VerdictResult:
    """Verify each sub-claim separately, then aggregate into one result."""
    sub_claims_text = split_compound_claim(claim)
    print(f"[Pipeline] Compound claim — {len(sub_claims_text)} sub-claims detected")

    # Verify every sub-claim independently (sequentially to avoid rate limits)
    sub_results = []
    for sub in sub_claims_text:
        print(f"[Pipeline] Verifying sub-claim: '{sub[:60]}'")
        result = await _run_single_pipeline(sub)
        sub_results.append({
            "text":       sub,
            "verdict":    result.verdict,
            "confidence": result.confidence,
        })

    # Determine aggregated verdict + confidence
    agg_verdict     = _aggregate_verdict(sub_results)
    agg_confidence  = _aggregate_confidence(sub_results)

    print(f"[Pipeline] Aggregated verdict: {agg_verdict} "
          f"(confidence={agg_confidence}) from {len(sub_results)} sub-claims")

    # Run a full pipeline on the original claim for evidence/sources/explanation
    overall = await _run_single_pipeline(claim)

    # Override the verdict/confidence with the compound-aware values
    overall.verdict     = agg_verdict
    overall.confidence  = agg_confidence
    overall.sub_claims  = sub_results
    overall.is_compound = True

    # Regenerate explanation now that we have the real aggregated verdict
    overall.explanation = await generate_explanation(
        claim=claim,
        verdict=agg_verdict,
        top_sources=overall.sources,
        algorithm_trace={
            **overall.algorithm_trace,
            "sub_claims": sub_results,
        },
        sub_claims=sub_results,
    )

    return overall


# ─────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────
async def run_pipeline(claim: str) -> VerdictResult:
    """
    Main pipeline — called by the FastAPI endpoint.

    If the claim is compound (contains multiple assertions), each sub-claim
    is verified independently and the results are aggregated.
    Otherwise a single end-to-end verification is performed.
    """
    if is_compound(claim):
        return await _run_compound_pipeline(claim)
    return await _run_single_pipeline(claim)


# ─────────────────────────────────────────────
# TEST: Run the full pipeline
# python pipeline.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    async def test_all():
        test_claims = [
            ("Iran lost the war",                                          "FALSE"),
            ("NASA confirmed alien life",                                   "UNVERIFIED"),
            ("COVID vaccines contain microchips",                           "FALSE"),
            ("Artemis mission launched in 2022",                           "TRUE"),
            ("New virus outbreak started in India",                        "MISLEADING"),
            ("COVID vaccines contain microchips and NASA confirmed aliens", "MISLEADING"),
        ]
        print("\n" + "="*70)
        print("TESTING ALL BENCHMARK CLAIMS")
        print("="*70 + "\n")

        for claim, expected in test_claims:
            result = await run_pipeline(claim)
            match  = "✅" if result.verdict == expected else "❌"
            print(f"{match} '{claim}'")
            print(f"   Got: {result.verdict} | Expected: {expected}")
            print(f"   Confidence: {result.confidence} | "
                  f"Time: {result.processing_time_ms}ms | "
                  f"Compound: {result.is_compound}")
            if result.sub_claims:
                for sc in result.sub_claims:
                    print(f"     • [{sc['verdict']}] {sc['text']}")
            print(f"   Explanation: {result.explanation[:80]}...")
            print()
            await asyncio.sleep(2)   # avoid rate limits between tests

    asyncio.run(test_all())
