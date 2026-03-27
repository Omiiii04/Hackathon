# backend/explainer.py
import os
import re
from openai import AsyncOpenAI

# ─────────────────────────────────────────────
# LM STUDIO CLIENT SETUP
# ─────────────────────────────────────────────
client = AsyncOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

# ─────────────────────────────────────────────
# RULE-BASED FALLBACK
# ─────────────────────────────────────────────
FALLBACK_TEMPLATES = {
    "TRUE": "Multiple credible sources confirm this claim is accurate. The evidence consistently supports the statement.",
    "FALSE": "Multiple credible sources contradict this claim. The evidence consistently shows this statement is inaccurate.",
    "MISLEADING": "The evidence presents a mixed or incomplete picture. While some aspects may be accurate, the claim lacks important context or contains distortions.",
    "CONFLICTING": "High-credibility sources genuinely disagree on this claim. There is real debate among reliable outlets, and a definitive verdict cannot be reached.",
    "UNVERIFIED": "Insufficient credible evidence was found to verify or refute this claim. This does not mean the claim is false — it means we could not find enough sources.",
}

async def generate_explanation(claim: str, verdict: str,
                                top_sources: list,
                                algorithm_trace: dict) -> str:
    """
    Calls a local LLM via LM Studio to generate a 2 to 4 sentence explanation.
    Includes programmatic truncation to handle overly chatty local models.
    """
    try:
        source_names = [s.get("source", s.get("title", ""))[:30] for s in top_sources[:3]]
        source_str   = ", ".join(filter(None, source_names)) or "multiple sources"

        ratio    = algorithm_trace.get("support_ratio", 0.5)
        sup_cnt  = algorithm_trace.get("supporting_count", 0)
        con_cnt  = algorithm_trace.get("contradicting_count", 0)
        tier1    = algorithm_trace.get("tier1_count", 0)

        prompt = f"""You are a professional fact-checker.
A deterministic algorithm has computed the verdict.
Write exactly 2 to 4 sentences explaining the verdict based on the data below.

CLAIM: {claim}
ALGORITHM VERDICT: {verdict}
SUPPORT RATIO: {ratio}
SOURCES CONSULTED: {source_str}
SUPPORTING EVIDENCE: {sup_cnt}
CONTRADICTING EVIDENCE: {con_cnt}
HIGH-CREDIBILITY SOURCES: {tier1}

STRICT RULES:
- Output ONLY the 2-4 sentences.
- NO intro (e.g., do not say "Here is the explanation").
- NO outro.
- NO formatting, bullet points, or newlines."""

        response = await client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": "You are a data-to-text pipeline. You output only the requested sentences. You never use conversational filler."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=500  # ── Bumped up to allow room for the thinking process!
        )
        
        raw_text = response.choices[0].message.content.strip()

        # ── THE FIX: Remove everything inside <think> and </think> ──
        # flags=re.DOTALL ensures it deletes across multiple lines
        raw_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()

        # 1. Remove common chatty prefixes the model might still try to use
        raw_text = re.sub(r"^(Here is|The explanation is|Based on the).{0,50}:\s*", "", raw_text, flags=re.IGNORECASE)
        
        # 2. Split the text into sentences based on punctuation (.!?)
        sentences = re.split(r'(?<=[.!?]) +', raw_text)
        
        # 3. Forcefully keep only the first 4 sentences and join them back together
        clean_text = " ".join(sentences[:4]).strip()
        
        # ── UPDATE 3: Relaxed Sanity Check ──
        # If it's still weirdly short or somehow massive, we fall back.
        if len(clean_text) > 800 or len(clean_text) < 20:
            print(f"[Explainer] Response length out of bounds ({len(clean_text)} chars). Using fallback.")
            return FALLBACK_TEMPLATES.get(verdict, FALLBACK_TEMPLATES["UNVERIFIED"])

        return clean_text

    except Exception as e:
        print(f"[Explainer] Local LLM failed: {e} — using fallback template")
        return FALLBACK_TEMPLATES.get(verdict, FALLBACK_TEMPLATES["UNVERIFIED"])

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
        print("\nFinal Explanation:")
        print(explanation)

    asyncio.run(test())