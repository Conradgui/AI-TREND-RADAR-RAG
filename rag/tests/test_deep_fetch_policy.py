"""Tests for bounded deep-fetch integration policy."""

import asyncio
import threading
import unittest

import pytest

from rag.deep_fetch_policy import (
    apply_deep_fetch_policy,
    apply_deep_fetch_policy_async,
    choose_deep_fetch_targets,
)


@pytest.mark.asyncio
async def test_async_policy_moves_sync_fetcher_off_event_loop():
    release = threading.Event()

    def blocking_fetcher(url):
        release.wait(timeout=1)
        return {"ok": True, "url": url}

    task = asyncio.create_task(apply_deep_fetch_policy_async(
        [{
            "evidence_type": "external",
            "source_quality": "official",
            "needs_deep_fetch": True,
            "url": "https://example.com/evidence",
        }],
        fetcher=blocking_fetcher,
    ))
    await asyncio.sleep(0.01)

    assert task.done() is False
    release.set()
    _citations, trace = await task
    assert trace["success_count"] == 1


class DeepFetchPolicyTests(unittest.TestCase):
    def test_choose_deep_fetch_targets_prioritizes_authoritative_then_weak_sources(self):
        citations = [
            {
                "evidence_type": "external",
                "source_quality": "generic",
                "needs_deep_fetch": True,
                "url": "https://generic.example/okf",
            },
            {
                "evidence_type": "external",
                "source_quality": "official",
                "needs_deep_fetch": False,
                "url": "https://cloud.google.com/okf",
            },
            {
                "evidence_type": "internal",
                "url": "https://internal.example/not-fetchable",
            },
            {
                "evidence_type": "external",
                "source_quality": "social",
                "needs_deep_fetch": True,
                "url": "https://x.com/example",
            },
        ]

        targets = choose_deep_fetch_targets(citations, max_urls=2)

        self.assertEqual([target["url"] for target in targets], [
            "https://cloud.google.com/okf",
            "https://generic.example/okf",
        ])

    def test_apply_deep_fetch_policy_attaches_records_and_trace(self):
        citations = [
            {
                "evidence_type": "external",
                "source_quality": "official",
                "needs_deep_fetch": False,
                "url": "https://cloud.google.com/okf",
            },
            {
                "evidence_type": "external",
                "source_quality": "generic",
                "needs_deep_fetch": True,
                "url": "https://generic.example/okf",
            },
        ]
        calls = []

        def fake_fetcher(url):
            calls.append(url)
            return {
                "ok": url.startswith("https://cloud.google.com"),
                "url": url,
                "final_url": url,
                "fetched_at": "2026-06-22T00:00:00+00:00",
                "title": "Fetched source",
                "text_excerpt": "Fetched source evidence.",
                "error": "" if url.startswith("https://cloud.google.com") else "network_error",
            }

        deepened, trace = apply_deep_fetch_policy(citations, fetcher=fake_fetcher, max_urls=2)

        self.assertEqual(calls, ["https://cloud.google.com/okf", "https://generic.example/okf"])
        self.assertTrue(deepened[0]["deep_fetch"]["ok"])
        self.assertFalse(deepened[1]["deep_fetch"]["ok"])
        self.assertEqual(trace["attempted"], True)
        self.assertEqual(trace["selected_count"], 2)
        self.assertEqual(trace["success_count"], 1)
        self.assertEqual(trace["failure_count"], 1)

    def test_apply_deep_fetch_policy_can_be_disabled(self):
        citations = [
            {
                "evidence_type": "external",
                "source_quality": "official",
                "url": "https://cloud.google.com/okf",
            }
        ]

        deepened, trace = apply_deep_fetch_policy(citations, fetcher=lambda url: {"ok": True}, enabled=False)

        self.assertEqual(deepened, citations)
        self.assertFalse(trace["attempted"])
        self.assertEqual(trace["reason"], "disabled")

    def test_sufficient_verified_snippet_does_not_trigger_deep_fetch(self):
        citations = [
            {
                "evidence_type": "external",
                "source_quality": "official",
                "needs_deep_fetch": False,
                "url": "https://openai.com/research/example",
                "excerpt": "A" * 240,
                "provenance_status": "verified",
                "date_status": "verified",
            }
        ]

        targets = choose_deep_fetch_targets(citations)

        self.assertEqual(targets, [])

    def test_explicit_evidence_demand_triggers_deep_fetch(self):
        citations = [
            {
                "evidence_type": "external",
                "source_quality": "official",
                "needs_deep_fetch": False,
                "url": "https://openai.com/research/example",
                "excerpt": "A" * 240,
                "provenance_status": "verified",
                "date_status": "verified",
                "evidence_demand": "verify_methodology",
            }
        ]

        targets = choose_deep_fetch_targets(citations)

        self.assertEqual([target["url"] for target in targets], ["https://openai.com/research/example"])

    def test_primary_claim_source_with_sufficient_snippet_does_not_require_independence_status(self):
        citations = [{
            "evidence_type": "external",
            "source_quality": "official",
            "source_role": "primary_claim_source",
            "needs_deep_fetch": False,
            "url": "https://openai.com/release",
            "excerpt": "A" * 240,
            "provenance_status": "unknown",
            "date_status": "verified",
        }]

        assert choose_deep_fetch_targets(citations) == []


if __name__ == "__main__":
    unittest.main()
