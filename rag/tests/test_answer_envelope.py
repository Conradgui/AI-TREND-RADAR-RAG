from rag.answer_envelope import parse_answer_envelope


def test_answer_envelope_accepts_matching_known_evidence_ids():
    result = parse_answer_envelope(
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"结论一。[E2]\\n\\n结论二。[E1]",'
        '"evidence_ids":["E2","E1"]}',
        {"E1", "E2"},
    )

    assert result["valid"] is True
    assert result["envelope"].evidence_ids == ("E2", "E1")


def test_answer_envelope_normalizes_provider_double_escaped_newlines():
    result = parse_answer_envelope(
        r'{"schema_version":"answer-envelope/1.0",'
        r'"body_markdown":"第一段。\\n\\n第二段。[E1]",'
        r'"evidence_ids":["E1"]}',
        {"E1"},
    )

    assert result["valid"] is True
    assert result["envelope"].body_markdown == "第一段。\n\n第二段。[E1]"


def test_answer_envelope_rejects_free_text_without_json_repair():
    result = parse_answer_envelope("这是自由文本。[E1]", {"E1"})

    assert result == {"valid": False, "errors": ["invalid_json"], "envelope": None}


def test_answer_envelope_rejects_json_code_fence():
    result = parse_answer_envelope(
        '```json\n{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"结论。[E1]","evidence_ids":["E1"]}\n```',
        {"E1"},
    )

    assert result == {"valid": False, "errors": ["invalid_json"], "envelope": None}


def test_answer_envelope_rejects_duplicate_evidence_ids():
    result = parse_answer_envelope(
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"结论。[E1]","evidence_ids":["E1","E1"]}',
        {"E1"},
    )

    assert result["valid"] is False
    assert result["errors"] == ["duplicate_evidence_id", "evidence_marker_mismatch"]


def test_answer_envelope_rejects_marker_mismatch_and_unknown_ids():
    result = parse_answer_envelope(
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"结论。[E1]",'
        '"evidence_ids":["E9"]}',
        {"E1"},
    )

    assert result["valid"] is False
    assert result["errors"] == ["evidence_marker_mismatch", "unknown_evidence_id"]


def test_claim_verification_envelope_requires_structured_machine_result():
    result = parse_answer_envelope(
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"现有证据不足。[E1]",'
        '"evidence_ids":["E1"]}',
        {"E1"},
        require_claim_verification=True,
    )

    assert result["valid"] is False
    assert result["errors"] == ["claim_verification_missing"]


def test_claim_verification_envelope_accepts_valid_structured_result():
    result = parse_answer_envelope(
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"现有证据不足。[E1]",'
        '"evidence_ids":["E1"],'
        '"claim_verification":{'
        '"verdict":"insufficient","rationale":"缺少发布证据",'
        '"evidence_ids":["E1"],"missing_criteria":["官方发布记录"],'
        '"direct_refutation":false}}',
        {"E1"},
        require_claim_verification=True,
    )

    assert result["valid"] is True
    assert result["envelope"].claim_verification == {
        "valid": True,
        "schema_valid": True,
        "validation_scope": "format_and_evidence_reference_only",
        "verdict": "insufficient",
        "rationale": "缺少发布证据",
        "evidence_ids": ["E1"],
        "unknown_evidence_ids": [],
        "missing_criteria": ["官方发布记录"],
        "direct_refutation": False,
        "errors": [],
    }


def test_claim_verification_contradiction_requires_bound_evidence():
    result = parse_answer_envelope(
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"现有证据直接否定该主张。[E1]",'
        '"evidence_ids":["E1"],'
        '"claim_verification":{'
        '"verdict":"contradicted","rationale":"存在直接反证",'
        '"evidence_ids":[],"missing_criteria":[],"direct_refutation":true}}',
        {"E1"},
        require_claim_verification=True,
    )

    assert result["valid"] is False
    assert result["errors"] == ["contradicting_evidence_required"]
