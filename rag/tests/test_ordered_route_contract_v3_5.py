"""Visible v3.5 contract calibration through the public ordered-query seam."""

from __future__ import annotations

from rag.ordered_frame_client_v3 import OrderedFrameClientV3, understand_ordered_query_v3


class ScriptedModel:
    model = "scripted-v3.5"

    def __init__(self, frame: dict):
        self.frame = frame

    def complete(self, query: str, conversation_context: str | None):
        return self.frame, {"total_tokens": 0}


def _delivery(family: str, evidence: str, output: str) -> dict:
    return {
        "task_family": family,
        "evidence_spans": [evidence],
        "requested_output_form": output,
        "locator_kind": "none",
    }


def _frame(
    *deliveries: dict,
    protected: list[str] | None = None,
    claims: list[str] | None = None,
    subjects: list[str] | None = None,
    sources: list[str] | None = None,
) -> dict:
    frame = {
        "schema_version": "atr.ordered-semantic-frame/3.0",
        "deliveries": list(deliveries),
        "protected_spans": protected or [],
        "web_permission": "on_demand",
        "web_evidence_spans": [],
        "unresolved_reference_spans": [],
    }
    if claims is not None:
        frame["claim_spans"] = claims
    if subjects is not None:
        frame["subject_spans"] = subjects
    if sources is not None:
        frame["source_spans"] = sources
    return frame


def _understand(query: str, frame: dict, context: str | None = None) -> dict:
    envelope, _ = understand_ordered_query_v3(
        query,
        OrderedFrameClientV3(ScriptedModel(frame)),
        context,
    )
    return envelope


def test_bare_reference_without_public_context_requires_clarification() -> None:
    query = "请解释它为什么值得关注。"

    envelope = _understand(
        query,
        _frame(
            _delivery("evidence_research", "解释它为什么值得关注", "explanation")
        ),
    )

    assert envelope["status"] == "clarification_required"
    assert envelope["contract"] is None
    assert "它" in envelope["reasons"][0]


def test_direct_factual_claim_is_preserved_in_route_contract() -> None:
    query = "请核验星河模型已经开放权重。"

    envelope = _understand(
        query,
        _frame(
            _delivery("claim_verification", "核验", "verification_verdict"),
            claims=["星河模型已经开放权重"],
            subjects=["星河模型"],
        ),
    )

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["claims"] == ["星河模型已经开放权重"]


def test_retrieval_only_hints_survive_without_becoming_subjects_or_claims() -> None:
    query = "最近 AI 编程助手在跨会话上下文和代码库知识上有哪些做法？"

    envelope = _understand(
        query,
        {
            **_frame(
                _delivery("trend_discovery", "最近", "important_news"),
                subjects=["AI 编程助手"],
            ),
            "retrieval_hints": [
                "persistent context across sessions",
                "codebase knowledge graph",
            ],
        },
    )

    assert envelope["status"] == "resolved"
    contract = envelope["contract"]
    assert contract["retrieval_hints"] == [
        "persistent context across sessions",
        "codebase knowledge graph",
    ]
    assert contract["subjects"] == ["AI 编程助手"]
    assert contract["claims"] == []


def test_explicit_hypothesis_is_preserved_as_a_claim() -> None:
    query = "假设星河模型采用了稀疏专家架构，请分析这个判断是否成立。"

    envelope = _understand(
        query,
        _frame(
            _delivery("claim_verification", "判断是否成立", "verification_verdict"),
            claims=["星河模型采用了稀疏专家架构"],
        ),
    )

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["claims"] == ["星河模型采用了稀疏专家架构"]


def test_arbitrary_organization_uses_a_dedicated_official_source_span() -> None:
    query = "请只用星河实验室官方材料核验星河模型已经开放权重。"

    envelope = _understand(
        query,
        _frame(
            _delivery("claim_verification", "核验", "verification_verdict"),
            protected=["星河实验室", "星河模型", "开放权重"],
            claims=["星河模型已经开放权重"],
            subjects=["星河模型"],
            sources=["星河实验室"],
        ),
    )

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["source_constraint"] == {
        "requested_sources": ["星河实验室"],
        "official_first": True,
    }
    assert "星河实验室" not in envelope["contract"]["protected_terms"]


def test_source_phrase_is_not_an_antecedent_for_a_bare_reference() -> None:
    query = "基于星河实验室官方材料解释它为什么重要。"

    envelope = _understand(
        query,
        _frame(
            _delivery("evidence_research", "解释它为什么重要", "explanation"),
            sources=["星河实验室"],
        ),
    )

    assert envelope["status"] == "clarification_required"


def test_explicit_subject_in_an_earlier_query_sentence_can_resolve_pronoun() -> None:
    query = "星河模型发布了新版本。请解释它为什么重要。"

    envelope = _understand(
        query,
        _frame(
            _delivery("evidence_research", "解释它为什么重要", "explanation"),
            subjects=["星河模型"],
        ),
    )

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["subjects"] == ["星河模型"]


def test_unresolved_publication_reference_requires_clarification() -> None:
    query = "请只用星河实验室官方材料核验这项发布。"

    envelope = _understand(
        query,
        _frame(
            _delivery("claim_verification", "核验这项发布", "verification_verdict"),
            sources=["星河实验室"],
        ),
    )

    assert envelope["status"] == "clarification_required"


def test_content_changing_negation_remains_a_protected_constraint() -> None:
    query = "解释星河模型的发布，不要扩展成行业趋势。"

    envelope = _understand(
        query,
        _frame(
            _delivery("evidence_research", "解释星河模型的发布", "explanation"),
            subjects=["星河模型"],
        ),
    )

    assert envelope["status"] == "resolved"
    assert "不要扩展成行业趋势" in envelope["contract"]["protected_terms"]


def test_absolute_period_exposes_surface_and_machine_readable_boundaries() -> None:
    query = "比较星河模型在2026年3月至2026年7月的变化。"

    envelope = _understand(
        query,
        _frame(
            _delivery(
                "temporal_relation_exploration",
                "2026年3月至2026年7月的变化",
                "longitudinal_trend",
            ),
            protected=["星河模型", "2026年3月至2026年7月"],
        ),
    )

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["temporal_constraint"] == {
        "mode": "absolute_range",
        "value": "2026年3月 | 2026年7月",
        "surface": "2026年3月至2026年7月",
        "start": "2026-03-01",
        "end": "2026-07-31",
    }


def test_reversed_absolute_period_fails_closed_before_retrieval() -> None:
    query = "比较星河模型在2026年7月至2026年3月的变化。"

    envelope = _understand(
        query,
        _frame(
            _delivery(
                "temporal_relation_exploration",
                "2026年7月至2026年3月的变化",
                "longitudinal_trend",
            ),
            subjects=["星河模型"],
        ),
    )

    assert envelope["status"] == "clarification_required"
    assert "starts after" in envelope["reasons"][0]
