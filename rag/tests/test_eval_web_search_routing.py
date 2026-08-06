"""Minimum gold-set checks for web-search routing decisions."""

from rag.eval_web_search_routing import evaluate_minimum_routing_gold_set


def test_minimum_routing_gold_set_has_no_missed_or_unnecessary_web_calls():
    report = evaluate_minimum_routing_gold_set(today="2026-08-06")

    assert report["case_count"] >= 7
    assert report["missed_web_rate"] == 0
    assert report["unnecessary_web_rate"] == 0
    assert report["failed_cases"] == []
