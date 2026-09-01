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


def test_short_title_inside_entity_name_does_not_hijack_navigation(tmp_path):
    short_noise = {
        **DOCUMENTS[0],
        "occurrence_id": "occ-min",
        "content_id": "content-min",
        "title": "min.",
        "summary": "A short unrelated title.",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([short_noise])
        results = store.search("Google 和 Gemini 最近有哪些重要动态？", k=5)
    finally:
        store.close()

    assert not results or results[0]["match_type"] != "exact_title"


def test_specific_title_without_harmless_prefix_can_navigate(tmp_path):
    document = {
        **DOCUMENTS[0],
        "occurrence_id": "occ-exchange",
        "content_id": "content-exchange",
        "title": "Introducing The OpenAI Economic Research Exchange",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([document])
        results = store.search("OpenAI Economic Research Exchange 是什么？", k=5)
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "occ-exchange"
    assert results[0]["match_type"] == "title_in_query"


def test_repeated_repository_title_alias_can_navigate_to_requested_date(tmp_path):
    documents = [
        {
            **DOCUMENTS[0],
            "occurrence_id": "ATR-20260820-AAAAAA",
            "content_id": "repo-open-webui",
            "date": "2026-08-20",
            "title": "open-webui/open-webui",
            "summary": "User-friendly AI Interface supporting Ollama and OpenAI API.",
        },
        {
            **DOCUMENTS[0],
            "occurrence_id": "ATR-20260821-BBBBBB",
            "content_id": "repo-open-webui",
            "date": "2026-08-21",
            "title": "open-webui/open-webui",
            "summary": "User-friendly AI Interface supporting Ollama and OpenAI API.",
        },
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        results = store.search(
            "打开 open-webui 这个支持 Ollama 和 OpenAI API 的开源界面条目（8 月 21 日）。",
            k=5,
        )
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "ATR-20260821-BBBBBB"
    assert results[0]["match_type"] == "title_in_query"


def test_repository_slug_in_comparison_query_is_a_title_alias(tmp_path):
    repositories = [
        {
            **DOCUMENTS[0],
            "occurrence_id": "occ-graphify",
            "content_id": "repo-graphify",
            "title": "Graphify-Labs/graphify",
            "summary": "Queryable codebase knowledge graph.",
        },
        {
            **DOCUMENTS[0],
            "occurrence_id": "occ-claude-mem",
            "content_id": "repo-claude-mem",
            "title": "thedotmack/claude-mem",
            "summary": "Persistent context across agent sessions.",
        },
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(repositories)
        results = store.search(
            "Graphify 和 claude-mem 在保留和检索上下文上分别做什么？",
            k=2,
        )
    finally:
        store.close()

    assert {item["metadata"]["occurrence_id"] for item in results} == {
        "occ-graphify",
        "occ-claude-mem",
    }
    assert all(item["match_type"] == "title_in_query" for item in results)


def test_named_entity_with_bilingual_event_alias_returns_event_reports(tmp_path):
    documents = [
        {
            **DOCUMENTS[0],
            "occurrence_id": "ATR-20260812-0E70FB",
            "content_id": "openai-ipo-share-sale",
            "date": "2026-08-12",
            "title": "OpenAI wraps $7B share sale ahead of potential IPO",
        },
        {
            **DOCUMENTS[0],
            "occurrence_id": "ATR-20260820-6EFF79",
            "content_id": "openai-ipo-2027",
            "date": "2026-08-20",
            "title": "OpenAI will be a public company in 2027 or sooner",
            "external_url": "https://example.com/openai-ipo-timing-2027",
        },
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        results = store.search("OpenAI 上市 IPO", k=5)
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in results] == [
        "ATR-20260820-6EFF79",
        "ATR-20260812-0E70FB",
    ]
    assert all(item["match_type"] == "entity_event" for item in results)


def test_functional_description_can_find_one_structured_project(tmp_path):
    graphify = {
        **DOCUMENTS[0],
        "occurrence_id": "ATR-20260821-CCCCCC",
        "content_id": "repo-graphify",
        "date": "2026-08-21",
        "title": "Graphify-Labs/graphify",
        "summary": (
            "Turn any codebase, docs, SQL schemas, and configs into a queryable "
            "knowledge graph with no vector store."
        ),
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([graphify, *DOCUMENTS])
        results = store.search(
            "找那个能把代码库文档、SQL schema 和配置转成可查询知识图谱、而且强调不用向量库的项目。",
            k=5,
        )
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "ATR-20260821-CCCCCC"
    assert results[0]["match_type"] == "descriptor"


def test_distinctive_safety_description_can_find_one_news_record(tmp_path):
    record = {
        **DOCUMENTS[0],
        "occurrence_id": "ATR-20260811-EF1380",
        "content_id": "claude-auto-mode",
        "date": "2026-08-11",
        "title": "Claude Code 将自动模式设为默认，称人类审批只抓到 13.6% 危险命令",
        "summary": (
            "Anthropic 宣布 Claude Code 将默认启用自动模式；实验中人工审批只抓到 "
            "13.6% 的危险命令，而自动模式抓到了 89%。"
        ),
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([record, *DOCUMENTS])
        results = store.search(
            "打开 8 月 11 日那条说 Claude Code 默认启用自动模式、并提到人工审批只抓到 13.6% 危险命令的记录。",
            k=5,
        )
    finally:
        store.close()

    assert results[0]["metadata"]["occurrence_id"] == "ATR-20260811-EF1380"
    assert results[0]["match_type"] == "descriptor"


def test_descriptive_entity_question_does_not_force_title_navigation(tmp_path):
    document = {
        **DOCUMENTS[0],
        "occurrence_id": "occ-weather",
        "content_id": "content-weather",
        "title": "AI model achieves breakthrough in forecasting cyclones — Google DeepMind",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([document])
        results = store.search("Google DeepMind 最近在气旋预测上有什么突破？", k=5)
    finally:
        store.close()

    assert not results or results[0]["match_type"] != "title_in_query"


def test_entity_name_alone_does_not_make_a_generic_publisher_page_exact(tmp_path):
    document = {
        **DOCUMENTS[0],
        "occurrence_id": "occ-alphago",
        "content_id": "content-alphago",
        "title": "AlphaGo — Google DeepMind",
    }
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild([document])
        results = store.search("Google DeepMind 最近在气旋预测上有什么突破？", k=5)
    finally:
        store.close()

    assert not results or results[0]["match_type"] != "title_in_query"


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


def test_recent_supports_inclusive_date_ranges_in_composite_filters(tmp_path):
    documents = [
        {**DOCUMENTS[0], "date": "2026-08-14", "occurrence_id": "before"},
        {**DOCUMENTS[0], "date": "2026-08-18", "occurrence_id": "inside"},
        {**DOCUMENTS[0], "date": "2026-08-22", "occurrence_id": "after"},
    ]
    store = LexicalStore(tmp_path / "lexical.sqlite3")
    try:
        store.rebuild(documents)
        results = store.recent(
            limit=5,
            where={"$and": [
                {"content_type": "topic_candidate"},
                {"$and": [
                    {"effective_date": {"$gte": "2026-08-15"}},
                    {"effective_date": {"$lte": "2026-08-21"}},
                ]},
            ]},
        )
    finally:
        store.close()

    assert [item["metadata"]["occurrence_id"] for item in results] == ["inside"]


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
