# backend/explainer.py
import os
from dotenv import load_dotenv

# NEW IMPORTS: Switch to the new google.genai package
from google import genai
from google.genai import types

load_dotenv()

# Initialize the new Client. 
# It automatically looks for the GEMINI_API_KEY environment variable.
client = genai.Client()

# ─────────────────────────────────────────────
# RULE-BASED FALLBACK (always works, no API needed)
# ─────────────────────────────────────────────
FALLBACK_TEMPLATES = {
    "TRUE": (
        "Multiple credible sources confirm this claim is accurate. "
        "The evidence consistently supports the statement."
    ),
    "FALSE": (
        "Multiple credible sources contradict this claim. "
        "The evidence consistently shows this statement is inaccurate."
    ),
    "MISLEADING": (
        "The evidence presents a mixed or incomplete picture. "
        "While some aspects may be accurate, the claim lacks important context or contains distortions."
    ),
    "CONFLICTING": (
        "High-credibility sources genuinely disagree on this claim. "
        "There is real debate among reliable outlets, and a definitive verdict cannot be reached."
    ),
    "UNVERIFIED": (
        "Insufficient credible evidence was found to verify or refute this claim. "
        "This does not mean the claim is false — it means we could not find enough sources."
    ),
}

async def generate_explanation(claim: str, verdict: str,
                                top_sources: list,
                                algorithm_trace: dict) -> str:
    """
    Calls Gemini to generate a 2-sentence explanation using the new SDK.
    Temperature=0.0 — locked, no creative drift.
    Falls back to template if API fails.
    """
    try:
        source_names = [s.get("source", s.get("title", ""))[:30] for s in top_sources[:3]]
        source_str   = ", ".join(filter(None, source_names)) or "multiple sources"

        ratio    = algorithm_trace.get("support_ratio", 0.5)
        sup_cnt  = algorithm_trace.get("supporting_count", 0)
        con_cnt  = algorithm_trace.get("contradicting_count", 0)
        tier1    = algorithm_trace.get("tier1_count", 0)

        prompt = f"""You are a professional fact-checker.
A deterministic algorithm has already computed the verdict for this claim.
Your ONLY task: write exactly 2 clear sentences explaining this verdict.

CLAIM: {claim}
ALGORITHM VERDICT: {verdict}
SUPPORT RATIO: {ratio} (higher = more evidence supports the claim)
SOURCES CONSULTED: {source_str}
SUPPORTING EVIDENCE COUNT: {sup_cnt}
CONTRADICTING EVIDENCE COUNT: {con_cnt}
HIGH-CREDIBILITY SOURCES: {tier1}

STRICT RULES:
- Do NOT change or question the verdict
- Do NOT add any information not present above
- Write for a general audience (no technical jargon)
- Maximum 60 words total
- Do not use bullet points or lists

Write only the 2-sentence explanation. Nothing else."""

# NEW SDK SYNTAX: Use client.aio for async calls
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=150,
                # ── UPDATE: Change from BLOCK_ONLY_HIGH to BLOCK_NONE ──
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE",
                    )
                ]
            )
        )
        
        # ── ADD THIS: Debug the finish reason so we aren't flying blind ──
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            # A normal, successful generation has a finish_reason of 'STOP'
            if str(finish_reason) != "STOP":
                print(f"[Explainer] Gemini aborted generation! Reason: {finish_reason}")
        
        # Safely extract text (in case it was completely blocked and text is None)
        text = response.text.strip() if response.text else ""

        # Our length check to catch anything weird
        if len(text) > 400 or len(text) < 50:
            print(f"[Explainer] Response too short/long. Length: {len(text)}. Using fallback.")
            return FALLBACK_TEMPLATES.get(verdict, FALLBACK_TEMPLATES["UNVERIFIED"])

        return text

    except Exception as e:
        # This will catch network errors, blocked content, or missing API keys
        print(f"[Explainer] Gemini failed: {e} — using fallback template")
        return FALLBACK_TEMPLATES.get(verdict, FALLBACK_TEMPLATES["UNVERIFIED"])


# ─────────────────────────────────────────────
# TEST: Run directly
# python explainer.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    async def test():
        explanation = await generate_explanation(
            claim="COVID vaccines contain microchips",
            verdict="FALSE",
            top_sources=[{"source": "Reuters"}, {"source": "BBC"}],
            algorithm_trace={"support_ratio": 0.08, "tier1_count": 3,
                             "supporting_count": 1, "contradicting_count": 10}
        )
        print("Explanation:", explanation)

    asyncio.run(test())