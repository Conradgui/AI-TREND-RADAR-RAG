from rag.prompt_registry import compile_task_prompt, extract_claim_verification_result


def test_task_prompts_enforce_their_core_product_contracts():
    trend = compile_task_prompt("trend_discovery", 6)
    claim = compile_task_prompt("claim_verification", 0)
    fallback = compile_task_prompt("unknown", 2)

    assert "趋势簇" in trend and "单条新闻不得直接称为趋势" in trend
    assert "supported、contradicted 或 insufficient" in claim
    assert "必须返回证据不足" in claim
    assert "claim_verification" in claim
    assert "claim-result" not in claim
    assert "直接否定" in compile_task_prompt("claim_verification", 3)
    assert "亏损" in compile_task_prompt("claim_verification", 3)
    assert "每条结论绑定具体证据编号" in fallback


def test_prompt_registry_records_the_validated_route_contract_id():
    prompt = compile_task_prompt(
        "trend_discovery",
        3,
        prompt_contract_id="atr.prompt/trend_discovery/1.0",
    )

    assert "atr.prompt/trend_discovery/1.0" in prompt


def test_claim_result_is_machine_validated_and_removed_from_display_answer():
    answer = (
        "现有证据不足以证明该主张。[E1]\n"
        '<!--claim-result:{"verdict":"insufficient","rationale":"缺少财务与用户数据",'
        '"evidence_ids":["E1"],"missing_criteria":["财务结果","用户采用"],'
        '"direct_refutation":false}-->'
    )

    display, result = extract_claim_verification_result(answer, {"E1"})

    assert "claim-result" not in display
    assert result["valid"] is True
    assert result["verdict"] == "insufficient"
    assert result["evidence_ids"] == ["E1"]


def test_claim_result_rejects_contradiction_without_direct_refutation():
    answer = (
        "公司出现亏损，因此没有商业成功。[E1]\n"
        '<!--claim-result:{"verdict":"contradicted","rationale":"出现亏损",'
        '"evidence_ids":["E1"],"missing_criteria":[],"direct_refutation":false}-->'
    )

    _display, result = extract_claim_verification_result(answer, {"E1"})

    assert result["valid"] is False
    assert "direct_refutation_required" in result["errors"]


def test_claim_result_rejects_unknown_evidence_ids():
    answer = (
        "该主张成立。[E9]\n"
        '<!--claim-result:{"verdict":"supported","rationale":"证据支持",'
        '"evidence_ids":["E9"],"missing_criteria":[],"direct_refutation":false}-->'
    )

    _display, result = extract_claim_verification_result(answer, {"E1"})

    assert result["valid"] is False
    assert result["unknown_evidence_ids"] == ["E9"]
