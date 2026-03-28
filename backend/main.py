# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pipeline import run_pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Pre-load and warm up the BART-MNLI stance classifier before accepting
    any requests. This means the first real user request pays no loading cost.
    """
    print("\n" + "="*60)
    print("[Startup] Pre-loading BART-MNLI stance classifier…")
    print("="*60)

    # Import triggers module-level pipeline() call in verdict_engine.py
    from verdict_engine import stance_classifier

    # Warm-up: run one dummy inference so PyTorch JIT-compiles the graph.
    # This eliminates the 2-3 s overhead on the very first real request.
    try:
        _ = stance_classifier(
            "This is a warmup sentence.",
            ["supports the claim", "contradicts the claim", "neutral or unrelated"],
            hypothesis_template="This text {} that the sky is blue."
        )
        print("[Startup] ✅ BART-MNLI ready — warmup inference complete.")
    except Exception as e:
        print(f"[Startup] ⚠ Warmup failed (model still loaded): {e}")

    print("="*60 + "\n")

    yield   # ← server is now live and handling requests

    # Shutdown hook (optional cleanup)
    print("[Shutdown] OSINT Verify shutting down.")


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────
app = FastAPI(
    title="OSINT Verify API",
    description="Verify any claim using 10+ global OSINT sources",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allows the Chrome extension and any local frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache (no database needed for MVP)
_cache:   dict = {}   # claim text → result
_history: list = []   # last 20 verifications


class VerifyRequest(BaseModel):
    claim: str = ""
    image_url: str | None = None
    image_base64: str | None = None

class VerifyResponse(BaseModel):
    verdict: str
    localized_verdict: Optional[str] = None
    confidence: float
    explanation: str
    support_ratio: float
    evidence_count: int
    sources: List[Dict[str, Any]] = []
    algorithm_trace: Dict[str, Any] = {}
    cached: bool = False
    processing_time_ms: int = 0
    sub_claims: List[Dict[str, Any]] = []
    is_compound: bool = False

class HistoryItem(BaseModel):
    timestamp: str
    claim: str
    verdict: str

class HistoryResponse(BaseModel):
    history: List[HistoryItem]

class StatusResponse(BaseModel):
    status: str


@app.get("/health")
def health():
    """Health check — returns model status so you can verify it loaded."""
    from verdict_engine import stance_classifier
    model_ready = stance_classifier is not None
    return {
        "status":      "ok",
        "message":     "OSINT Verify is running",
        "model_ready": model_ready,
    }


@app.post("/verify", response_model=VerifyResponse)
async def verify(body: VerifyRequest):
    """Main endpoint — full pipeline. Now supports text and image claims."""
    claim = body.claim.strip()

    if body.image_url or body.image_base64:
        from image_engine import extract_claim_from_image
        import base64
        import httpx

        image_bytes = None
        if body.image_base64:
            # handle 'data:image/png;base64,....' prefix if present
            b64_str = body.image_base64
            if "," in b64_str:
                b64_str = b64_str.split(",")[1]
            image_bytes = base64.b64decode(b64_str)
        elif body.image_url:
            async with httpx.AsyncClient() as client:
                resp = await client.get(body.image_url)
                if resp.status_code == 200:
                    image_bytes = resp.content
        
        if image_bytes:
            print("[API] Extracting claim from image...")
            claim = extract_claim_from_image(image_bytes)
            print(f"[API] Extracted claim: {claim}")

    if not claim:
        raise HTTPException(status_code=400, detail="No valid claim could be found or extracted.")

    from translator import detect_lang, translate_to_en, translate_from_en, translate_verdict
    source_lang = detect_lang(claim)
    
    if source_lang != 'en':
        print(f"[API] Detected '{source_lang}', translating to EN...")
        claim = translate_to_en(claim, source_lang)

    result = await run_pipeline(claim)
    
    # Store in history 
    import datetime
    _history.append({
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "claim": claim[:100] + ("..." if len(claim) > 100 else ""),
        "verdict": result.verdict
    })
    if len(_history) > 30:
        _history.pop(0)

    return result.to_dict()

@app.get("/history", response_model=HistoryResponse)
def get_history():
    return {"history": list(reversed(_history))}

@app.delete("/history/clear", response_model=StatusResponse)
def clear_history():
    _history.clear()
    return {"status": "success"}
