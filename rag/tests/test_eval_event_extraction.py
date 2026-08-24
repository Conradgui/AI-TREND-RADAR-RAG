import unittest

from rag.eval_event_extraction import evaluate_predictions


class EventExtractionEvaluationTests(unittest.TestCase):
    def test_reports_field_errors_independently(self):
        documents = [{
            "daily_item_id":"A", "title":"OpenAI launches research program",
            "summary":"OpenAI launches it.", "source":"OpenAI",
            "publication_date":"2026-08-04", "publication_date_source":"official_feed",
        }]
        annotations = [{
            "daily_item_id":"A", "content_kind":"first_party_news", "event_type":"program_launch",
            "subject_entity_ids":["openai"], "mentioned_entity_ids":[],
            "publication_date":"2026-08-04", "temporal_confidence":"high",
        }]

        result = evaluate_predictions(documents, annotations)

        self.assertEqual(result["fields"]["content_kind"]["accuracy"], 1.0)
        self.assertEqual(result["fields"]["source_role"]["accuracy"], 1.0)
        self.assertEqual(result["fields"]["subject_entity_ids"]["accuracy"], 1.0)
        self.assertEqual(result["exact_record_rate"], 1.0)

    def test_source_locked_date_uses_document_not_reviewer_inference(self):
        documents = [{
            "daily_item_id":"A", "title":"OpenAI launches research program",
            "summary":"The article text says Aug 4.", "source":"OpenAI",
            "publication_date":None, "publication_date_source":"unknown",
        }]
        annotations = [{
            "daily_item_id":"A", "content_kind":"first_party_news", "event_type":"program_launch",
            "subject_entity_ids":["openai"], "mentioned_entity_ids":[],
            "publication_date":"2026-08-04", "temporal_confidence":"high",
        }]

        result = evaluate_predictions(documents, annotations)

        self.assertEqual(result["fields"]["publication_date"]["accuracy"], 1.0)
        self.assertEqual(result["fields"]["temporal_confidence"]["accuracy"], 1.0)
        self.assertEqual(result["contract_version"], "event-contract-v2")

    def test_unannotated_source_role_is_not_counted_as_an_error(self):
        documents = [{
            "daily_item_id":"A", "title":"A neutral article",
            "summary":"No event keywords.", "source":"News",
            "publication_date":None, "publication_date_source":"unknown",
        }]
        annotations = [{
            "daily_item_id":"A", "content_kind":"unknown", "event_type":"other",
            "subject_entity_ids":[], "mentioned_entity_ids":[],
            "publication_date":None, "temporal_confidence":"unknown",
        }]

        result = evaluate_predictions(documents, annotations)

        self.assertEqual(result["fields"]["source_role"]["total"], 0)
        self.assertIsNone(result["fields"]["source_role"]["accuracy"])

    def test_reports_non_news_false_admission_rate(self):
        documents = [{
            "daily_item_id":"A", "title":"Announcing alpha",
            "summary":"A launch announcement.", "source":"News",
            "publication_date":None, "publication_date_source":"unknown",
        }]
        annotations = [{
            "daily_item_id":"A", "content_kind":"tutorial", "event_type":"how_to",
            "subject_entity_ids":[], "mentioned_entity_ids":[],
            "publication_date":None, "temporal_confidence":"unknown",
        }]

        result = evaluate_predictions(documents, annotations)

        self.assertEqual(result["quality_metrics"]["non_news_false_admission_rate"], 1.0)
        self.assertEqual(result["source_fact_checks"], ["publication_date", "temporal_confidence"])
