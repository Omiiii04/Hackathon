# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time

app = FastAPI(
    title="OSINT Verify API",
    description="Verify any claim using 10+ global OSINT sources",
    version="1.0.0"
)

# CORS — allows React (localhost:3000) to call this API (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # in production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (no database needed for MVP)
_cache:   dict = {}   # claim text → result
_history: list = []   # last 20 verifications


class VerifyRequest(BaseModel):
    claim: str


@app.get("/health")
def health():
    """Health check — judges and your teammate will hit this first."""
    return {"status": "ok", "message": "OSINT Verify is running"}


@app.post("/verify")
async def verify(body: VerifyRequest):
    """Main endpoint — stub for now, will wire to pipeline in Hour 8."""
    # Hardcoded for testing during Hour 0–8
    return {
        "verdict":        "FALSE",
        "confidence":     0.84,
        "explanation":    "Test response — AI pipeline not connected yet.",
        "support_ratio":  0.08,
        "evidence_count": 11,
        "sources": [
            {"title": "Test Source", "url": "https://example.com",
             "source": "Test", "credibility": "HIGH", "stance": "CONTRADICTING"}
        ],
        "algorithm_trace": {"support_ratio": 0.08, "evidence_count": 11, "tier1_count": 3},
        "cached": False,
        "processing_time_ms": 100
    }
