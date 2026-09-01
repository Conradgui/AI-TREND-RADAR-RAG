import unittest

from rag.event_extraction import extract_event_batch, extract_event_fields
from rag.event_contract import canonical_content_kind, canonical_event_type


class EventExtractionTests(unittest.TestCase):
    def test_canonical_contract_values_are_idempotent(self):
        self.assertEqual(canonical_content_kind("news"), "news")
        self.assertEqual(canonical_content_kind("news_event"), "news")
        self.assertEqual(canonical_event_type("partnership"), "partnership")

    def test_official_company_announcement_owns_the_event(self):
        fields = extract_event_fields({
            "title": "OpenAI launches an Economic Research Exchange",
            "summary": "OpenAI launches a new research program.",
            "source": "OpenAI",
            "publication_date": "2026-08-04",
            "publication_date_source": "official_feed",
        })

        self.assertEqual(fields["content_kind"], "news")
        self.assertEqual(fields["source_role"], "first_party")
        self.assertEqual(fields["subject_entity_ids"], ["openai"])
        self.assertEqual(fields["mentioned_entity_ids"], [])
        self.assertEqual(fields["temporal_confidence"], "high")

    def test_third_party_project_keeps_compatible_companies_as_mentions(self):
        fields = extract_event_fields({
            "title": "thedotmack/claude-mem",
            "summary": "Works with Claude Code, Codex and Gemini.",
            "source": "GitHub Search:rag",
            "publication_date": None,
            "publication_date_source": "unknown",
        })

        self.assertEqual(fields["content_kind"], "product_listing")
        self.assertEqual(fields["source_role"], "third_party")
        self.assertEqual(fields["subject_entity_ids"], ["claude-mem"])
        self.assertIn("anthropic", fields["mentioned_entity_ids"])
        self.assertIn("google", fields["mentioned_entity_ids"])
        self.assertEqual(fields["temporal_confidence"], "unknown")

    def test_how_to_article_is_not_promoted_to_company_news(self):
        fields = extract_event_fields({
            "title": "How to export ChatGPT to PDF",
            "summary": "A step-by-step tutorial for ChatGPT users.",
            "source": "Dev.to",
            "publication_date": None,
            "publication_date_source": "unknown",
        })

        self.assertEqual(fields["content_kind"], "tutorial")
        self.assertEqual(fields["event_type"], "documentation_or_tutorial")
        self.assertEqual(fields["subject_entity_ids"], [])
        self.assertEqual(fields["mentioned_entity_ids"], ["openai"])

    def test_material_business_report_is_a_news_event_not_an_unknown_mention(self):
        fields = extract_event_fields({
            "title": "Anthropic revenue jumps ahead of a potential IPO",
            "summary": "Quarterly revenue and valuation expectations reshape its competitive position.",
            "source": "Hacker News",
            "publication_date": "2026-08-16",
            "publication_date_source": "legacy_adapter_contract",
        })

        self.assertEqual(fields["content_kind"], "news")
        self.assertEqual(fields["event_type"], "business_update")
        self.assertEqual(fields["subject_entity_ids"], ["anthropic"])

    def test_news_headline_verbs_are_classified_without_requiring_the_word_announce(self):
        rollout = extract_event_fields({
            "title": "OpenAI rolling out ads for Europe later this month",
            "summary": "HN discussion by notenlish",
            "source": "Hacker News",
            "publication_date": "2026-08-15",
            "publication_date_source": "structured",
        })
        public_company = extract_event_fields({
            "title": "OpenAI will be a public company in 2027 or sooner",
            "summary": "HN discussion by thm",
            "source": "Hacker News",
            "publication_date": "2026-08-19",
            "publication_date_source": "structured",
        })

        self.assertEqual((rollout["content_kind"], rollout["event_type"]), ("news", "product_launch"))
        self.assertEqual((public_company["content_kind"], public_company["event_type"]), ("news", "business_update"))

    def test_official_red_team_analysis_is_research_not_generic_developer_content(self):
        fields = extract_event_fields({
            "title": "Patterns and problems in multiagent systems",
            "summary": "Frontier Red Team analysis of behavioral tendencies and systemic failures in emerging multiagent systems.",
            "source": "Anthropic (Claude)",
            "publication_date": None,
            "publication_date_source": "unknown",
        })

        self.assertEqual((fields["content_kind"], fields["event_type"]), ("research", "research_release"))

    def test_incidental_developer_words_do_not_hide_official_news_or_research(self):
        watermark = extract_event_fields({
            "title": "How Claude's text watermarking works",
            "summary": "Announcements explain how major model developers will comply with the EU AI Act.",
            "source": "Anthropic (Claude)",
        })
        red_team = extract_event_fields({
            "title": "Patterns and problems in multiagent systems",
            "summary": "Red Team analysis describes agent interaction, behavioral tendencies, and systemic failures.",
            "source": "Anthropic (Claude)",
        })

        self.assertEqual((watermark["content_kind"], watermark["event_type"]), ("news", "product_launch"))
        self.assertEqual((red_team["content_kind"], red_team["event_type"]), ("research", "research_release"))

    def test_mixed_chinese_latin_entities_keep_subject_roles(self):
        regulatory = extract_event_fields({
            "title": "美国众议院委员会要求参观xAI数据中心以调查污染情况",
            "summary": "委员会致信SpaceX首席执行官并调查xAI数据中心。",
            "source": "36kr",
        })
        release = extract_event_fields({
            "title": "马斯克连夜开源Grok Build",
            "summary": "Grok Build 代码正式开源。",
            "source": "InfoQ 中国",
        })

        self.assertEqual(regulatory["content_kind"], "news")
        self.assertEqual(regulatory["event_type"], "regulatory_action")
        self.assertIn("xai", regulatory["subject_entity_ids"])
        self.assertEqual(release["event_type"], "product_launch")
        self.assertIn("grok", release["subject_entity_ids"])

    def test_high_value_event_contract_handles_bilingual_daily_report_phrasing(self):
        cases = [
            (
                {"title": "哈萨比斯卸任 DeepMind CEO，Jeff Dean 离职创业", "summary": "谷歌重排 AI 权力中心。", "source": "InfoQ 中国"},
                ("news", "leadership"),
            ),
            (
                {"title": "苹果指控 OpenAI 挖人偷文件，OpenAI 公开反击", "summary": "双方争议进入法律程序。", "source": "InfoQ 中国"},
                ("news", "litigation"),
            ),
            (
                {"title": "平台工程成熟度成为 AI 应用关键因素", "summary": "Perforce Software 发布 2026 年平台工程报告。", "source": "InfoQ 中国"},
                ("research", "research_release"),
            ),
            (
                {"title": "Improving Fable 5 Safeguards", "summary": "Product announcement: updates reduce biology fallbacks by 85%.", "source": "Anthropic (Claude)"},
                ("news", "product_launch"),
            ),
        ]

        for document, expected in cases:
            with self.subTest(title=document["title"]):
                fields = extract_event_fields(document)
                self.assertEqual((fields["content_kind"], fields["event_type"]), expected)

    def test_product_listing_gets_stable_subject_without_promoting_compatibility_mentions(self):
        fields = extract_event_fields({
            "title": "Termexo",
            "summary": "A local Windows workbench for Claude Code and Codex",
            "source": "Product Hunt",
            "publication_date": "2026-08-02",
            "publication_date_source": "legacy_adapter_contract",
        })

        self.assertEqual(fields["content_kind"], "product_listing")
        self.assertEqual(fields["subject_entity_ids"], ["termexo"])
        self.assertIn("anthropic", fields["mentioned_entity_ids"])
        self.assertIn("codex", fields["mentioned_entity_ids"])

    def test_batch_groups_same_multi_party_event_but_not_other_litigation(self):
        documents = [
            {"daily_item_id":"A", "date":"2026-08-05", "title":"Apple sues OpenAI", "summary":"Apple files a lawsuit against OpenAI.", "source":"News", "publication_date":"2026-08-04", "publication_date_source":"structured"},
            {"daily_item_id":"B", "date":"2026-08-05", "title":"OpenAI responds to Apple lawsuit", "summary":"OpenAI disputes Apple's claims.", "source":"OpenAI", "publication_date":"2026-08-04", "publication_date_source":"official_feed"},
            {"daily_item_id":"C", "date":"2026-08-05", "title":"OpenAI settles employment probe", "summary":"A separate employment investigation ends.", "source":"News", "publication_date":"2026-08-04", "publication_date_source":"structured"},
        ]

        extracted = {row["daily_item_id"]: row for row in extract_event_batch(documents)}

        self.assertEqual(extracted["A"]["event_group_id"], extracted["B"]["event_group_id"])
        self.assertNotEqual(extracted["A"]["event_group_id"], extracted["C"]["event_group_id"])

    def test_batch_clusters_same_company_business_updates_within_one_week(self):
        documents = [
            {"daily_item_id":"A", "date":"2026-08-17", "title":"Anthropic revenue jumps beyond Apple before IPO", "summary":"Revenue exceeds expectations.", "source":"Hacker News"},
            {"daily_item_id":"B", "date":"2026-08-19", "title":"Anthropic annualized revenue tops forecast", "summary":"The IPO outlook changes.", "source":"Hacker News"},
        ]

        extracted = {row["daily_item_id"]: row for row in extract_event_batch(documents)}

        self.assertEqual(extracted["A"]["event_group_id"], extracted["B"]["event_group_id"])
