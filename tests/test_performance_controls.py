from models import EvidenceItem
from pipeline.runtime import run_deterministic_verdict
from pipeline.stance import classify_stance_bulk


def make_item(url: str, stance: str = "SUPPORTING"):
    return EvidenceItem(
        title="Long enough title",
        snippet="This is a sufficiently detailed snippet that mentions the claim and avoids prefiltering.",
        url=url,
        source=url.split("//")[-1].split("/")[0],
        stance=stance,
        credibility=0.95,
        stance_confidence=0.95,
        semantic_similarity=0.92,
        published_at="2026-04-09",
    )


def test_staged_runtime_skips_stage2_when_stage1_is_sufficient(monkeypatch):
    stage1_items = [
        make_item("https://www.reuters.com/a"),
        make_item("https://www.bbc.com/a"),
        make_item("https://www.apnews.com/a"),
    ]

    async def fake_collect(claim, stage, max_per_source=None, client=None):
        if stage == 1:
            return stage1_items
        raise AssertionError("stage 2 should not be fetched")

    monkeypatch.setattr("pipeline.runtime.collect_evidence_stage", fake_collect)
    monkeypatch.setattr("pipeline.runtime.rank_evidence", lambda emb, evidence: evidence)
    monkeypatch.setattr("pipeline.runtime.classify_stance_bulk", lambda evidence, claim: evidence)

    result = __import__("asyncio").run(run_deterministic_verdict("Officials confirmed the claim.", claim_embedding=[0.1]))
    assert result.used_stage2 is False
    assert result.verdict == "TRUE"


def test_batched_stance_reduces_model_invocations(monkeypatch):
    calls = {"count": 0}

    def fake_classifier(texts, candidate_labels, hypothesis_template=None, batch_size=None):
        calls["count"] += 1
        return [
            {"labels": ["supports the claim", "neutral or unrelated", "contradicts the claim"], "scores": [0.91, 0.05, 0.04]}
            for _ in texts
        ]

    monkeypatch.setattr("pipeline.stance._get_classifier", lambda: fake_classifier)

    evidence = [
        EvidenceItem(
            title=f"Title {idx}",
            snippet="This sufficiently long snippet repeats the claim in neutral language.",
            url=f"https://www.example{idx}.com/a",
            source=f"example{idx}",
            credibility=0.8,
            semantic_similarity=0.8,
        )
        for idx in range(17)
    ]

    classify_stance_bulk(evidence, "The claim is repeated here.", batch_size=8)
    assert calls["count"] == 3
    assert all(item.stance == "SUPPORTING" for item in evidence)
