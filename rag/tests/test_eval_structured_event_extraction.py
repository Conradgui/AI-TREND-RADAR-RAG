from rag.eval_structured_event_extraction_live import score_predictions


def test_scores_semantic_fields_and_exact_records():
    annotations = [{
        "daily_item_id":"A", "content_kind":"news", "event_type":"partnership",
        "subject_entity_ids":["openai"], "mentioned_entity_ids":[],
    }]
    predictions = [{
        **annotations[0], "extraction_status":"extracted", "diagnostics":[],
    }]

    result = score_predictions(predictions, annotations)

    assert result["valid_contract_rate"] == 1.0
    assert result["exact_record_rate"] == 1.0
    assert result["fields"]["subject_entity_ids"]["accuracy"] == 1.0
