from rag.retriever.lexical_store import LexicalStore


DOCUMENTS = [
    {
        "occurrence_id": "occ-apple",
        "content_id": "content-apple",
        "date": "2026-08-05",
        "title": "Apple Is Getting This Wrong",
        "summary": "A focused analysis of Apple's AI strategy.",
        "source": "OpenAI",
        "local_url": "#2026-08-05/ai-topic-radar/item/occ-apple",
        "external_url": "https://example.com/apple",
        "result_type": "item",
        "report_type": "daily",
    },
    {
        "occurrence_id": "occ-cn",
        "content_id": "content-cn",
        "date": "2026-08-05",
        "title": "人工智能基础设施趋势",
        "summary": "讨论算力与数据基础设施。",
        "source": "InfoQ 中国",
        "local_url": "#2026-08-05/ai-topic-radar/item/occ-cn",
        "external_url": "https://example.com/cn",
        "result_type": "item",
        "report_type": "daily",
    },
]


def test_exact_title_inside_natural_language_query_is_ranked_first(tmp_path):
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        assert store.rebuild(DOCUMENTS) == 2
        results = store.search("Apple Is Getting This Wrong 讲了什么？", k=5)
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "occ-apple"
    assert results[0]["metadata"]["citation_id"] == "occ-apple"
    assert results[0]["metadata"]["local_url"].endswith("/item/occ-apple")
    assert results[0]["match_type"] == "exact_title"


def test_exact_title_outranks_a_longer_title_that_only_contains_the_query(tmp_path):
    exact = DOCUMENTS[0]
    longer = {
        **DOCUMENTS[0],
        "occurrence_id": "occ-repost",
        "content_id": "content-repost",
        "title": "OpenAI 公开邮件回应苹果诉讼，称 Apple Is Getting This Wrong",
        "source": "转载媒体",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([longer, exact])
        results = store.search("Apple Is Getting This Wrong", k=5)
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "occ-apple"
    assert results[0]["match_type"] == "exact_title"
    assert results[1]["match_type"] == "title_contains_query"


def test_two_character_chinese_query_uses_bounded_substring_fallback(tmp_path):
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(DOCUMENTS)
        results = store.search("智能", k=5)
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in results] == ["occ-cn"]
    assert results[0]["match_type"] == "substring"


def test_daily_item_id_uses_a_deterministic_exact_path(tmp_path):
    document = {
        **DOCUMENTS[0],
        "occurrence_id": "ATR-20260805-A1B2C3",
        "local_url": "#2026-08-05/ai-topic-radar/item/ATR-20260805-A1B2C3",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([document])
        results = store.search("atr-20260805-a1b2c3", k=5)
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "ATR-20260805-A1B2C3"
    assert results[0]["match_type"] == "exact_id"


def test_daily_item_id_inside_natural_language_uses_exact_path(tmp_path):
    document = {
        **DOCUMENTS[0],
        "occurrence_id": "ATR-20260805-A1B2C3",
        "local_url": "#2026-08-05/ai-topic-radar/item/ATR-20260805-A1B2C3",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([document])
        results = store.search("请查找并说明条目 ATR-20260805-A1B2C3", k=5)
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "ATR-20260805-A1B2C3"
    assert results[0]["match_type"] == "exact_id"


def test_metadata_filter_applies_to_lexical_results(tmp_path):
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(DOCUMENTS)
        results = store.search(
            "Apple Is Getting This Wrong",
            k=5,
            where={"source": "InfoQ 中国"},
        )
    finally:
        store.close()

    assert results == []


def test_recent_returns_daily_items_in_date_and_score_order(tmp_path):
    documents = [
        {
            **DOCUMENTS[0],
            "date": "2026-08-04",
            "score": 99,
        },
        {
            **DOCUMENTS[1],
            "score": 80,
        },
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        results = store.recent(limit=5, where={"content_type": "topic_candidate"})
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in results] == ["occ-cn", "occ-apple"]


def test_recent_publication_filter_excludes_old_content_collected_in_a_new_report(tmp_path):
    documents = [
        {
            **DOCUMENTS[0],
            "report_date": "2026-08-05",
            "publication_date": "2022-02-11",
            "effective_date": "2022-02-11",
            "effective_date_basis": "publication_date",
        },
        {
            **DOCUMENTS[1],
            "date": "2026-08-04",
            "report_date": "2026-08-04",
            "publication_date": "2026-08-03",
            "effective_date": "2026-08-03",
            "effective_date_basis": "publication_date",
        },
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        results = store.recent(
            limit=5,
            where={"effective_date": {"$in": ["2026-08-03", "2026-08-04", "2026-08-05"]}},
        )
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in results] == ["occ-cn"]


def test_recent_sorts_by_the_filtered_temporal_role(tmp_path):
    documents = [
        {**DOCUMENTS[0], "source_updated_at": "2026-08-04", "effective_date": "2026-08-05"},
        {**DOCUMENTS[1], "source_updated_at": "2026-08-05", "effective_date": "2026-08-04"},
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        results = store.recent(
            limit=5,
            where={"source_updated_at": {"$in": ["2026-08-04", "2026-08-05"]}},
        )
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in results] == ["occ-cn", "occ-apple"]


def test_temporal_role_filters_keep_three_mutually_exclusive_documents_separate(tmp_path):
    documents = [
        {
            **DOCUMENTS[0],
            "occurrence_id": "published-only",
            "publication_date": "2026-08-12",
            "source_updated_at": "",
            "report_date": "2026-07-01",
        },
        {
            **DOCUMENTS[1],
            "occurrence_id": "updated-only",
            "publication_date": "",
            "source_updated_at": "2026-08-12",
            "report_date": "2026-07-01",
        },
        {
            **DOCUMENTS[0],
            "occurrence_id": "reported-only",
            "publication_date": "",
            "source_updated_at": "",
            "report_date": "2026-08-12",
        },
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        published = store.recent(5, {"publication_date": {"$in": ["2026-08-12"]}})
        updated = store.recent(5, {"source_updated_at": {"$in": ["2026-08-12"]}})
        reported = store.recent(5, {"report_date": {"$in": ["2026-08-12"]}})
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in published] == ["published-only"]
    assert [item["metadata"]["occurrence_id"] for item in updated] == ["updated-only"]
    assert [item["metadata"]["occurrence_id"] for item in reported] == ["reported-only"]


def test_lexical_metadata_preserves_structured_entity_ids(tmp_path):
    document = {**DOCUMENTS[0], "entity_ids": ["apple", "openai"]}
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([document])
        result = store.search("Apple Is Getting This Wrong", k=1)[0]
    finally:
        store.close()

    assert result["metadata"]["entity_ids"] == ["apple", "openai"]
