"""Contract tests for the route-balanced v2 development assets."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from rag.route_contract_validation import RouteContractViolation, validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json"
PROJECTION_SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/route-contract-v2-expected-projection.schema.json"
DATASET_PATH = ROOT / "docs/rag-transformation/evals/route-contract-v2-development-2026-08-13.json"

ROUTES = {
    "item_navigation",
    "trend_discovery",
    "temporal_relation_exploration",
    "claim_verification",
    "evidence_research",
}

POLICY_IDS = {
    "item_navigation": {
        "rewrite_policy_id": "atr.rewrite/item_navigation/1.0",
        "retrieval_policy_id": "atr.retrieval/item_navigation/1.0",
        "output_schema_id": "atr.answer/navigation/1.0",
        "budget_profile_id": "atr.budget/deterministic/1.0",
    },
    "trend_discovery": {
        "rewrite_policy_id": "atr.rewrite/trend_discovery/1.0",
        "retrieval_policy_id": "atr.retrieval/trend_discovery/1.0",
        "output_schema_id": "atr.answer/trend/1.0",
        "budget_profile_id": "atr.budget/standard/1.0",
    },
    "temporal_relation_exploration": {
        "rewrite_policy_id": "atr.rewrite/temporal_relation_exploration/1.0",
        "retrieval_policy_id": "atr.retrieval/temporal_relation_exploration/1.0",
        "output_schema_id": "atr.answer/temporal_relation/1.0",
        "budget_profile_id": "atr.budget/graph/1.0",
    },
    "claim_verification": {
        "rewrite_policy_id": "atr.rewrite/claim_verification/1.0",
        "retrieval_policy_id": "atr.retrieval/claim_verification/1.0",
        "output_schema_id": "atr.answer/verification/1.0",
        "budget_profile_id": "atr.budget/verification/1.0",
    },
    "evidence_research": {
        "rewrite_policy_id": "atr.rewrite/evidence_research/1.0",
        "retrieval_policy_id": "atr.retrieval/evidence_research/1.0",
        "output_schema_id": "atr.answer/research/1.0",
        "budget_profile_id": "atr.budget/research/1.0",
    },
}


class RouteContractV2AssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.projection_schema = json.loads(PROJECTION_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        self.cases = self.dataset["cases"]
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator.check_schema(self.projection_schema)
        self.contract_validator = Draft202012Validator(self.schema)
        self.projection_validator = Draft202012Validator(self.projection_schema)

    def _materialize_contract(self, case: dict) -> dict:
        expected = case["expected"]
        route = expected["primary_task_family"]
        needs_disambiguation = expected["answer_mode"] == "item_disambiguation"
        return {
            "schema_version": "atr.route/2.0",
            "request_id": case["case_id"],
            "original_query": expected["original_query"],
            "protected_terms": expected["preserve_tokens"],
            "intent_signals": expected["intent_signals"],
            "primary_task_family": route,
            "supporting_task_families": expected["supporting_task_families"],
            "answer_mode": expected["answer_mode"],
            "route_confidence": 0.6 if needs_disambiguation else 1.0,
            "ambiguities": ["item locator may match multiple records"] if needs_disambiguation else [],
            "delivery_contracts": [
                {
                    "task_family": route,
                    "requested_output_form": expected["answer_mode"],
                    "locator_kind": None if route == "item_navigation" else "none",
                },
                *[
                    {
                        "task_family": supporting,
                        "requested_output_form": None,
                        "locator_kind": None if supporting == "item_navigation" else "none",
                    }
                    for supporting in expected["supporting_task_families"]
                ],
            ],
            "resolved_references": [],
            "supporting_contracts": [
                {
                    "task_family": supporting,
                    "rewrite_policy_id": POLICY_IDS[supporting]["rewrite_policy_id"],
                    "retrieval_policy_id": POLICY_IDS[supporting]["retrieval_policy_id"],
                    "prompt_contract_id": f"atr.prompt/{supporting}/1.0",
                    "answer_builder_contract_id": None,
                    "output_schema_id": POLICY_IDS[supporting]["output_schema_id"],
                    "budget_profile_id": POLICY_IDS[supporting]["budget_profile_id"],
                }
                for supporting in expected["supporting_task_families"]
            ],
            "subjects": [],
            "topics": [],
            "claims": [],
            "temporal_constraint": {"mode": "none", "value": None},
            "source_constraint": {"requested_sources": [], "official_first": False},
            "web_permission": expected["web_permission"],
            **POLICY_IDS[route],
            "prompt_contract_id": expected["prompt_contract_id"],
            "answer_builder_contract_id": expected["answer_builder_contract_id"],
        }

    def test_schema_declares_the_five_confirmed_routes(self) -> None:
        route_enum = set(
            self.schema["$defs"]["taskRoute"]["enum"]
        )
        self.assertEqual(route_enum, ROUTES)

    def test_development_set_is_balanced_across_five_routes(self) -> None:
        self.assertEqual(len(self.cases), 25)
        counts = Counter(case["expected"]["primary_task_family"] for case in self.cases)
        self.assertEqual(counts, Counter({route: 5 for route in ROUTES}))

    def test_every_case_preserves_original_query_and_has_unique_id(self) -> None:
        ids = [case["case_id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in self.cases:
            self.assertTrue(case["query"].strip())
            self.assertEqual(case["query"], case["expected"]["original_query"])

    def test_every_expected_projection_and_materialized_contract_is_valid(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                self.projection_validator.validate(case["expected"])
                contract = self._materialize_contract(case)
                self.contract_validator.validate(contract)
                validate_route_contract_semantics(contract)

    def test_route_specific_contract_ids_do_not_conflict(self) -> None:
        for case in self.cases:
            expected = case["expected"]
            route = expected["primary_task_family"]
            if route == "item_navigation":
                self.assertIsNone(expected["prompt_contract_id"])
                self.assertTrue(expected["answer_builder_contract_id"])
            else:
                self.assertTrue(expected["prompt_contract_id"])
                self.assertIsNone(expected["answer_builder_contract_id"])

    def test_confirmed_trend_boundary_is_represented(self) -> None:
        by_id = {case["case_id"]: case for case in self.cases}
        self.assertEqual(
            by_id["RCV2-B01"]["expected"]["primary_task_family"],
            "trend_discovery",
        )
        self.assertEqual(
            by_id["RCV2-C01"]["expected"]["primary_task_family"],
            "temporal_relation_exploration",
        )
        self.assertEqual(
            by_id["RCV2-C01"]["expected"]["answer_mode"],
            "timeline",
        )

    def test_degraded_contracts_are_rejected(self) -> None:
        by_id = {case["case_id"]: case for case in self.cases}

        a_with_prompt = self._materialize_contract(by_id["RCV2-A01"])
        a_with_prompt["prompt_contract_id"] = "atr.prompt/trend_discovery/1.0"

        b_with_timeline = self._materialize_contract(by_id["RCV2-B01"])
        b_with_timeline["answer_mode"] = "timeline"

        route_mismatched_ids = self._materialize_contract(by_id["RCV2-B02"])
        route_mismatched_ids["retrieval_policy_id"] = "atr.retrieval/evidence_research/1.0"

        for name, contract in {
            "a_with_prompt": a_with_prompt,
            "b_with_timeline": b_with_timeline,
            "route_mismatched_ids": route_mismatched_ids,
        }.items():
            with self.subTest(mutation=name), self.assertRaises(ValidationError):
                self.contract_validator.validate(contract)

        duplicate_support = self._materialize_contract(by_id["RCV2-C01"])
        duplicate_support["supporting_task_families"] = [duplicate_support["primary_task_family"]]
        with self.assertRaises(RouteContractViolation):
            validate_route_contract_semantics(duplicate_support)

        lost_original_term = deepcopy(self._materialize_contract(by_id["RCV2-A01"]))
        lost_original_term["original_query"] = "打开那一条"
        with self.assertRaises(RouteContractViolation):
            validate_route_contract_semantics(lost_original_term)

        silent_disambiguation = self._materialize_contract(by_id["RCV2-A03"])
        silent_disambiguation["answer_mode"] = "item_disambiguation"
        silent_disambiguation["route_confidence"] = 1.0
        silent_disambiguation["ambiguities"] = []
        with self.assertRaisesRegex(RouteContractViolation, "disambiguation"):
            validate_route_contract_semantics(silent_disambiguation)

        missing_support_contract = self._materialize_contract(by_id["RCV2-C04"])
        missing_support_contract["supporting_contracts"] = []
        with self.assertRaisesRegex(RouteContractViolation, "supporting contracts"):
            validate_route_contract_semantics(missing_support_contract)

        mismatched_support_policy = self._materialize_contract(by_id["RCV2-C04"])
        mismatched_support_policy["supporting_contracts"][0]["prompt_contract_id"] = (
            "atr.prompt/claim_verification/1.0"
        )
        with self.assertRaisesRegex(RouteContractViolation, "supporting contract policy"):
            validate_route_contract_semantics(mismatched_support_policy)


if __name__ == "__main__":
    unittest.main()
