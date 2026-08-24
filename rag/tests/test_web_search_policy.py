"""Behavior tests for request-scoped web-search routing."""

from types import SimpleNamespace

from rag.web_search_policy import decide_web_search


def _plan(question="稳定知识问题", *, needs_web=False, recent=False):
    return SimpleNamespace(
        original_question=question,
        needs_web_search=needs_web,
        time_window={"label": "recent_corpus_first" if recent else "unspecified", "days": 14 if recent else None},
        entities=[],
    )


def test_user_forced_web_search_runs_when_capability_is_available():
    decision = decide_web_search(
        _plan("请查官网核实"),
        requested_mode="always",
        retrieval_status="ready",
        citations=[{"date": "2026-08-06"}],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is True
    assert decision.effective_mode == "always"
    assert decision.reason == "user_forced"


def test_explicit_internal_only_text_overrides_always_mode():
    decision = decide_web_search(
        _plan("只基于内部语料回答，不要联网"),
        requested_mode="always",
        retrieval_status="ready",
        citations=[{"date": "2026-08-06"}],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is False
    assert decision.effective_mode == "never"
    assert decision.reason == "internal_only_constraint"
    assert decision.intent_constraint == "internal_only"


def test_route_contract_forbidden_web_overrides_always_mode():
    decision = decide_web_search(
        _plan("请总结内部库中的动态"),
        requested_mode="always",
        retrieval_status="ready",
        citations=[{"date": "2026-08-06"}],
        capability_available=True,
        contract_web_permission="forbidden",
        today="2026-08-06",
    )

    assert decision.should_search is False
    assert decision.effective_mode == "never"
    assert decision.reason == "route_contract_forbidden"


def test_auto_mode_uses_web_when_internal_search_is_empty():
    decision = decide_web_search(
        _plan(),
        requested_mode="auto",
        retrieval_status="empty",
        citations=[],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is True
    assert decision.reason == "internal_empty"


def test_auto_mode_does_not_hide_internal_retrieval_failure_with_web():
    decision = decide_web_search(
        _plan(),
        requested_mode="auto",
        retrieval_status="error",
        citations=[],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is False
    assert decision.reason == "internal_error"
    assert decision.evidence_quality_status == "SYSTEM_ERROR"
    assert decision.evidence_gaps == ("retrieval_error",)


def test_auto_recent_question_uses_web_when_relevant_evidence_is_stale():
    decision = decide_web_search(
        _plan("OpenAI 最近有什么动态", recent=True),
        requested_mode="auto",
        retrieval_status="ready",
        citations=[{"date": "2026-07-01"}],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is True
    assert decision.reason == "freshness_gap"


def test_auto_stable_question_keeps_internal_quality_floor_without_unneeded_web():
    decision = decide_web_search(
        _plan(),
        requested_mode="auto",
        retrieval_status="ready",
        citations=[{
            "date": "2026-07-01",
            "source": "内部日报",
            "title": "稳定知识",
            "citation_id": "stable/1",
            "excerpt": "可引用的内部证据",
        }],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is False
    assert decision.reason == "internal_ready"


def test_system_capability_boundary_blocks_all_request_modes():
    decision = decide_web_search(
        _plan("请联网搜索"),
        requested_mode="always",
        retrieval_status="empty",
        citations=[],
        capability_available=False,
        today="2026-08-06",
    )

    assert decision.should_search is False
    assert decision.effective_mode == "never"
    assert decision.reason == "capability_unavailable"


def test_structured_entity_gap_marks_nonempty_internal_evidence_partial():
    plan = _plan("OpenAI 的产品策略是什么")
    plan.entities = ["OpenAI"]

    decision = decide_web_search(
        plan,
        requested_mode="auto",
        retrieval_status="ready",
        citations=[{"date": "2026-08-05", "source": "日报", "title": "产品策略", "citation_id": "x", "excerpt": "证据"}],
        capability_available=True,
        today="2026-08-06",
    )

    assert decision.should_search is True
    assert decision.reason == "internal_partial"
    assert decision.evidence_quality_status == "PARTIAL"
    assert "entity_coverage_unverified" in decision.evidence_gaps
