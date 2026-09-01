from pathlib import Path

import pytest

from rag.entity_relation_feedback import capture_relation_feedback
from rag.entity_relation_memory import EntityRelationMemory
from rag.query_route_resolver import QueryRouteResolver
from rag.query_understanding import analyze_query


def test_official_cited_relation_becomes_reusable_without_another_model(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")

    feedback = capture_relation_feedback(
        "NovaFlow 是 Google 推出的 AI 产品。[E1]",
        [{
            "evidence_id": "E1",
            "source": "Google",
            "source_quality": "official",
            "url": "https://blog.google/products/novaflow",
        }],
        subjects=["NovaFlow"],
        memory=memory,
    )

    assert feedback[0]["status"] == "verified"
    plan = analyze_query(
        "NovaFlow 最近有什么动态？",
        entity_relation_memory=memory,
    )
    assert plan.entities == ["novaflow"]
    assert plan.entity_expansions[0]["entity_id"] == "google"
    assert "google" in plan.retrieval_query.casefold()


def test_non_primary_citation_stays_candidate_and_cannot_expand(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")

    feedback = capture_relation_feedback(
        "NovaFlow 是 Google 推出的 AI 产品。[E1]",
        [{
            "evidence_id": "E1",
            "source": "Example News",
            "source_quality": "trusted_media",
            "url": "https://news.example/novaflow",
        }],
        subjects=["NovaFlow"],
        memory=memory,
    )

    assert feedback[0]["status"] == "candidate"
    assert memory.verified_expansions(["novaflow"]) == []
    assert memory.query_entity_ids("NovaFlow 最近有什么动态？") == []


def test_uncited_relation_is_not_learned(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")

    feedback = capture_relation_feedback(
        "NovaFlow 是 Google 推出的 AI 产品。",
        [],
        subjects=["NovaFlow"],
        memory=memory,
    )

    assert feedback == []


@pytest.mark.asyncio
async def test_verified_learned_subject_routes_locally_on_next_request(tmp_path: Path) -> None:
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe(
        "novaflow",
        "google",
        "product_of",
        evidence=[{"url": "https://google.example/novaflow", "supports": True}],
    )
    memory.decide(candidate["candidate_id"], "verified")

    async def forbidden_fallback(_query: str, _context: dict):
        raise AssertionError("verified learned subjects must not call the model")

    envelope, metadata = await QueryRouteResolver(
        forbidden_fallback,
        entity_relation_memory=memory,
    )("NovaFlow 最近有什么动态？", {})

    assert envelope["contract"]["subjects"] == ["novaflow"]
    assert metadata["model_calls"] == 0
