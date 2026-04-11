from types import SimpleNamespace

from models import EvidenceItem
from pipeline.adversarial import compute_claim_style_risk
from pipeline.aggregator import aggregate
from pipeline.diversity import apply_independence_factors, compute_diversity_metrics
from pipeline.runtime import aggregate_compound_confidence, should_run_subclaims
from pipeline.temporal import annotate_temporal_alignment
from pipeline.verdict import compute_verdict


def make_item(
    url: str,
    stance: str = "SUPPORTING",
    credibility: float = 0.9,
    similarity: float = 0.9,
    stance_confidence: float = 0.9,
    published_at: str | None = "2026-04-09",
    title: str = "Source title",
    snippet: str = "A detailed evidence snippet with enough context to avoid prefiltering.",
):
    return EvidenceItem(
        title=title,
        snippet=snippet,
        url=url,
        source=url.split("//")[-1].split("/")[0],
        stance=stance,
        credibility=credibility,
        stance_confidence=stance_confidence,
        semantic_similarity=similarity,
        published_at=published_at,
    )


def test_diversity_penalizes_same_domain_echo_chamber():
    evidence = [
        make_item("https://www.reuters.com/a"),
        make_item("https://www.reuters.com/b"),
        make_item("https://www.bbc.com/a"),
    ]
    apply_independence_factors(evidence)
    metrics = compute_diversity_metrics(evidence)

    assert evidence[0].independence_factor == evidence[1].independence_factor
    assert evidence[0].independence_factor < evidence[2].independence_factor
    assert metrics["independent_domains"] == 2
    assert metrics["top_domain_share"] > 0.6


def test_claim_style_risk_higher_for_sensational_claim():
    plain = compute_claim_style_risk("Officials released an update on the incident.")
    sensational = compute_claim_style_risk("BREAKING!!! SHOCKING proof they don't want you to see!!!")
    assert sensational > plain
    assert sensational >= 0.4


def test_temporal_alignment_penalizes_predating_source():
    evidence = [
        make_item(
            "https://www.reuters.com/a",
            published_at="2023-01-05",
            title="Archive report",
        )
    ]
    info = annotate_temporal_alignment(evidence, "This event happened in 2024.")
    assert evidence[0].temporal_alignment < 0.5
    assert info["temporal_penalty"] > 0


def test_early_exit_requires_independent_domains():
    strong_same_domain = [
        make_item("https://www.reuters.com/a"),
        make_item("https://www.reuters.com/b"),
        make_item("https://www.reuters.com/c"),
    ]
    agg = aggregate(strong_same_domain, "Officials confirmed the claim.")
    assert agg.early_exit is False


def test_strong_multi_domain_support_true():
    evidence = [
        make_item("https://www.reuters.com/a"),
        make_item("https://www.bbc.com/a"),
        make_item("https://www.apnews.com/a"),
    ]
    agg = aggregate(evidence, "Officials confirmed the claim.")
    verdict, confidence, _, trace = compute_verdict(agg, evidence)
    assert verdict == "TRUE"
    assert confidence >= 0.7
    assert trace["independent_domains"] >= 3


def test_strong_multi_domain_contradiction_false():
    evidence = [
        make_item("https://www.reuters.com/a", stance="CONTRADICTING"),
        make_item("https://www.bbc.com/a", stance="CONTRADICTING"),
        make_item("https://www.apnews.com/a", stance="CONTRADICTING"),
    ]
    agg = aggregate(evidence, "Officials confirmed the claim.")
    verdict, _, _, _ = compute_verdict(agg, evidence)
    assert verdict == "FALSE"


def test_near_even_high_credibility_split_conflicting():
    evidence = [
        make_item("https://www.reuters.com/a", stance="SUPPORTING"),
        make_item("https://www.bbc.com/a", stance="CONTRADICTING"),
        make_item("https://www.apnews.com/a", stance="SUPPORTING", stance_confidence=0.7, similarity=0.8),
        make_item("https://www.washingtonpost.com/a", stance="CONTRADICTING", stance_confidence=0.7, similarity=0.8),
    ]
    agg = aggregate(evidence, "Officials confirmed the claim.")
    verdict, _, _, _ = compute_verdict(agg, evidence)
    assert verdict == "CONFLICTING"


def test_mixed_evidence_with_temporal_mismatch_is_misleading():
    evidence = [
        make_item("https://www.reuters.com/a", stance="SUPPORTING", published_at="2025-01-01"),
        make_item("https://www.bbc.com/a", stance="CONTRADICTING", published_at="2026-04-09"),
        make_item("https://www.apnews.com/a", stance="SUPPORTING", published_at="2025-01-15"),
    ]
    agg = aggregate(evidence, "Breaking news today: a new outbreak started yesterday.")
    verdict, _, _, trace = compute_verdict(agg, evidence)
    assert verdict == "MISLEADING"
    assert trace["temporal_penalty"] > 0.25


def test_low_diversity_support_not_true():
    evidence = [
        make_item("https://example.com/a", credibility=0.8),
        make_item("https://example.com/b", credibility=0.8),
        make_item("https://example.com/c", credibility=0.8),
    ]
    agg = aggregate(evidence, "Officials confirmed the claim.")
    verdict, _, _, _ = compute_verdict(agg, evidence)
    assert verdict in {"MISLEADING", "UNVERIFIED"}


def test_compound_gate_skips_high_confidence_true():
    parsed = SimpleNamespace(is_compound=True, sub_claims=["a", "b"])
    assert should_run_subclaims(parsed, "TRUE", 0.9) is False
    assert should_run_subclaims(parsed, "MISLEADING", 0.65) is True


def test_compound_confidence_penalizes_disagreement():
    sub_results = [
        {"text": "a", "verdict": "TRUE", "confidence": 0.8},
        {"text": "b", "verdict": "FALSE", "confidence": 0.8},
    ]
    assert aggregate_compound_confidence(sub_results, 0.9) < 0.85
