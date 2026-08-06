"""Behavior tests for canonical evidence and user-facing source labels."""

from rag.evidence_presentation import build_evidence_presentation


def test_presentation_numbers_internal_and_web_evidence_from_final_citations():
    result = build_evidence_presentation(
        "内部事实 [E3]，联网补充 [E7]，共同支持 [E3][E8]。",
        [
            {"evidence_id": "E3", "evidence_type": "internal", "title": "内部日报"},
            {"evidence_id": "E7", "evidence_type": "external", "title": "官方公告", "url": "https://example.com/release"},
            {"evidence_id": "E8", "evidence_type": "external", "title": "独立复核", "url": "https://research.example.org/check"},
        ],
    )

    assert result["evidence_display_map"] == {"E3": "I1", "E7": "W1", "E8": "W2"}
    assert result["display_answer"] == (
        "🌐 已联网补充（内部语料优先）\n\n"
        "内部事实 [I1]，联网补充 [W1 🌐]，共同支持 [I1][W2 🌐]。"
    )
    assert [citation["display_label"] for citation in result["citations"]] == ["I1", "W1", "W2"]
    assert result["source_summary"] == {
        "internal_citations": 1,
        "external_citations": 2,
        "search_references": 0,
    }


def test_presentation_does_not_number_unused_search_references_as_citations():
    result = build_evidence_presentation(
        "结论 [E1]。",
        [{"evidence_id": "E1", "evidence_type": "internal"}],
        search_references=[
            {"url": "https://example.com/unused", "source_role": "discovery_only"},
        ],
    )

    assert result["display_answer"] == "📚 仅内部语料\n\n结论 [I1]。"
    assert result["evidence_display_map"] == {"E1": "I1"}
    assert result["search_references"][0]["url"] == "https://example.com/unused"
    assert result["source_summary"]["search_references"] == 1


def test_presentation_marks_external_only_when_internal_evidence_is_unavailable():
    result = build_evidence_presentation(
        "外部结论 [E4]。",
        [{"evidence_id": "E4", "evidence_type": "external", "url": "https://example.com"}],
    )

    assert result["display_answer"] == "🌐 仅外部证据（内部语料无相关结果）\n\n外部结论 [W1 🌐]。"


def test_final_citation_wins_over_duplicate_search_reference():
    result = build_evidence_presentation(
        "外部结论 [E4]。",
        [
            {
                "evidence_id": "E4",
                "evidence_type": "external",
                "url": "https://example.com/release?utm_source=search",
            }
        ],
        search_references=[
            {"url": "https://example.com/release", "source_role": "discovery_only"},
            {"url": "https://example.com/background", "source_role": "discovery_only"},
        ],
    )

    assert [item["url"] for item in result["search_references"]] == ["https://example.com/background"]
    assert result["source_summary"]["search_references"] == 1


def test_presentation_discloses_internal_failure_when_forced_web_succeeds():
    result = build_evidence_presentation(
        "外部结论 [E4]。",
        [{"evidence_id": "E4", "evidence_type": "external", "url": "https://example.com"}],
        internal_retrieval_status="error",
        web_search_status="admitted",
    )

    assert result["display_answer"].startswith("🌐 仅外部证据（内部检索失败）")


def test_presentation_discloses_failed_web_attempt_before_internal_answer():
    result = build_evidence_presentation(
        "内部结论 [E1]。",
        [{"evidence_id": "E1", "evidence_type": "internal"}],
        web_search_status="failed",
    )

    assert result["display_answer"].startswith("⚠️ 已尝试联网但失败；以下仅展示内部语料")
