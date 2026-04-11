"""
backend/models.py
------------------
Core data classes shared across the pipeline.

FIX LOG:
  - EvidenceItem: added published_at, risk_flags, domain, root_domain,
    independence_factor, temporal_alignment — all referenced by
    temporal.py, diversity.py, and runtime.py but previously missing.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvidenceItem:
    title: str
    snippet: str                        # text from the source
    url: str
    source: str                         # "Reuters", "Wikipedia", etc.
    stance: str = "NEUTRAL"             # SUPPORTING / CONTRADICTING / NEUTRAL
    credibility: float = 0.40           # 0.0 to 1.0
    score: float = 0.0                  # composite weight in aggregation
    stance_confidence: float = 0.5      # BART-MNLI confidence for the stance label
    semantic_similarity: float = 0.5    # MiniLM cosine similarity to claim
    published_days_ago: int = 30        # recency (default 30 days if unknown)

    # --- fields added to fix AttributeError in temporal.py / diversity.py ---
    published_at: Optional[str] = None  # ISO date string "YYYY-MM-DD", or None
    risk_flags: List[str] = field(default_factory=list)  # e.g. ["stale_source"]
    domain: str = ""                    # e.g. "reuters.com"
    root_domain: str = ""               # e.g. "reuters.com" (registrable root)
    independence_factor: float = 1.0    # penalises same-domain repetition
    temporal_alignment: float = 1.0     # 0–1; reduced for pre-dating sources


@dataclass
class VerdictResult:
    verdict: str                     # TRUE / FALSE / MISLEADING / CONFLICTING / UNVERIFIED
    confidence: float                # 0.0 to 1.0
    explanation: str                 # LLM-generated explanation
    support_ratio: float             # sup_weight / (sup_weight + con_weight)
    evidence_count: int
    sources: List[dict] = field(default_factory=list)
    algorithm_trace: dict = field(default_factory=dict)
    cached: bool = False
    processing_time_ms: int = 0
    sub_claims: List[dict] = field(default_factory=list)
    is_compound: bool = False
    is_mutation: bool = False
    mutation_chain: List[dict] = field(default_factory=list)
    localized_verdict: Optional[str] = None
    llm_provider: str = "template"
    claim_type: str = "general"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "localized_verdict": self.localized_verdict,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "llm_provider": self.llm_provider,
            "support_ratio": self.support_ratio,
            "evidence_count": self.evidence_count,
            "sources": self.sources,
            "algorithm_trace": self.algorithm_trace,
            "cached": self.cached,
            "processing_ms": self.processing_time_ms,
            "processing_time_ms": self.processing_time_ms,
            "sub_claims": self.sub_claims,
            "is_compound": self.is_compound,
            "is_mutation": self.is_mutation,
            "mutation_chain": self.mutation_chain,
            "claim_type": self.claim_type,
        }