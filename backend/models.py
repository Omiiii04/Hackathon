# backend/models.py
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvidenceItem:
    title:       str
    snippet:     str          # short text from the source
    url:         str
    source:      str          # "Reuters", "Wikipedia", etc.
    stance:      str = "NEUTRAL"       # SUPPORTING / CONTRADICTING / NEUTRAL
    credibility: float = 0.40          # 0.0 to 1.0
    score:       float = 0.0           # credibility × relevance


@dataclass
class VerdictResult:
    verdict:          str              # TRUE/FALSE/MISLEADING/CONFLICTING/UNVERIFIED
    confidence:       float            # 0.0 to 1.0
    explanation:      str              # 2-sentence LLM explanation
    support_ratio:    float            # sup_weight / (sup_weight + con_weight)
    evidence_count:   int
    sources:          List[dict] = field(default_factory=list)
    algorithm_trace:  dict = field(default_factory=dict)
    cached:           bool = False
    processing_time_ms: int = 0
    sub_claims:       List[dict] = field(default_factory=list)   # per-subclaim breakdown
    is_compound:      bool = False                                # True if claim was split
    localized_verdict: Optional[str] = None                       # Present if translated

    def to_dict(self) -> dict:
        return {
            "verdict":            self.verdict,
            "localized_verdict":  self.localized_verdict,
            "confidence":         self.confidence,
            "explanation":        self.explanation,
            "support_ratio":      self.support_ratio,
            "evidence_count":     self.evidence_count,
            "sources":            self.sources,
            "algorithm_trace":    self.algorithm_trace,
            "cached":             self.cached,
            "processing_time_ms": self.processing_time_ms,
            "sub_claims":         self.sub_claims,
            "is_compound":        self.is_compound,
        }
