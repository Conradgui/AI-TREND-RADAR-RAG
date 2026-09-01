from pathlib import Path

import pytest

from rag.entity_identity import related_entity_expansions
from rag.entity_relation_memory import EntityRelationMemory
from rag.query_understanding import analyze_query


def test_candidate_is_isolated_until_evidence_verifies_it(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")

    candidate = memory.observe(
        "antigravity",
        "google",
        "product_of",
        parser_version="test-parser/1",
    )

    assert candidate["status"] == "candidate"
    assert memory.verified_expansions(["antigravity"]) == []

    verified = memory.decide(
        candidate["candidate_id"],
        "verified",
        evidence=[{"url": "https://example.com/official", "supports": True}],
    )

    assert verified["status"] == "verified"
    assert memory.verified_expansions(["antigravity"]) == [
        {
            "from_entity_id": "antigravity",
            "entity_id": "google",
            "relation": "product_of",
            "weight": 0.5,
            "provenance": "learned_verified",
        }
    ]


def test_repeated_observation_reuses_one_candidate(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")

    first = memory.observe("grok", "xai", "product_of", parser_version="p1")
    second = memory.observe("Grok", "xAI", "product_of", parser_version="p2")

    assert first["candidate_id"] == second["candidate_id"]
    assert second["observation_count"] == 2


def test_verification_requires_traceable_supporting_evidence(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe("tool", "company", "product_of")

    with pytest.raises(ValueError, match="supporting evidence"):
        memory.decide(candidate["candidate_id"], "verified", evidence=[])

    with pytest.raises(ValueError, match="supporting evidence"):
        memory.decide(
            candidate["candidate_id"],
            "verified",
            evidence=[{"summary": "model thinks so", "supports": True}],
        )


def test_verification_can_reuse_evidence_recorded_during_observation(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe(
        "tool",
        "company",
        "product_of",
        evidence=[{"atr_id": "ATR-20260820-ABC123", "supports": True}],
    )

    verified = memory.decide(candidate["candidate_id"], "verified")

    assert verified["status"] == "verified"


def test_revoked_relation_immediately_stops_expanding(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe("product", "company", "product_of")
    memory.decide(
        candidate["candidate_id"],
        "verified",
        evidence=[{"atr_id": "ATR-20260820-ABC123", "supports": True}],
    )
    assert memory.verified_expansions(["product"])

    revoked = memory.decide(candidate["candidate_id"], "revoked", reason="source corrected")

    assert revoked["status"] == "revoked"
    assert memory.verified_expansions(["product"]) == []


def test_rejected_or_revoked_decision_requires_a_reason(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe("product", "company", "product_of")

    with pytest.raises(ValueError, match="reason"):
        memory.decide(candidate["candidate_id"], "rejected")


def test_query_expansion_combines_curated_and_verified_memory(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe("antigravity", "google", "product_of")
    memory.decide(
        candidate["candidate_id"],
        "verified",
        evidence=[{"url": "https://example.com/official", "supports": True}],
    )

    assert related_entity_expansions(["Antigravity"], memory=memory) == [
        {
            "from_entity_id": "antigravity",
            "entity_id": "google",
            "relation": "product_of",
            "weight": 0.5,
            "provenance": "learned_verified",
        }
    ]


def test_query_plan_reuses_verified_memory_without_a_model_call(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe("antigravity", "google", "product_of")
    memory.decide(
        candidate["candidate_id"],
        "verified",
        evidence=[{"url": "https://example.com/official", "supports": True}],
    )

    plan = analyze_query(
        "Antigravity 最近有什么动态？",
        entity_relation_memory=memory,
    )

    assert plan.entity_expansions == [
        {
            "from_entity_id": "antigravity",
            "entity_id": "google",
            "relation": "product_of",
            "weight": 0.5,
            "provenance": "learned_verified",
        }
    ]
    assert "google" in plan.retrieval_query.casefold()
