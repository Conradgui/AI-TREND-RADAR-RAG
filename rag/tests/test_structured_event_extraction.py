import unittest

from rag.structured_event_extraction import extract_semantic_event


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def extract(self, document):
        self.requests.append(document)
        return self.payload


class StructuredEventExtractionTests(unittest.TestCase):
    def test_returns_validated_semantic_fields_without_source_owned_facts(self):
        client = FakeClient({
            "content_kind": "news",
            "event_type": "partnership",
            "subject_entity_ids": ["openai", "apa"],
            "mentioned_entity_ids": [],
        })
        document = {
            "daily_item_id": "ATR-1", "title": "OpenAI and APA partner",
            "summary": "They announce a partnership.", "source": "OpenAI",
            "publication_date": "2026-08-01", "external_url": "https://example.com",
        }

        result = extract_semantic_event(document, client)

        self.assertEqual(result["extraction_status"], "extracted")
        self.assertEqual(result["content_kind"], "news")
        self.assertNotIn("publication_date", result)
        self.assertNotIn("daily_item_id", result)
        self.assertEqual(set(client.requests[0]), {"title", "summary", "source", "external_url", "tags"})

    def test_rejects_unknown_enum_and_overlapping_entity_roles(self):
        client = FakeClient({
            "content_kind": "press_release",
            "event_type": "partnership",
            "subject_entity_ids": ["openai"],
            "mentioned_entity_ids": ["openai"],
        })

        result = extract_semantic_event({"title":"x", "summary":"y", "source":"z"}, client)

        self.assertEqual(result["extraction_status"], "needs_review")
        self.assertIn("invalid_content_kind", result["diagnostics"])
        self.assertIn("overlapping_entity_roles", result["diagnostics"])

    def test_normalizes_entity_ids_and_deduplicates(self):
        client = FakeClient({
            "content_kind": "research",
            "event_type": "research_release",
            "subject_entity_ids": ["Google DeepMind", "google-deepmind"],
            "mentioned_entity_ids": ["Nature"],
        })

        result = extract_semantic_event({"title":"x", "summary":"y", "source":"z"}, client)

        self.assertEqual(result["subject_entity_ids"], ["google-deepmind"])
        self.assertEqual(result["mentioned_entity_ids"], ["nature"])
