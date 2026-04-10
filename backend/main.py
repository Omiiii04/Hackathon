# backend/main.py
"""
OSINT Verify — FastAPI entry point.
Connects the pipeline backend to the index.html frontend.

Key responsibilities:
  • Warm up BART-MNLI on startup (zero first-request latency).
  • POST /verify  → run full pipeline, translate result into the UI schema.
  • GET  /history → last 30 verifications.
  • DELETE /history/clear
  • GET  /health
"""

import datetime
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline import run_pipeline


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP / SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load BART-MNLI and warm it up before the first real request."""
    print("\n" + "=" * 60)
    print("[Startup] Pre-loading BART-MNLI stance classifier…")
    print("=" * 60)

    from verdict_engine import stance_classifier  # triggers module-level load

    try:
        _ = stance_classifier(
            "This is a warmup sentence.",
            ["supports the claim", "contradicts the claim", "neutral or unrelated"],
            hypothesis_template="This text {} that the sky is blue.",
        )
        print("[Startup] ✅ BART-MNLI ready — warmup inference complete.")
    except Exception as exc:
        print(f"[Startup] ⚠ Warmup failed (model still loaded): {exc}")

    print("=" * 60 + "\n")
    yield
    print("[Shutdown] OSINT Engine shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OSINT Engine API",
    description="Verify any claim using 10+ global OSINT sources",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend HTML directly at "/"
# Place index.html next to main.py (or adjust the path below).
try:
    app.mount("/static", StaticFiles(directory="."), name="static")
except Exception:
    pass  # skip if directory not found; API still works fine


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("index.html")


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY STORE
# ─────────────────────────────────────────────────────────────────────────────

_history: list = []   # list[dict] — last 30 verifications


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    claim:         str            = ""
    image_url:     Optional[str]  = None
    image_base64:  Optional[str]  = None
    claim_type:    Optional[str]  = "general"   # hint from UI type-selector


# The response schema mirrors what index.html's renderReport() expects.
class VerifyResponse(BaseModel):
    # Core verdict
    verdict:           str
    localized_verdict: Optional[str]       = None
    confidence:        float
    explanation:       str
    llm_provider:      str                 = "local_llm"
    claim_type:        str                 = "general"

    # Timing / cache
    processing_ms:     int
    cached:            bool

    # Evidence summary
    support_ratio:     float
    evidence_count:    int
    support_bar:       Dict[str, int]      # {support_pct, contradict_pct}

    # Verdict decoration
    verdict_tags:      List[str]           = []
    is_compound:       bool                = False
    is_mutation:       bool                = False
    adversarial:       bool                = False

    # Detailed outputs
    sources:           List[Dict[str, Any]] = []
    sub_claims:        List[Dict[str, Any]] = []
    trace:             Dict[str, Any]       = {}
    evidence_graph:    Dict[str, Any]       = {}
    mutation_chain:    List[Dict[str, Any]] = []
    algorithm_trace:   Dict[str, Any]       = {}   # raw trace for debugging


class HistoryItem(BaseModel):
    timestamp: str
    claim:     str
    verdict:   str


class HistoryResponse(BaseModel):
    history: List[HistoryItem]


class StatusResponse(BaseModel):
    status: str


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: extract domain from URL
# ─────────────────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    """Return bare domain, e.g. 'reuters.com'."""
    try:
        host = urlparse(url).netloc or url
        return host.replace("www.", "").lower()
    except Exception:
        return url.lower()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: map credibility label/float → tier integer for the UI
# ─────────────────────────────────────────────────────────────────────────────

def _tier(credibility_label: str, credibility_float: float = 0.0) -> int:
    """
    Convert a credibility label (HIGH / MEDIUM / LOW) or raw float to a
    1–4 tier number used by the UI's source cards.
    """
    label = credibility_label.upper() if credibility_label else ""
    if label == "HIGH"   or credibility_float >= 0.85:  return 1
    if label == "MEDIUM" or credibility_float >= 0.55:  return 2
    if credibility_float >= 0.35:                        return 3
    return 4


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: derive verdict_tags from the algorithm trace
# ─────────────────────────────────────────────────────────────────────────────

def _build_verdict_tags(verdict: str, trace: dict, is_compound: bool) -> List[str]:
    tags: List[str] = []

    tier1 = trace.get("tier1_count", 0)
    n     = trace.get("evidence_count", 0)
    agree = trace.get("agreement", 0)

    if tier1 >= 3:
        tags.append(f"{tier1} Tier-1 sources")
    elif tier1 >= 1:
        tags.append(f"{tier1} Tier-1 source{'s' if tier1 > 1 else ''}")

    if agree >= 0.7:
        tags.append("High agreement")
    elif agree < 0.3:
        tags.append("Split evidence")

    if n >= 10:
        tags.append("Strong evidence base")
    elif n == 0:
        tags.append("Insufficient sources")

    if is_compound:
        tags.append("Compound claim")

    if verdict == "MISLEADING":
        tags.append("Context missing")
    if verdict == "CONFLICTING":
        tags.append("Genuine disagreement")
    if verdict == "UNVERIFIED":
        tags.append("Check back later")

    return tags[:5]   # cap at 5 tags


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: detect claim type from claim text
# ─────────────────────────────────────────────────────────────────────────────

_BREAKING_KW  = re.compile(r"\b(breaks?|breaking|just in|alert|urgent|develop)\b", re.I)
_SCIENTIFIC_KW = re.compile(r"\b(study|research|scientist|vaccine|virus|data|trial|experiment|survey)\b", re.I)
_POLITICAL_KW  = re.compile(r"\b(government|president|minister|election|parliament|senate|congress|policy|law|bill|vote)\b", re.I)


def _detect_claim_type(claim: str, hint: str = "general") -> str:
    if hint and hint != "general":
        return hint
    if _BREAKING_KW.search(claim):  return "breaking_news"
    if _SCIENTIFIC_KW.search(claim): return "scientific"
    if _POLITICAL_KW.search(claim):  return "political"
    return "general"


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: build evidence graph for the right-panel canvas
# ─────────────────────────────────────────────────────────────────────────────

def _build_evidence_graph(sources: List[dict]) -> Dict[str, Any]:
    """
    Construct a simple graph from the top sources list.
    Nodes  → each source domain.
    Edges  → pairs of same-stance sources (claim_overlap approximated from credibility).
    """
    nodes = []
    for s in sources:
        nodes.append({
            "id":     s.get("domain", s.get("source", "unknown")),
            "tier":   s.get("tier", 3),
            "stance": s.get("stance", "NEUTRAL"),
            "score":  round(s.get("credibility", 0.5), 2),
        })

    edges = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            if a["stance"] == b["stance"]:
                overlap = round((a["score"] + b["score"]) / 2 * 0.85, 2)
                edges.append({"source": a["id"], "target": b["id"], "claim_overlap": overlap})

    return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TRANSFORMER: VerdictResult dict → UI response dict
# ─────────────────────────────────────────────────────────────────────────────

def _format_for_ui(
    raw: dict,
    claim: str,
    claim_type_hint: str = "general",
) -> dict:
    """
    Converts the raw VerdictResult.to_dict() payload into the shape that
    index.html's renderReport() function expects.
    """
    verdict      = raw.get("verdict", "UNVERIFIED")
    confidence   = raw.get("confidence", 0.0)
    explanation  = raw.get("explanation", "")
    support_ratio = raw.get("support_ratio", 0.5)
    evidence_count = raw.get("evidence_count", 0)
    is_compound  = raw.get("is_compound", False)
    cached       = raw.get("cached", False)
    proc_ms      = raw.get("processing_time_ms", 0)
    algo_trace   = raw.get("algorithm_trace", {})

    # ── Sources ──────────────────────────────────────────────────────────────
    # Backend sources: {title, url, source, credibility (label str), stance}
    # UI sources:      {name, domain, tier, credibility (float 0-1), stance, date, shift}

    # Credibility label → float lookup (reverse of get_credibility_label)
    _label_to_float = {"HIGH": 0.90, "MEDIUM": 0.65, "LOW": 0.35}

    ui_sources = []
    for s in raw.get("sources", []):
        cred_label = s.get("credibility", "MEDIUM")
        cred_float = _label_to_float.get(str(cred_label).upper(), 0.65)

        ui_sources.append({
            "name":        s.get("source", s.get("title", "Unknown"))[:40],
            "domain":      _domain(s.get("url", "")),
            "tier":        _tier(str(cred_label), cred_float),
            "credibility": cred_float,
            "stance":      s.get("stance", "NEUTRAL"),
            "date":        "recent",   # scraper doesn't return publish date yet
            "shift":       0,          # delta credibility shift (reserved)
        })

    # ── Support bar ───────────────────────────────────────────────────────────
    support_pct   = round(support_ratio * 100)
    contradict_pct = 100 - support_pct
    support_bar = {"support_pct": support_pct, "contradict_pct": contradict_pct}

    # ── Claim type ────────────────────────────────────────────────────────────
    claim_type = _detect_claim_type(claim, claim_type_hint)

    # ── Verdict tags ──────────────────────────────────────────────────────────
    # Enrich algo_trace with extra keys for tag builder
    enriched_trace = {**algo_trace, "evidence_count": evidence_count}
    verdict_tags = _build_verdict_tags(verdict, enriched_trace, is_compound)

    # ── UI trace object ────────────────────────────────────────────────────────
    ui_trace = {
        "support_ratio":        round(support_ratio, 3),
        "total_evidence_items": evidence_count,
        "tier1_sources_found":  algo_trace.get("tier1_count", 0),
        "temporal_mismatch":    False,   # reserved — requires publish-date logic
        "echo_chamber_penalty": False,   # reserved — requires source diversity check
        "early_exit_triggered": False,
        "event_date":           "unknown",
        "utterance_date":       datetime.date.today().isoformat(),
        "confidence_raw":       round(confidence, 3),
        "confidence_final":     round(confidence, 3),
        "claim_type":           claim_type,
        "threshold_TRUE":       round(algo_trace.get("true_threshold", 0.70), 2),
        "threshold_FALSE":      round(algo_trace.get("true_threshold", 0.70) * 0.4, 2),
        # Extra algorithm detail (bonus for advanced profiles)
        "supporting_count":     algo_trace.get("supporting_count", 0),
        "contradicting_count":  algo_trace.get("contradicting_count", 0),
        "neutral_count":        algo_trace.get("neutral_count", 0),
        "avg_credibility":      algo_trace.get("avg_credibility", 0),
        "agreement":            algo_trace.get("agreement", 0),
    }

    # ── Sub-claims: add confidence if missing (UI renders verdict + text) ──────
    sub_claims = raw.get("sub_claims", [])

    # ── Evidence graph ────────────────────────────────────────────────────────
    evidence_graph = _build_evidence_graph(ui_sources)

    return {
        # Core
        "verdict":           verdict,
        "localized_verdict": raw.get("localized_verdict"),
        "confidence":        confidence,
        "explanation":       explanation,
        "llm_provider":      "local_llm",
        "claim_type":        claim_type,

        # Timing / cache
        "processing_ms":     proc_ms,
        "cached":            cached,

        # Evidence summary
        "support_ratio":     round(support_ratio, 3),
        "evidence_count":    evidence_count,
        "support_bar":       support_bar,

        # Decoration
        "verdict_tags":      verdict_tags,
        "is_compound":       is_compound,
        "is_mutation":       False,   # reserved — requires claim DB
        "adversarial":       False,   # reserved — requires adversarial detector
        "adversarial_signal": "",

        # Detailed outputs
        "sources":           ui_sources,
        "sub_claims":        sub_claims,
        "trace":             ui_trace,
        "evidence_graph":    evidence_graph,
        "mutation_chain":    [],      # reserved

        # Raw algorithm trace (kept for backend debugging)
        "algorithm_trace":   algo_trace,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check — confirms the model loaded correctly."""
    from verdict_engine import stance_classifier
    return {
        "status":      "ok",
        "message":     "OSINT Engine is running",
        "model_ready": stance_classifier is not None,
    }


@app.post("/verify")
async def verify(body: VerifyRequest):
    """
    Main verification endpoint — full pipeline.
    Accepts text claims and optionally an image (URL or base64).
    Returns a response shaped for index.html's renderReport().
    """
    claim = body.claim.strip()

    # ── Image extraction ─────────────────────────────────────────────────────
    if body.image_url or body.image_base64:
        from image_engine import extract_claim_from_image
        import base64
        import httpx

        image_bytes = None
        if body.image_base64:
            b64_str = body.image_base64
            if "," in b64_str:               # strip data-URL prefix
                b64_str = b64_str.split(",")[1]
            image_bytes = base64.b64decode(b64_str)
        elif body.image_url:
            async with httpx.AsyncClient() as client:
                resp = await client.get(body.image_url)
                if resp.status_code == 200:
                    image_bytes = resp.content

        if image_bytes:
            print("[API] Extracting claim from image…")
            claim = extract_claim_from_image(image_bytes)
            print(f"[API] Extracted claim: {claim}")

    if not claim:
        raise HTTPException(
            status_code=400,
            detail="No valid claim could be found or extracted.",
        )

    # ── Language detection / translation ─────────────────────────────────────
    from translator import detect_lang, translate_to_en, translate_verdict

    source_lang = detect_lang(claim)
    if source_lang != "en":
        print(f"[API] Detected '{source_lang}', translating to EN…")
        claim = translate_to_en(claim, source_lang)

    # ── Run the pipeline ──────────────────────────────────────────────────────
    result = await run_pipeline(claim)
    raw    = result.to_dict()

    # ── Localize verdict if needed ────────────────────────────────────────────
    if source_lang != "en":
        raw["localized_verdict"] = translate_verdict(raw["verdict"], source_lang)

    # ── History ───────────────────────────────────────────────────────────────
    _history.append({
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "claim":     claim[:100] + ("…" if len(claim) > 100 else ""),
        "verdict":   raw["verdict"],
    })
    if len(_history) > 30:
        _history.pop(0)

    # ── Transform to UI schema ────────────────────────────────────────────────
    return _format_for_ui(raw, claim, body.claim_type or "general")


@app.get("/history", response_model=HistoryResponse)
def get_history():
    """Return the last 30 verifications in reverse chronological order."""
    return {"history": list(reversed(_history))}


@app.delete("/history/clear", response_model=StatusResponse)
def clear_history():
    """Wipe the in-memory history."""
    _history.clear()
    return {"status": "success"}