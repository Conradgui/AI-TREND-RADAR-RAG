"""Behavior tests for user-visible chat performance metrics."""

from rag.metrics import MetricsCollector
from rag import chat_service


def test_recent_metrics_expose_timeout_and_stage_timings():
    collector = MetricsCollector()
    collector.record_chat_request(
        query_length=10,
        citation_count=0,
        internal_citation_count=0,
        external_citation_count=0,
        tool_calls_count=0,
        web_search_count=0,
        deep_fetch_count=0,
        model_calls_count=5,
        has_results=False,
        response_time_ms=27_000,
        retrieval_ms=1_500,
        agent_ms=25_000,
        repair_ms=0,
        agent_timeout=True,
    )

    sample = collector.get_recent_samples(1)[0]

    assert sample["agent_timeout"] is True
    assert sample["model_calls_count"] == 5
    assert sample["retrieval_ms"] == 1_500
    assert sample["agent_ms"] == 25_000
    assert sample["repair_ms"] == 0
    assert sample["total_ms"] == 27_000


def test_summary_reports_average_stage_timings():
    collector = MetricsCollector()
    common = {
        "query_length": 10,
        "citation_count": 2,
        "internal_citation_count": 2,
        "external_citation_count": 0,
        "tool_calls_count": 1,
        "web_search_count": 0,
        "deep_fetch_count": 0,
        "model_calls_count": 1,
        "has_results": True,
    }
    collector.record_chat_request(
        **common,
        response_time_ms=10_000,
        retrieval_ms=1_000,
        agent_ms=8_000,
        repair_ms=0,
    )
    collector.record_chat_request(
        **common,
        response_time_ms=20_000,
        retrieval_ms=3_000,
        agent_ms=14_000,
        repair_ms=2_000,
    )

    summary = collector.get_summary().to_dict()

    assert summary["avg_retrieval_ms"] == 2_000
    assert summary["avg_agent_ms"] == 11_000
    assert summary["avg_repair_ms"] == 1_000
    assert summary["avg_response_time_ms"] == 15_000
    assert summary["avg_model_calls_per_request"] == 1


def test_chat_metric_counts_actual_search_attempts_not_external_citations(monkeypatch):
    recorded = {}

    class Recorder:
        def record_chat_request(self, **kwargs):
            recorded.update(kwargs)

    monkeypatch.setattr(chat_service, "metrics_collector", Recorder())
    chat_service._record_metrics(
        query_length=20,
        citations=[],
        tool_calls_count=0,
        has_results=False,
        start_time=chat_service.time.perf_counter(),
        web_search_count=1,
        deep_fetch_count=0,
    )

    assert recorded["external_citation_count"] == 0
    assert recorded["web_search_count"] == 1


def test_summary_separates_search_and_deep_fetch_counts_and_latency_percentiles():
    collector = MetricsCollector()
    for response_time, provider_calls, candidates, admitted, deep_success, deep_failure in [
        (1_000, 0, 0, 0, 0, 0),
        (2_000, 1, 10, 2, 1, 0),
        (8_000, 2, 20, 1, 0, 1),
    ]:
        collector.record_chat_request(
            query_length=10,
            citation_count=admitted,
            internal_citation_count=0,
            external_citation_count=admitted,
            tool_calls_count=1,
            web_search_count=provider_calls,
            deep_fetch_count=deep_success + deep_failure,
            has_results=True,
            response_time_ms=response_time,
            search_candidate_count=candidates,
            admitted_external_count=admitted,
            deep_fetch_success_count=deep_success,
            deep_fetch_failure_count=deep_failure,
        )

    summary = collector.get_summary().to_dict()

    assert summary["response_time_p50_ms"] == 2_000
    assert summary["response_time_p95_ms"] == 8_000
    assert summary["web_search_request_count"] == 2
    assert summary["provider_call_count"] == 3
    assert summary["search_candidate_count"] == 30
    assert summary["admitted_external_count"] == 3
    assert summary["deep_fetch_success_count"] == 1
    assert summary["deep_fetch_failure_count"] == 1
