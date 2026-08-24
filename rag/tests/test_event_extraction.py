import unittest

from rag.event_extraction import extract_event_batch, extract_event_fields


class EventExtractionTests(unittest.TestCase):
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
