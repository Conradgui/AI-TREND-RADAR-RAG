"""Tests for batched external evidence acquisition planning."""

import unittest

from rag.evidence_batch_plan import (
    build_batched_evidence_acquisition_plan,
    execute_batched_evidence_acquisition_plan,
)


SAMPLE_MATRIX = {
    "artifact": "docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md",
    "topic": "RAG",
    "relevance_status": "relevance_verified",
    "reviews": [
        {
            "citation_id": "https://arxiv.org/html/example",
            "source": "arxiv.org",
            "relevance_label": "direct_support",
        },
        {
            "citation_id": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
            "source": "en.wikipedia.org",
            "relevance_label": "weak_context",
        },
        {
            "citation_id": "https://www.braintrust.dev/articles/best-rag-evaluation-tools",
            "source": "www.braintrust.dev",
            "relevance_label": "partial_support",
        },
    ],
}


class EvidenceBatchPlanTests(unittest.TestCase):
    def test_builds_no_network_batch_plan_from_relevance_matrix(self):
        plan = build_batched_evidence_acquisition_plan(
            SAMPLE_MATRIX,
            configured_providers={"brave", "tavily", "exa"},
            max_total_calls=4,
        )

        self.assertEqual(plan["topic"], "RAG")
        self.assertEqual(plan["external_api_calls"], 0)
        self.assertEqual(plan["execution_status"], "planned_not_executed")
        self.assertEqual(plan["budget"]["max_results_per_call"], 8)
        self.assertEqual(plan["budget"]["planned_calls"], 4)
        self.assertEqual(len(plan["claim_gaps"]), 2)
        self.assertEqual(len(plan["search_tasks"]), 2)

    def test_partial_support_prefers_research_provider_route(self):
        plan = build_batched_evidence_acquisition_plan(
            SAMPLE_MATRIX,
            configured_providers={"brave", "tavily", "exa"},
        )

        task = next(task for task in plan["search_tasks"] if task["gap_id"].startswith("www-braintrust-dev"))

        self.assertEqual(task["task_type"], "research_paper")
        self.assertEqual(task["available_provider_chain"], ["exa", "tavily"])
        self.assertIn("benchmark", task["query"])

    def test_exploration_mode_pools_more_providers_and_results(self):
        plan = build_batched_evidence_acquisition_plan(
            SAMPLE_MATRIX,
            configured_providers={"brave", "tavily", "exa", "github"},
            strategy_mode="exploration",
        )

        task = next(task for task in plan["search_tasks"] if task["gap_id"].startswith("www-braintrust-dev"))

        self.assertEqual(plan["budget"]["strategy_mode"], "exploration")
        self.assertEqual(plan["budget"]["max_results_per_call"], 15)
        self.assertEqual(plan["budget"]["max_total_calls"], 8)
        self.assertEqual(task["available_provider_chain"], ["exa", "tavily", "brave"])

    def test_weak_context_gets_authoritative_definition_gap(self):
        plan = build_batched_evidence_acquisition_plan(
            SAMPLE_MATRIX,
            configured_providers={"brave", "tavily", "exa"},
        )

        task = next(task for task in plan["search_tasks"] if task["gap_id"].startswith("en-wikipedia-org"))

        self.assertEqual(task["task_type"], "technical_article")
        self.assertEqual(task["available_provider_chain"], ["exa", "tavily"])
        self.assertIn("authoritative", task["query"])

    def test_missing_direct_support_creates_p0_gap(self):
        matrix = {
            "topic": "RAG",
            "reviews": [{"source": "example.com", "relevance_label": "partial_support"}],
        }

        plan = build_batched_evidence_acquisition_plan(matrix, configured_providers={"exa", "tavily"})

        self.assertEqual(plan["claim_gaps"][0]["gap_id"], "missing-direct-support")
        self.assertEqual(plan["claim_gaps"][0]["priority"], "P0")


class EvidenceBatchExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_planned_provider_calls_with_budget(self):
        plan = build_batched_evidence_acquisition_plan(
            SAMPLE_MATRIX,
            configured_providers={"brave", "tavily", "exa"},
            max_total_calls=3,
            execute=True,
        )
        registry = FakeRegistry()

        result = await execute_batched_evidence_acquisition_plan(plan, registry, max_total_calls=3)

        self.assertEqual(result["execution_status"], "executed")
        self.assertEqual(result["external_api_calls"], 3)
        self.assertEqual(len(registry.requests), 3)
        self.assertEqual(result["citation_count"], 3)
        self.assertEqual(result["claim_gap_results"][0]["citation_count"], 2)
        self.assertEqual(result["claim_gap_results"][1]["citation_count"], 1)


class FakeRegistry:
    def __init__(self):
        self.requests = []

    async def search(self, request):
        self.requests.append(request)
        return {
            "provider": request.provider,
            "available": True,
            "query": request.query,
            "task_type": request.task_type,
            "citations": [
                {
                    "evidence_type": "external",
                    "provider": request.provider,
                    "source": f"{request.provider}.example",
                    "source_type": "web",
                    "title": f"{request.provider} result",
                    "url": f"https://{request.provider}.example/result",
                    "retrieved_at": "2026-06-25",
                    "excerpt": "Relevant evidence excerpt.",
                    "relevance_score": 0.9,
                }
            ],
            "raw_results_count": 1,
            "errors": [],
        }


if __name__ == "__main__":
    unittest.main()
