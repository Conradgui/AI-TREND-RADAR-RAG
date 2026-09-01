import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from rag.eval_event_shadow import evaluate


class EventShadowEvaluationTests(unittest.TestCase):
    def test_event_contract_preserves_quality_after_legacy_runtime_backfill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            dataset = root / "dataset.json"
            source.write_text(json.dumps({"documents": [
                {"daily_item_id":"ATR-20260805-MAIN01","occurrence_id":"ATR-20260805-MAIN01","result_type":"item","report_type":"daily","date":"2026-08-05","title":"Company settles investigation","summary":"A material settlement.","source":"OpenAI","score":90},
                {"daily_item_id":"ATR-20260805-NOISE1","occurrence_id":"ATR-20260805-NOISE1","result_type":"item","report_type":"daily","date":"2026-08-05","title":"Tool supports OpenAI API","summary":"Compatibility listing.","source":"GitHub","score":99}
            ]}), encoding="utf-8")
            dataset.write_text(json.dumps({
                "dataset_id":"tiny", "report_date":"2026-08-05", "scope_limit":"test",
                "annotations":[
                    {"daily_item_id":"ATR-20260805-MAIN01","content_kind":"news_event","event_type":"litigation","subject_entity_ids":["openai"],"mentioned_entity_ids":[],"publication_date":"2026-08-04","temporal_confidence":"high"},
                    {"daily_item_id":"ATR-20260805-NOISE1","content_kind":"project_listing","event_type":"compatibility","subject_entity_ids":["tool"],"mentioned_entity_ids":["openai"],"publication_date":None,"temporal_confidence":"low"}
                ],
                "evaluation_queries":[{"query":"OpenAI 最近有哪些重要动态？","entity":"openai","expected_main":["ATR-20260805-MAIN01"],"expected_background":[],"expected_exclude":["ATR-20260805-NOISE1"]}]
            }), encoding="utf-8")

            result = asyncio.run(evaluate(source, dataset))

        versions = {row["version"]: row for row in result["versions"]}
        # The production gateway now backfills the event contract for an old
        # active generation. The legacy view is therefore a compatibility
        # view, not an intentionally degraded historical baseline.
        self.assertLessEqual(
            versions["v0_legacy_entity"]["rows"][0]["metrics"]["precision"],
            versions["v2_event_contract"]["rows"][0]["metrics"]["precision"],
        )
        self.assertEqual(
            versions["v2_event_contract"]["rows"][0]["observed_main"],
            ["ATR-20260805-MAIN01"],
        )
        self.assertEqual(
            versions["v2_event_contract"]["rows"][0]["metrics"]["duplicate_event_slots"],
            0,
        )
