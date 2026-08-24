import unittest

from rag.event_shadow import apply_event_annotations


class EventShadowTests(unittest.TestCase):
    def test_reviewed_event_fields_preserve_public_item_identity(self):
        source = [{"daily_item_id": "ATR-20260805-ABC123", "title": "Example"}]
        annotations = [{
            "daily_item_id": "ATR-20260805-ABC123",
            "content_kind": "news_event",
            "event_type": "partnership",
            "subject_entity_ids": ["openai"],
            "mentioned_entity_ids": ["apple"],
            "publication_date": "2026-08-04",
            "temporal_confidence": "high",
        }]

        result = apply_event_annotations(source, annotations)

        self.assertEqual(result[0]["daily_item_id"], "ATR-20260805-ABC123")
        self.assertEqual(result[0]["subject_entity_ids"], ["openai"])
        self.assertEqual(result[0]["mentioned_entity_ids"], ["apple"])

    def test_unknown_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown daily_item_id"):
            apply_event_annotations([], [{
                "daily_item_id": "ATR-20260805-MISSING",
                "content_kind": "news_event", "event_type": "other",
                "subject_entity_ids": [], "mentioned_entity_ids": [],
                "publication_date": None, "temporal_confidence": "low",
            }])
