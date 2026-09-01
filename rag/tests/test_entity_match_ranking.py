from rag.retrieval_gateway import (
    _annotate_entity_match_tier,
    _candidates_for_entities,
    _ensure_event_contract,
    _rank_important_news_candidates,
)


def _candidate(title, subject, score):
    return {
        "text": title,
        "metadata": {
            "title": title,
            "summary": "announced major product release",
            "evidence": "announced major product release",
            "content_kind": "news_event",
            "event_type": "model_release",
            "subject_entity_ids": [subject],
            "publication_date": "2026-08-20",
            "temporal_confidence": "high",
            "score": score,
            "citation_id": title,
        },
    }


def test_direct_subject_stays_above_related_subject_even_when_related_score_is_higher():
    candidates = _annotate_entity_match_tier(
        [_candidate("Gemini direct", "gemini", 70), _candidate("Google related", "google", 99)],
        direct_entities=["Gemini"],
        expansions=[{"entity_id": "google", "relation": "owned_by", "weight": 0.45}],
    )
    main, supplementary, *_ = _rank_important_news_candidates(
        candidates, latest_corpus_date="2026-08-20", limit=2
    )
    assert [item["metadata"]["title"] for item in main] == ["Gemini direct"]
    assert [item["metadata"]["title"] for item in supplementary] == ["Google related"]


def test_registered_direct_mention_wins_over_related_metadata_entity():
    candidate = _candidate("Claude launches a new model", "anthropic", 70)
    candidate["metadata"]["summary"] = "Claude launches a new model for users."
    candidate["metadata"]["evidence"] = "Claude launches a new model for users."

    result = _annotate_entity_match_tier(
        [candidate],
        direct_entities=["Claude"],
        expansions=[{"entity_id": "anthropic", "relation": "developed_by", "weight": 0.55}],
    )

    assert result[0]["metadata"]["_entity_match_tier"] == "direct"


def test_unrelated_background_is_not_marked_as_direct_or_related():
    result = _annotate_entity_match_tier(
        [_candidate("Other", "openai", 50)],
        direct_entities=["Gemini"],
        expansions=[{"entity_id": "google", "relation": "owned_by", "weight": 0.45}],
    )
    assert result[0]["metadata"]["_entity_match_tier"] == "background"


def test_explicit_hyphenated_entity_ids_are_not_dropped_during_entity_filtering():
    candidates = [
        _candidate("Gemini Robotics", "google-deepmind", 90),
        _candidate("Claude Code", "claude-code", 90),
    ]

    focused, rejected, mode = _candidates_for_entities(
        candidates, ["google-deepmind", "gemini"]
    )

    assert [item["metadata"]["title"] for item in focused] == ["Gemini Robotics"]
    assert [item["metadata"]["title"] for item in rejected] == ["Claude Code"]
    assert mode == "event_subject"


def test_plain_recent_dynamics_keeps_fresh_direct_research_in_main_answer():
    candidate = _candidate("Claude publishes new science results", "anthropic", 93)
    candidate["metadata"].update({
        "summary": "Claude accelerates protein design research.",
        "evidence": "Claude accelerates protein design research.",
        "content_kind": "research",
        "event_type": "research_release",
    })
    annotated = _annotate_entity_match_tier(
        [candidate],
        direct_entities=["Claude"],
        expansions=[{"entity_id": "anthropic", "relation": "developed_by", "weight": 0.55}],
    )

    main, supplementary, *_ = _rank_important_news_candidates(
        annotated,
        latest_corpus_date="2026-08-20",
        limit=5,
        strict_importance=False,
    )

    assert [item["metadata"]["title"] for item in main] == [
        "Claude publishes new science results"
    ]
    assert supplementary == []


def test_specific_first_party_title_can_recover_an_unknown_legacy_event_contract():
    candidate = _candidate(
        "Gemini Robotics 2 brings whole body intelligence to robots — Google DeepMind",
        "google-deepmind",
        89,
    )
    candidate["metadata"].update({
        "content_kind": "unknown",
        "event_type": "other",
        "source_role": "first_party",
        "summary": "",
        "evidence": "",
    })
    annotated = _annotate_entity_match_tier(
        [candidate], direct_entities=["google-deepmind"], expansions=[]
    )

    main, *_ = _rank_important_news_candidates(
        annotated,
        latest_corpus_date="2026-08-21",
        limit=5,
        strict_importance=False,
    )

    assert [item["metadata"]["title"] for item in main] == [candidate["metadata"]["title"]]


def test_recent_third_party_report_date_can_rank_without_being_quarantined():
    candidate = _candidate("Gemini 3.7 Flash product report", "gemini", 53)
    candidate["metadata"].update({
        "source_role": "third_party",
        "temporal_confidence": "unknown",
        "publication_date": "",
        "effective_date": "2026-08-18",
        "effective_date_basis": "report_date_fallback",
    })
    annotated = _annotate_entity_match_tier(
        [candidate], direct_entities=["gemini"], expansions=[]
    )

    main, *_ = _rank_important_news_candidates(
        annotated,
        latest_corpus_date="2026-08-21",
        limit=5,
        strict_importance=False,
    )

    assert [item["metadata"]["title"] for item in main] == [candidate["metadata"]["title"]]


def test_generic_first_party_news_landing_page_is_not_a_news_event():
    candidate = _candidate("News — Google DeepMind", "google-deepmind", 94)
    candidate["metadata"].update({
        "source": "Google DeepMind",
        "summary": "News Discover our latest AI breakthroughs and updates.",
        "evidence": "News Discover our latest AI breakthroughs and updates.",
        "source_role": "first_party",
    })
    annotated = _annotate_entity_match_tier(
        [candidate], direct_entities=["google-deepmind"], expansions=[]
    )

    main, supplementary, background, unverified, excluded, *_ = _rank_important_news_candidates(
        annotated,
        latest_corpus_date="2026-08-21",
        limit=5,
        strict_importance=False,
    )

    assert main == []
    assert supplementary == []
    assert background == []
    assert unverified == []
    assert excluded[0]["metadata"]["title"] == "News — Google DeepMind"


def test_legacy_unknown_news_headline_receives_the_current_event_contract():
    candidate = _candidate("OpenAI rolling out ads for Europe later this month", "openai", 59)
    candidate["metadata"].update({
        "source": "Hacker News",
        "summary": "HN discussion by notenlish",
        "evidence": "HN discussion by notenlish",
        "content_kind": "unknown",
        "event_type": "other",
        "source_role": "third_party",
        "subject_entity_ids": [],
    })

    enriched = _ensure_event_contract([candidate])[0]

    assert enriched["metadata"]["content_kind"] == "news"
    assert enriched["metadata"]["event_type"] == "product_launch"
    assert enriched["metadata"]["subject_entity_ids"] == ["openai"]


def test_legacy_official_research_row_can_upgrade_from_developer_content():
    candidate = _candidate("Patterns and problems in multiagent systems", "anthropic", 93)
    candidate["metadata"].update({
        "source": "Anthropic (Claude)",
        "summary": "Frontier Red Team analysis of behavioral tendencies and systemic failures in emerging multiagent systems.",
        "evidence": "Frontier Red Team analysis of behavioral tendencies and systemic failures in emerging multiagent systems.",
        "content_kind": "developer_content",
        "event_type": "documentation_or_tutorial",
        "source_role": "first_party",
    })

    enriched = _ensure_event_contract([candidate])[0]

    assert enriched["metadata"]["content_kind"] == "research"
    assert enriched["metadata"]["event_type"] == "research_release"


def test_high_impact_official_policy_and_safety_events_reach_main_news_list():
    candidates = []
    for title, summary in (
        (
            "How Claude's text watermarking works",
            "Announcements explain how major model developers will comply with the EU AI Act.",
        ),
        (
            "Patterns and problems in multiagent systems",
            "Red Team analysis describes agent interaction, behavioral tendencies, and systemic failures.",
        ),
    ):
        candidate = _candidate(title, "anthropic", 93)
        candidate["metadata"].update({
            "source": "Anthropic (Claude)",
            "summary": summary,
            "evidence": summary,
            "content_kind": "developer_content",
            "event_type": "documentation_or_tutorial",
            "source_role": "first_party",
        })
        candidates.append(candidate)

    enriched = _ensure_event_contract(candidates)
    annotated = _annotate_entity_match_tier(
        enriched, direct_entities=["anthropic"], expansions=[]
    )
    main, *_ = _rank_important_news_candidates(
        annotated,
        latest_corpus_date="2026-08-21",
        limit=5,
        strict_importance=True,
    )

    assert {item["metadata"]["title"] for item in main} == {
        "How Claude's text watermarking works",
        "Patterns and problems in multiagent systems",
    }
