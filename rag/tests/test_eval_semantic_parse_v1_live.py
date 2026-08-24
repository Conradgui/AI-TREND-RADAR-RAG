"""Report-level test for the SemanticParseV1 diagnostic evaluator."""

from __future__ import annotations

import json
from pathlib import Path

from rag.eval_semantic_parse_v1_live import run


class _Client:
    model = "fake-fixed-model"

    def extract(self, query: str, context: str | None = None):
        return ({
            "subjects": ["模型水印"],
            "claims": [],
            "locators": [],
            "constraints": [
                {"kind": "time", "value": "30 days", "literal_span": "近 30 天"},
                {"kind": "importance", "value": "important", "literal_span": "重要动态"},
            ],
            "references": [],
            "task_atoms": [{
                "action": "discover", "target": "模型水印",
                "success_criterion": "汇总重要动态", "delivery_role": "main",
            }],
            "literal_spans": ["近 30 天", "模型水印"],
            "confidence": 0.95,
            "ambiguities": [],
        }, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})


def test_diagnostic_report_compares_new_and_old_route(tmp_path: Path) -> None:
    query = "汇总近 30 天模型水印的重要动态。"
    queries = {"dataset_id": "d", "cases": [{"case_id": "B1", "query": query}]}
    gold = {"dataset_id": "d", "cases": [{
        "case_id": "B1", "original_query": query,
        "intent_signals": ["recency", "importance"],
        "primary_task_family": "trend_discovery", "supporting_task_families": [],
        "answer_mode": "important_news", "web_permission": "on_demand",
        "expected_protected_terms": ["近 30 天", "模型水印"],
        "ambiguity_expected": False, "expected_resolved_references": [],
    }]}
    old = {"predictions": [{
        "case_id": "B1", "prediction": {"primary_task_family": "evidence_research"}
    }]}
    paths = []
    for name, payload in (("q.json", queries), ("g.json", gold), ("o.json", old)):
        path = tmp_path / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        paths.append(path)

    report = run(*paths, _Client())

    assert report["route"]["accuracy"] == 1
    assert report["old_route_baseline"]["net_gain_cases"] == 1
    assert report["protected_term_micro"]["f1"] == 1
    assert report["tokens"]["total"] == 15
