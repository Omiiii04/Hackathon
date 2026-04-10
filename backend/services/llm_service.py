"""
backend/services/llm_service.py
---------------------------------
Unified LLM wrapper with:
  - Primary: LM Studio (local, OpenAI-compatible)
  - Fallback: Gemini 3 Flash Preview via google-genai SDK
  - Final fallback: Template strings (always succeeds)
  - Circuit breaker on each provider
"""
import asyncio
import logging
import re
import time
from typing import Optional

from config import settings
from services.circuit_breaker import get_breaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

# ── Fallback templates ────────────────────────────────────────────────────────
FALLBACK_TEMPLATES = {
    "TRUE": (
        "Multiple credible sources confirm this claim is accurate. "
        "The evidence from high-credibility outlets consistently supports the statement, "
        "with strong agreement across independent reporting."
    ),
    "FALSE": (
        "Multiple credible sources contradict this claim. "
        "The evidence from fact-checkers and major news outlets consistently "
        "shows this statement is inaccurate or fabricated."
    ),
    "MISLEADING": (
        "The evidence presents a mixed or incomplete picture. "
        "While some aspects may be accurate, the claim lacks important context, "
        "cherry-picks data, or contains distortions that could mislead readers."
    ),
    "CONFLICTING": (
        "High-credibility sources genuinely disagree on this claim. "
        "There is real debate among reliable outlets, and a definitive verdict "
        "cannot be reached with current evidence."
    ),
    "UNVERIFIED": (
        "Insufficient credible evidence was found to verify or refute this claim. "
        "This does not mean the claim is false — it means verifiable sourcing "
        "is currently unavailable."
    ),
}


def _clean_llm_output(raw: str, max_sentences: int = 4) -> str:
    """Strip reasoning tags, intros, and truncate to max_sentences."""
    # Remove <think>...</think> blocks (DeepSeek/Qwen reasoning)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Remove common chatty prefixes
    raw = re.sub(
        r"^(Here is|The explanation is|Based on the data|Sure[,!]?).{0,60}[:\n]\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", raw)
    return " ".join(sentences[:max_sentences]).strip()


# ── LM Studio call ────────────────────────────────────────────────────────────

async def _call_lm_studio(prompt: str, system: str, max_tokens: int = 200) -> str:
    """Call LM Studio local server (OpenAI-compatible)."""
    import httpx  # lazy import so startup is fast if LM Studio is not used

    breaker = get_breaker(
        "lm_studio",
        fail_max=settings.circuit_breaker_fail_max,
        reset_timeout=settings.circuit_breaker_reset_seconds,
    )

    async with breaker:
        # Dynamically discover the loaded model
        target_model = settings.lm_studio_model
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{settings.lm_studio_base_url}/models")
                data = r.json()
                models = [m["id"] for m in data.get("data", [])]
                if models:
                    # Prefer reasoning models for fact-checking
                    models.sort(
                        key=lambda x: 0 if any(k in x.lower() for k in ["deepseek", "r1", "qwen"]) else 1
                    )
                    target_model = models[0]
        except Exception:
            pass  # use default from config

        logger.info(f"[LLM] Calling LM Studio model: {target_model}")

        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=settings.lm_studio_timeout) as client:
            resp = await client.post(
                f"{settings.lm_studio_base_url}/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"].strip()


# ── Gemini call ───────────────────────────────────────────────────────────────

async def _call_gemini(prompt: str, max_tokens: int = 200) -> str:
    """Call Gemini 3 Flash Preview via google-genai SDK."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not set")

    breaker = get_breaker(
        "gemini",
        fail_max=settings.circuit_breaker_fail_max,
        reset_timeout=settings.circuit_breaker_reset_seconds,
    )

    async with breaker:
        from google import genai
        from google.genai import types

        logger.info(f"[LLM] Calling Gemini: {settings.gemini_model}")

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.0,
            ),
        )
        return response.text.strip()


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_explanation(
    claim: str,
    verdict: str,
    top_sources: list,
    algorithm_trace: dict,
    sub_claims: Optional[list] = None,
) -> tuple[str, str]:
    """
    Generate a 2-4 sentence explanation for the verdict.

    Returns:
        (explanation_text, provider_used)
    """
    source_names = [
        s.get("source", s.get("title", ""))[:30] for s in top_sources[:3]
    ]
    source_str = ", ".join(filter(None, source_names)) or "multiple sources"

    ratio = algorithm_trace.get("support_ratio", 0.5)
    sup_cnt = algorithm_trace.get("supporting_count", 0)
    con_cnt = algorithm_trace.get("contradicting_count", 0)
    tier1 = algorithm_trace.get("tier1_count", 0)
    avg_cred = algorithm_trace.get("avg_credibility", 0)
    evidence_count = algorithm_trace.get("evidence_count", 0)

    subclaim_block = ""
    if sub_claims:
        lines = "\n".join(
            f'  - "{sc["text"]}" → {sc["verdict"]} ({int(sc.get("confidence", 0) * 100)}%)'
            for sc in sub_claims
        )
        subclaim_block = f"\nSUBCLAIM BREAKDOWN:\n{lines}"

    prompt = f"""You are a professional fact-checker writing a verification report.
A deterministic algorithm computed the verdict below. Write exactly 2-4 sentences explaining it.

CLAIM: {claim}
ALGORITHM VERDICT: {verdict}
SUPPORT RATIO: {ratio:.2f}  (1.0=fully supported, 0.0=fully contradicted)
EVIDENCE COUNT: {evidence_count} sources analysed
SOURCES CONSULTED: {source_str}
SUPPORTING EVIDENCE ITEMS: {sup_cnt}
CONTRADICTING EVIDENCE ITEMS: {con_cnt}
HIGH-CREDIBILITY TIER-1 SOURCES: {tier1}
AVERAGE SOURCE CREDIBILITY: {avg_cred:.2f}{subclaim_block}

STRICT OUTPUT RULES:
- Output ONLY the 2-4 sentences.
- Do NOT start with "Here is", "Based on", or any intro phrase.
- Do NOT use bullet points, headers, or markdown.
- Do NOT mention confidence percentages — focus on evidence quality.
- Be specific: name source types (e.g. "fact-checkers", "major news outlets").
- Maximum 120 words."""

    system = (
        "You are a terse fact-checking engine. "
        "You output only the requested sentences with zero filler text."
    )

    # ── Try LM Studio first ───────────────────────────────────────────────────
    try:
        raw = await _call_lm_studio(prompt, system, max_tokens=200)
        text = _clean_llm_output(raw)
        if 20 <= len(text) <= 900:
            logger.info("[LLM] Explanation from LM Studio ✅")
            return text, "lm_studio"
        logger.warning(f"[LLM] LM Studio output out of bounds ({len(text)} chars), trying Gemini")
    except CircuitBreakerOpenError:
        logger.warning("[LLM] LM Studio circuit OPEN — trying Gemini")
    except Exception as e:
        logger.warning(f"[LLM] LM Studio failed: {e} — trying Gemini")

    # ── Try Gemini ────────────────────────────────────────────────────────────
    try:
        raw = await _call_gemini(prompt, max_tokens=200)
        text = _clean_llm_output(raw)
        if 20 <= len(text) <= 900:
            logger.info("[LLM] Explanation from Gemini ✅")
            return text, "gemini"
        logger.warning(f"[LLM] Gemini output out of bounds ({len(text)} chars), using template")
    except CircuitBreakerOpenError:
        logger.warning("[LLM] Gemini circuit OPEN — using template")
    except Exception as e:
        logger.warning(f"[LLM] Gemini failed: {e} — using template")

    # ── Final fallback ────────────────────────────────────────────────────────
    text = FALLBACK_TEMPLATES.get(verdict, FALLBACK_TEMPLATES["UNVERIFIED"])
    logger.info("[LLM] Using template fallback")
    return text, "template"
