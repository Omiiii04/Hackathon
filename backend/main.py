# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from pipeline import run_pipeline

# ─────────────────────────────────────────────
# LIFESPAN — runs once at server startup/shutdown
# ─────────────────────────────────────────────
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
    claim: str


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


@app.post("/verify")
async def verify(body: VerifyRequest):
    """Main endpoint — full pipeline."""
    result = await run_pipeline(body.claim)
    return result.to_dict()
