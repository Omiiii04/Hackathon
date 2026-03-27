# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from pipeline import run_pipeline

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
    """Main endpoint — full pipeline."""
    result = await run_pipeline(body.claim)
    return result.to_dict()
