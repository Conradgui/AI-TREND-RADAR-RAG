from rag.run_g2_retrieval_snapshot import collect_snapshot


def test_collect_snapshot_uses_internal_only_requests_and_preserves_case_ids():
    calls = []

    def fake_request(message, *, web_search_mode, timeout_seconds):
        calls.append((message, web_search_mode, timeout_seconds))
        return {
            "answer": "ok",
            "citations": [{"occurrence_id": "ATR-1"}],
            "tool_trace": {"execution_path": "deterministic_navigation"},
        }

    gold = {
        "schema_version": "gold/1.0",
        "review_status": "human_reviewed",
        "corpus_boundary": {"activity_cutoff": "2026-08-21"},
        "cases": [{"case_id": "case-1", "query": "打开条目"}],
    }

    snapshot = collect_snapshot(gold, fake_request, timeout_seconds=17)

    assert calls == [("打开条目", "never", 17)]
    assert snapshot["dataset_schema_version"] == "gold/1.0"
    assert snapshot["corpus_boundary"] == {"activity_cutoff": "2026-08-21"}
    assert snapshot["rows"] == [{
        "case_id": "case-1",
        "query": "打开条目",
        "response": {
            "answer": "ok",
            "citations": [{"occurrence_id": "ATR-1"}],
            "tool_trace": {"execution_path": "deterministic_navigation"},
        },
    }]


def test_collect_snapshot_records_request_failure_without_losing_remaining_cases():
    def fake_request(message, **_kwargs):
        if message == "bad":
            raise RuntimeError("service unavailable")
        return {"answer": "ok", "citations": []}

    snapshot = collect_snapshot(
        {
            "schema_version": "gold/1.0",
            "review_status": "human_reviewed",
            "cases": [
                {"case_id": "bad-case", "query": "bad"},
                {"case_id": "good-case", "query": "good"},
            ],
        },
        fake_request,
        timeout_seconds=10,
    )

    assert snapshot["rows"][0]["error"] == "service unavailable"
    assert snapshot["rows"][1]["response"]["answer"] == "ok"


def test_collect_snapshot_pauses_between_rate_limit_batches():
    sleeps = []

    snapshot = collect_snapshot(
        {
            "schema_version": "gold/1.0",
            "review_status": "human_reviewed",
            "cases": [
                {"case_id": "one", "query": "one"},
                {"case_id": "two", "query": "two"},
                {"case_id": "three", "query": "three"},
            ],
        },
        lambda message, **_kwargs: {"answer": message, "citations": []},
        timeout_seconds=10,
        batch_size=2,
        batch_pause_seconds=61,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [61]
    assert [row["case_id"] for row in snapshot["rows"]] == ["one", "two", "three"]


def test_collect_snapshot_resumes_completed_cases_and_checkpoints_each_new_row():
    calls = []
    checkpoints = []
    gold = {
        "schema_version": "gold/1.0",
        "review_status": "human_reviewed",
        "cases": [
            {"case_id": "already-done", "query": "first"},
            {"case_id": "pending", "query": "second"},
        ],
    }

    snapshot = collect_snapshot(
        gold,
        lambda message, **_kwargs: calls.append(message) or {"answer": message, "citations": []},
        timeout_seconds=10,
        existing_rows=[{
            "case_id": "already-done", "query": "first",
            "response": {"answer": "first", "citations": []},
        }],
        checkpoint_fn=lambda current: checkpoints.append(current),
    )

    assert calls == ["second"]
    assert [row["case_id"] for row in snapshot["rows"]] == ["already-done", "pending"]
    assert len(checkpoints) == 1
    assert [row["case_id"] for row in checkpoints[0]["rows"]] == ["already-done", "pending"]
