from rag.eval_g2_retrieval import score_case, summarize_scores


def test_item_navigation_scores_target_rank_and_exact_hit():
    case = {
        "case_id": "nav-1",
        "task_family": "item_navigation",
        "relevant_occurrence_ids": ["ATR-1"],
    }
    response = {
        "citations": [
            {"occurrence_id": "ATR-NOISE"},
            {"occurrence_id": "ATR-1"},
        ],
        "tool_trace": {"execution_path": "deterministic_navigation"},
    }

    scored = score_case(case, response)

    assert scored["passed"] is True
    assert scored["target_rank"] == 2
    assert scored["recall_at_5"] == 1.0


def test_trend_scores_primary_only_in_main_layer_and_supporting_as_accepted():
    case = {
        "case_id": "trend-1",
        "task_family": "recent_trend",
        "relevant_occurrence_ids": {
            "primary": ["ATR-A", "ATR-B"],
            "supporting": ["ATR-C"],
        },
        "labels_exhaustive": True,
    }
    response = {
        "citations": [
            {"occurrence_id": "ATR-A", "news_tier": "direct"},
            {"occurrence_id": "ATR-C", "news_tier": "supplementary"},
            {"occurrence_id": "ATR-X", "news_tier": "background"},
        ]
    }

    scored = score_case(case, response)

    assert scored["primary_recall"] == 0.5
    assert scored["main_precision"] == 1.0
    assert scored["supporting_hits"] == ["ATR-C"]
    assert scored["passed"] is False


def test_trend_does_not_treat_unjudged_items_as_false_positives_when_labels_are_partial():
    case = {
        "case_id": "trend-partial",
        "task_family": "recent_trend",
        "relevant_occurrence_ids": {
            "primary": ["ATR-A", "ATR-B", "ATR-C"],
            "supporting": [],
        },
        "labels_exhaustive": False,
        "minimum_primary_hits": 2,
    }
    response = {
        "citations": [
            {"occurrence_id": "ATR-A", "news_tier": "direct"},
            {"occurrence_id": "ATR-B", "news_tier": "direct"},
            {"occurrence_id": "ATR-UNJUDGED", "news_tier": "direct"},
        ]
    }

    scored = score_case(case, response)

    assert scored["passed"] is True
    assert scored["primary_recall"] == 0.6667
    assert scored["main_precision"] is None
    assert scored["unjudged_main_occurrence_ids"] == ["ATR-UNJUDGED"]


def test_clarification_requires_no_retrieval_or_model_turn():
    case = {
        "case_id": "clarify-1",
        "task_family": "evidence_insufficiency",
        "answer_mode": "clarification_required",
        "relevant_occurrence_ids": [],
    }
    response = {
        "citations": [],
        "tool_trace": {
            "execution_path": "clarification_required",
            "execution_counts": {"model_turns": 0},
        },
    }

    scored = score_case(case, response)

    assert scored["passed"] is True
    assert scored["clarification_without_model"] is True


def test_comparison_accepts_a_later_occurrence_of_the_same_stable_content():
    case = {
        "case_id": "comparison-content-identity",
        "task_family": "relation_comparison",
        "relevant_occurrence_ids": ["ATR-20260821-MEM001", "ATR-20260821-GRAPH1"],
        "relevant_content_ids": ["content-claude-mem", "content-graphify"],
    }
    response = {
        "citations": [
            {
                "occurrence_id": "ATR-20260824-MEM002",
                "content_id": "content-claude-mem",
            },
            {
                "occurrence_id": "ATR-20260821-GRAPH1",
                "content_id": "content-graphify",
            },
        ]
    }

    scored = score_case(case, response)

    assert scored["passed"] is True
    assert scored["recall"] == 1.0
    assert scored["precision"] == 1.0


def test_trend_diagnostic_does_not_label_a_content_equivalent_as_unjudged():
    case = {
        "case_id": "trend-content-identity",
        "task_family": "recent_trend",
        "relevant_occurrence_ids": {"primary": ["ATR-OLD"], "supporting": []},
        "relevant_content_ids": {"primary": ["content-stable"], "supporting": []},
        "labels_exhaustive": False,
        "minimum_primary_hits": 1,
    }
    response = {
        "citations": [{
            "occurrence_id": "ATR-NEW",
            "content_id": "content-stable",
            "news_tier": "direct",
        }]
    }

    scored = score_case(case, response)

    assert scored["passed"] is True
    assert scored["unjudged_main_occurrence_ids"] == []


def test_summary_keeps_task_families_separate_instead_of_fake_global_f1():
    summary = summarize_scores(
        [
            {"case_id": "n1", "task_family": "item_navigation", "passed": True},
            {"case_id": "t1", "task_family": "recent_trend", "passed": False},
        ]
    )

    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["by_task_family"]["item_navigation"]["passed"] == 1
    assert summary["by_task_family"]["recent_trend"]["passed"] == 0
    assert "f1" not in summary
