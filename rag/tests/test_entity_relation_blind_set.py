import json
from pathlib import Path

from rag.entity_identity import canonical_entity_id
from rag.query_understanding_v2 import understand_query_v2
from rag.retrieval_gateway import _annotate_entity_match_tier, _rank_important_news_candidates


BLIND_SET = Path(__file__).parents[2] / "docs/rag-transformation/evals/sealed/entity-relation-blind-2026-08-26.json"


def test_entity_relation_blind_set_preserves_direct_subject_and_bounded_expansion():
    cases = json.loads(BLIND_SET.read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 8
    for case in cases:
        contract = understand_query_v2(case["query"])
        assert canonical_entity_id(contract.subjects[0]) == case["subject"], case["id"]
        actual_related = [item["entity_id"] for item in contract.entity_expansions]
        assert actual_related == case["related"], case["id"]


def test_entity_relation_blind_set_does_not_collapse_product_into_company():
    cases = json.loads(BLIND_SET.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case["subject"] in {"claude", "chatgpt", "gemini", "grok"}:
            assert case["subject"] not in case["related"]
            assert canonical_entity_id(case["subject"]) == case["subject"]


def test_entity_relation_blind_set_keeps_direct_candidate_first():
    cases = json.loads(BLIND_SET.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        candidates = [_candidate(case["subject"], 40)]
        candidates.extend(_candidate(entity_id, 99) for entity_id in case["related"])
        annotated = _annotate_entity_match_tier(
            candidates,
            direct_entities=[case["subject"]],
            expansions=[{"entity_id": entity_id, "weight": 0.5} for entity_id in case["related"]],
        )
        main, *_ = _rank_important_news_candidates(
            annotated, latest_corpus_date="2026-08-20", limit=len(candidates)
        )
        assert main[0]["metadata"]["subject_entity_ids"] == [case["subject"]], case["id"]


def _candidate(subject, score):
    return {
        "text": f"{subject} announced a major product release",
        "metadata": {
            "title": subject,
            "summary": "announced a major product release",
            "evidence": "announced a major product release",
            "content_kind": "news_event",
            # Keep this ranking fixture in the primary tier; the test is about
            # direct-vs-related entity order, not ordinary launch materiality.
            "event_type": "model_release",
            "subject_entity_ids": [subject],
            "publication_date": "2026-08-20",
            "temporal_confidence": "high",
            "score": score,
            "citation_id": f"{subject}-blind",
        },
    }
