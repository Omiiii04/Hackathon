"""
backend/models.py
------------------
Core data classes shared across the pipeline.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvidenceItem:
    title: str
    snippet: str                     # text from the source
    url: str
    source: str                      # "Reuters", "Wikipedia", etc.
    stance: str = "NEUTRAL"          # SUPPORTING / CONTRADICTING / NEUTRAL
    credibility: float = 0.40        # 0.0 to 1.0
    score: float = 0.0               # composite weight in aggregation
    stance_confidence: float = 0.5   # BART-MNLI confidence for the stance label
    semantic_similarity: float = 0.5 # MiniLM cosine similarity to claim
    published_days_ago: int = 30     # recency (default 30 days if unknown)


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
