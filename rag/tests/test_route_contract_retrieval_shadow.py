"""Shadow retrieval specifications through the public Gateway seam."""

from __future__ import annotations

import unittest

from rag.retrieval_gateway import EvidenceRetrievalGateway, ResearchRequest
from rag.retriever.hybrid import ChannelOutcome, HybridSearchOutcome, RetrievedChunk


class _EvidenceAdapter:
    def __init__(self):
        self.where = None

    async def search_with_status(
        self, query, k=5, where=None, graph_requirement="optional"
    ):
        self.where = where
        chunk = RetrievedChunk(
            text="星河模型官方发布说明。",
            source="vector",
            score=0.9,
            metadata={
                "date": "2026-07-01",
                "source": "星河实验室",
                "title": "星河模型发布说明",
                "citation_id": "ATR-20260701-STAR01",
            },
        )
        channel = ChannelOutcome(status="success", chunks=[chunk])
        return HybridSearchOutcome(
            status="ready",
            chunks=[chunk],
            channels={"vector": channel},
        )


def _claim_contract() -> dict:
    return {
        "schema_version": "atr.route/2.0",
        "request_id": "shadow-contract-test",
        "original_query": "请处理这条信息。",
        "protected_terms": [],
        "intent_signals": ["verification"],
        "primary_task_family": "claim_verification",
        "supporting_task_families": [],
        "answer_mode": "verification_verdict",
        "route_confidence": 1.0,
        "ambiguities": [],
        "delivery_contracts": [{
            "task_family": "claim_verification",
            "requested_output_form": "verification_verdict",
            "locator_kind": "none",
        }],
        "resolved_references": [],
        "supporting_contracts": [],
        "subjects": ["星河模型"],
        "topics": [],
        "claims": ["星河模型已经开放权重"],
        "temporal_constraint": {"mode": "none", "value": None},
        "source_constraint": {"requested_sources": [], "official_first": False},
        "web_permission": "on_demand",
        "rewrite_policy_id": "atr.rewrite/claim_verification/1.0",
        "retrieval_policy_id": "atr.retrieval/claim_verification/1.0",
        "prompt_contract_id": "atr.prompt/claim_verification/1.0",
        "answer_builder_contract_id": None,
        "output_schema_id": "atr.answer/verification/1.0",
        "budget_profile_id": "atr.budget/verification/1.0",
    }


def _temporal_contract(*, temporal_constraint: dict) -> dict:
    contract = _claim_contract()
    contract.update({
        "primary_task_family": "temporal_relation_exploration",
        "answer_mode": "longitudinal_trend",
        "intent_signals": ["timeline"],
        "delivery_contracts": [{
            "task_family": "temporal_relation_exploration",
            "requested_output_form": "longitudinal_trend",
            "locator_kind": "none",
        }],
        "claims": [],
        "temporal_constraint": temporal_constraint,
        "rewrite_policy_id": "atr.rewrite/temporal_relation_exploration/1.0",
        "retrieval_policy_id": "atr.retrieval/temporal_relation_exploration/1.0",
        "prompt_contract_id": "atr.prompt/temporal_relation_exploration/1.0",
        "output_schema_id": "atr.answer/temporal_relation/1.0",
        "budget_profile_id": "atr.budget/graph/1.0",
    })
    return contract


def _contract_for_route(family: str, answer_mode: str) -> dict:
    contract = _claim_contract()
    policies = {
        "item_navigation": {
            "intent_signals": ["navigation"],
            "rewrite_policy_id": "atr.rewrite/item_navigation/1.0",
            "retrieval_policy_id": "atr.retrieval/item_navigation/1.0",
            "prompt_contract_id": None,
            "answer_builder_contract_id": "atr.answer_builder/item_navigation/1.0",
            "output_schema_id": "atr.answer/navigation/1.0",
            "budget_profile_id": "atr.budget/deterministic/1.0",
        },
        "trend_discovery": {
            "intent_signals": ["trend"],
            "rewrite_policy_id": "atr.rewrite/trend_discovery/1.0",
            "retrieval_policy_id": "atr.retrieval/trend_discovery/1.0",
            "prompt_contract_id": "atr.prompt/trend_discovery/1.0",
            "answer_builder_contract_id": None,
            "output_schema_id": "atr.answer/trend/1.0",
            "budget_profile_id": "atr.budget/standard/1.0",
        },
        "temporal_relation_exploration": {
            "intent_signals": ["timeline"],
            "rewrite_policy_id": "atr.rewrite/temporal_relation_exploration/1.0",
            "retrieval_policy_id": "atr.retrieval/temporal_relation_exploration/1.0",
            "prompt_contract_id": "atr.prompt/temporal_relation_exploration/1.0",
            "answer_builder_contract_id": None,
            "output_schema_id": "atr.answer/temporal_relation/1.0",
            "budget_profile_id": "atr.budget/graph/1.0",
        },
        "claim_verification": {
            "intent_signals": ["verification"],
            "rewrite_policy_id": "atr.rewrite/claim_verification/1.0",
            "retrieval_policy_id": "atr.retrieval/claim_verification/1.0",
            "prompt_contract_id": "atr.prompt/claim_verification/1.0",
            "answer_builder_contract_id": None,
            "output_schema_id": "atr.answer/verification/1.0",
            "budget_profile_id": "atr.budget/verification/1.0",
        },
        "evidence_research": {
            "intent_signals": ["explanation"],
            "rewrite_policy_id": "atr.rewrite/evidence_research/1.0",
            "retrieval_policy_id": "atr.retrieval/evidence_research/1.0",
            "prompt_contract_id": "atr.prompt/evidence_research/1.0",
            "answer_builder_contract_id": None,
            "output_schema_id": "atr.answer/research/1.0",
            "budget_profile_id": "atr.budget/research/1.0",
        },
    }
    contract.update({
        "primary_task_family": family,
        "answer_mode": answer_mode,
        "delivery_contracts": [{
            "task_family": family,
            "requested_output_form": answer_mode,
            "locator_kind": "full_title" if family == "item_navigation" else "none",
        }],
        **policies[family],
    })
    return contract


class RouteContractRetrievalShadowTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_contract_owns_task_family_without_legacy_reclassification(self):
        gateway = EvidenceRetrievalGateway(retriever=_EvidenceAdapter())

        bundle = await gateway.retrieve(ResearchRequest(
            question="请处理这条信息。",
            route_contract=_claim_contract(),
            latest_corpus_date="2026-08-21",
        ))

        self.assertEqual(bundle.task_family, "claim_verification")
        self.assertEqual(bundle.trace["route_source"], "route_contract_v2")
        self.assertTrue(bundle.trace["shadow"])

    async def test_legacy_absolute_range_requires_reunderstanding_before_retrieval(self):
        gateway = EvidenceRetrievalGateway(retriever=_EvidenceAdapter())

        bundle = await gateway.retrieve(ResearchRequest(
            question="比较星河模型在2026年3月至2026年7月的变化。",
            route_contract=_temporal_contract(temporal_constraint={
                "mode": "absolute_range",
                "value": "2026年3月 | 2026年7月",
            }),
            latest_corpus_date="2026-08-21",
        ))

        self.assertEqual(bundle.status, "clarification_required")
        self.assertEqual(bundle.records, [])
        self.assertEqual(bundle.error_code, "route_contract_reunderstanding_required")

    async def test_absolute_range_is_applied_to_retrieval_metadata(self):
        adapter = _EvidenceAdapter()
        gateway = EvidenceRetrievalGateway(retriever=adapter)
        contract = _claim_contract()
        contract["temporal_constraint"] = {
            "mode": "absolute_range",
            "value": "2026年3月 | 2026年7月",
            "surface": "2026年3月至2026年7月",
            "start": "2026-03-01",
            "end": "2026-07-31",
        }

        await gateway.retrieve(ResearchRequest(
            question="请核验星河模型在2026年3月至2026年7月的变化。",
            route_contract=contract,
            latest_corpus_date="2026-08-21",
        ))

        self.assertEqual(adapter.where, {"$and": [
            {"effective_date": {"$gte": "2026-03-01"}},
            {"effective_date": {"$lte": "2026-07-31"}},
        ]})

    async def test_all_route_contract_families_remain_visible_at_the_gateway_output(self):
        cases = [
            ("item_navigation", "exact_item"),
            ("trend_discovery", "important_news"),
            ("temporal_relation_exploration", "longitudinal_trend"),
            ("claim_verification", "verification_verdict"),
            ("evidence_research", "explanation"),
        ]

        for family, answer_mode in cases:
            with self.subTest(family=family):
                gateway = EvidenceRetrievalGateway(retriever=_EvidenceAdapter())
                bundle = await gateway.retrieve(ResearchRequest(
                    question="请处理这条信息。",
                    route_contract=_contract_for_route(family, answer_mode),
                    latest_corpus_date="2026-08-21",
                ))

                self.assertEqual(bundle.task_family, family)
                self.assertEqual(bundle.trace["route_source"], "route_contract_v2")
                self.assertTrue(bundle.trace["shadow"])

    async def test_unknown_route_contract_family_fails_before_retrieval(self):
        adapter = _EvidenceAdapter()
        gateway = EvidenceRetrievalGateway(retriever=adapter)
        contract = _claim_contract()
        contract["primary_task_family"] = "unknown_route"

        bundle = await gateway.retrieve(ResearchRequest(
            question="请处理这条信息。",
            route_contract=contract,
            latest_corpus_date="2026-08-21",
        ))

        self.assertEqual(bundle.status, "clarification_required")
        self.assertEqual(bundle.error_code, "route_contract_reunderstanding_required")
        self.assertIsNone(adapter.where)

    async def test_route_policy_mismatch_fails_before_retrieval(self):
        adapter = _EvidenceAdapter()
        gateway = EvidenceRetrievalGateway(retriever=adapter)
        contract = _contract_for_route("trend_discovery", "important_news")
        contract["retrieval_policy_id"] = "atr.retrieval/claim_verification/1.0"

        bundle = await gateway.retrieve(ResearchRequest(
            question="最近有什么热门趋势？",
            route_contract=contract,
            latest_corpus_date="2026-08-21",
        ))

        self.assertEqual(bundle.status, "clarification_required")
        self.assertEqual(bundle.error_code, "route_contract_reunderstanding_required")
        self.assertIsNone(adapter.where)


if __name__ == "__main__":
    unittest.main()
