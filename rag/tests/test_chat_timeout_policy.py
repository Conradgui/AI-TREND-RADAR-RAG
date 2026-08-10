"""Unit tests for bounded chat timeout policy."""

from rag.chat_service import get_agent_timeout_seconds


def test_internal_questions_receive_a_practical_bounded_timeout():
    assert get_agent_timeout_seconds(
        needs_web_search=False,
        planned_tool_calls=1,
    ) == 75


def test_multi_tool_questions_receive_more_time_without_becoming_unbounded():
    assert get_agent_timeout_seconds(
        needs_web_search=False,
        planned_tool_calls=3,
    ) == 150


def test_web_search_questions_receive_bounded_extended_timeout():
    assert get_agent_timeout_seconds(
        needs_web_search=True,
        planned_tool_calls=4,
    ) == 180
