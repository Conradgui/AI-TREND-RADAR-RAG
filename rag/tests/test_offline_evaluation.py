"""Public-seam tests for offline frozen-run evaluation."""

import json
from pathlib import Path

import pytest

from rag.offline_evaluation import evaluate_frozen_run


DATASET = Path("docs/rag-transformation/evals/retrieval-quality-gold-candidate-v1.json")
RQ08_TARGET = "https://openai.com/index/introducing-the-openai-economic-research-exchange/"


def test_rq08_rank_one_is_a_correct_navigation_run(tmp_path):
    run_path = tmp_path / "rq08-correct.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "rq08-correct-literal",
                "dataset_id": "retrieval-quality-gold-candidate-v1",
                "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [
                    {
                        "query_id": "RQ08",
                        "retrieved": [
                            {
                                "identity": f"url:{RQ08_TARGET}",
                                "url": RQ08_TARGET,
                                "source": "OpenAI",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = evaluate_frozen_run(DATASET, run_path)

    assert report["evaluated_query_ids"] == ["RQ08"]
    assert report["release_gate_eligible"] is False
    assert report["rows"] == [
        {
            "query_id": "RQ08",
            "task_family": "item_navigation",
            "target_rank": 1,
            "hit_at_1": 1,
            "mrr": 1.0,
        }
    ]


def test_rq08_rank_five_is_visible_as_degraded_navigation(tmp_path):
    run_path = tmp_path / "rq08-degraded.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "rq08-degraded-literal",
                "dataset_id": "retrieval-quality-gold-candidate-v1",
                "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [
                    {
                        "query_id": "RQ08",
                        "retrieved": [
                            {"url": "https://example.com/noise-1", "source": "Noise"},
                            {"url": "https://example.com/noise-2", "source": "Noise"},
                            {"url": "https://example.com/noise-3", "source": "Noise"},
                            {"url": "https://example.com/noise-4", "source": "Noise"},
                            {"url": f"{RQ08_TARGET.rstrip('/')}?utm_source=fixture", "source": "OpenAI"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = evaluate_frozen_run(DATASET, run_path)

    assert report["rows"] == [
        {
            "query_id": "RQ08",
            "task_family": "item_navigation",
            "target_rank": 5,
            "hit_at_1": 0,
            "mrr": 0.2,
        }
    ]


def test_rq08_missing_target_is_wrong_navigation(tmp_path):
    run_path = tmp_path / "rq08-wrong.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "rq08-wrong-literal",
                "dataset_id": "retrieval-quality-gold-candidate-v1",
                "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [
                    {
                        "query_id": "RQ08",
                        "retrieved": [
                            {"url": "https://example.com/noise-1", "source": "Noise"},
                            {"url": "https://example.com/noise-2", "source": "Noise"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = evaluate_frozen_run(DATASET, run_path)

    assert report["rows"] == [
        {
            "query_id": "RQ08",
            "task_family": "item_navigation",
            "target_rank": None,
            "hit_at_1": 0,
            "mrr": 0.0,
        }
    ]


def test_trend_frozen_runs_distinguish_correct_degraded_and_wrong(tmp_path):
    relevant = [
        "https://openai.com/index/apple-is-getting-this-wrong/",
        "https://openai.com/index/introducing-the-openai-economic-research-exchange/",
        "https://openai.com/index/learn-teach-chatgpt-work-codex/",
    ]

    def evaluate(name, retrieved):
        run_path = tmp_path / f"{name}.json"
        run_path.write_text(json.dumps({
            "schema_version": "1.0",
            "run_id": name,
            "dataset_id": "retrieval-quality-gold-candidate-v1",
            "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
            "origin": "literal_fixture",
            "selected_query_ids": ["RQ02"],
            "results": [{"query_id": "RQ02", "retrieved": retrieved}],
        }), encoding="utf-8")
        return evaluate_frozen_run(DATASET, run_path)["rows"][0]

    correct = evaluate("trend-correct", [{"url": url} for url in relevant])
    degraded = evaluate("trend-degraded", [
        {"url": relevant[0]},
        {"url": "https://example.com/noise-1"},
        {"url": "https://example.com/noise-2"},
    ])
    wrong = evaluate("trend-wrong", [{"url": "https://example.com/noise"}])

    assert correct["task_family"] == "trend_discovery"
    assert correct["f1_at_k"] > degraded["f1_at_k"] > wrong["f1_at_k"]
    assert correct["recall_at_k"] > degraded["recall_at_k"] > wrong["recall_at_k"]


def test_unlabelled_trend_query_remains_diagnostic(tmp_path):
    run_path = tmp_path / "rq01.json"
    run_path.write_text(json.dumps({
        "schema_version": "1.0",
        "run_id": "rq01-diagnostic",
        "dataset_id": "retrieval-quality-gold-candidate-v1",
        "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
        "origin": "literal_fixture",
        "selected_query_ids": ["RQ01"],
        "results": [{"query_id": "RQ01", "retrieved": []}],
    }), encoding="utf-8")

    report = evaluate_frozen_run(DATASET, run_path)

    assert report["rows"][0]["scored"] is False
    assert report["rows"][0]["unscored_reason"] == "relevance_labels_missing"


def test_duplicate_urls_do_not_consume_multiple_ranks(tmp_path):
    run_path = tmp_path / "rq08-duplicate-noise.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "rq08-duplicate-noise-literal",
                "dataset_id": "retrieval-quality-gold-candidate-v1",
                "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [{
                    "query_id": "RQ08",
                    "retrieved": [
                        {"url": "https://example.com/noise?utm_source=one"},
                        {"url": "https://example.com/noise/"},
                        {"url": RQ08_TARGET},
                    ],
                }],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_frozen_run(DATASET, run_path)

    assert report["rows"][0]["target_rank"] == 2
    assert report["rows"][0]["mrr"] == 0.5


def test_rejects_run_for_a_different_dataset(tmp_path):
    run_path = tmp_path / "wrong-dataset.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "wrong-dataset-literal",
                "dataset_id": "another-dataset",
                "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [{"query_id": "RQ08", "retrieved": []}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="dataset_id mismatch"):
        evaluate_frozen_run(DATASET, run_path)


def test_rejects_run_for_a_different_corpus_revision(tmp_path):
    run_path = tmp_path / "wrong-revision.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "wrong-revision-literal",
                "dataset_id": "retrieval-quality-gold-candidate-v1",
                "corpus_revision": "different-revision",
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [{"query_id": "RQ08", "retrieved": []}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="corpus_revision mismatch"):
        evaluate_frozen_run(DATASET, run_path)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("duplicate_selection", "duplicate selected_query_ids"),
        ("duplicate_result", "duplicate result query_id"),
        ("missing_result", "missing selected result"),
        ("unexpected_result", "unexpected unselected result"),
    ],
)
def test_rejects_ambiguous_partial_runs(tmp_path, case, message):
    selected = ["RQ08"]
    results = [{"query_id": "RQ08", "retrieved": []}]
    if case == "duplicate_selection":
        selected.append("RQ08")
    elif case == "duplicate_result":
        results.append({"query_id": "RQ08", "retrieved": []})
    elif case == "missing_result":
        results.clear()
    elif case == "unexpected_result":
        results.append({"query_id": "RQ07", "retrieved": []})

    run_path = tmp_path / f"{case}.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": f"{case}-literal",
                "dataset_id": "retrieval-quality-gold-candidate-v1",
                "corpus_revision": "1bbc3d98270bb5e4ffcbdde29debc049ced125575c5082e01208be9aeef1fcca",
                "origin": "literal_fixture",
                "selected_query_ids": selected,
                "results": results,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        evaluate_frozen_run(DATASET, run_path)


def test_rq08_contract_requires_hit_at_one(tmp_path):
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    next(query for query in dataset["queries"] if query["id"] == "RQ08")["hit_cutoff"] = 2
    dataset_path = tmp_path / "invalid-hit-cutoff.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    run_path = tmp_path / "rq08-empty.json"
    run_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "rq08-empty-literal",
                "dataset_id": dataset["dataset_id"],
                "corpus_revision": dataset["target_snapshot"]["corpus_revision"],
                "origin": "literal_fixture",
                "selected_query_ids": ["RQ08"],
                "results": [{"query_id": "RQ08", "retrieved": []}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hit_cutoff must be 1"):
        evaluate_frozen_run(dataset_path, run_path)
