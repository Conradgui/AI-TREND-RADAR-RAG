"""Task-owned prompt contracts for grounded answers."""

from __future__ import annotations

import json
import re


_CLAIM_RESULT_RE = re.compile(r"\s*<!--claim-result:(\{.*?\})-->\s*", re.DOTALL)
_CLAIM_VERDICTS = {"supported", "contradicted", "insufficient"}


_TASK_PROMPTS = {
    "item_navigation": "任务：定位具体条目。只返回匹配条目的标题、日期、来源和本地跳转链接；不要扩写成长篇分析。",
    "trend_discovery": "任务：发现近期趋势或重要新闻。主榜只使用近期新闻证据；news_tier=background 的旧但重要证据只能放入‘历史背景’，不得混入近期主榜。趋势问题需先把不同事件按共同主题聚成趋势簇，再说明时间方向、来源多样性和代表证据；单条新闻不得直接称为趋势。",
    "timeline": "任务：梳理时间线。按日期列出已观测变化，区分正文更新与热度变化；缺失日期不得补写成事实。",
    "relation_exploration": "任务：解释关系。明确标注关系类型和证据；共同出现不等于因果，推断关系必须写明不确定性。",
    "claim_verification": "任务：核验主张。结论只能是 supported、contradicted 或 insufficient，并逐项绑定证据。contradicted 必须有直接否定该主张核心判据的证据；亏损、争议或单一负面信号不能自动否定宽泛的商业成功，应返回 insufficient 并解释缺少哪些判据。回答末尾必须追加且只追加一个隐藏机器结果：<!--claim-result:{\"verdict\":\"supported|contradicted|insufficient\",\"rationale\":\"简短理由\",\"evidence_ids\":[\"E1\"],\"missing_criteria\":[],\"direct_refutation\":false}-->。",
    "evidence_research": "任务：证据研究。先给核心结论，再让每条结论绑定具体证据编号；不得使用证据账本之外的信息补全。",
}


def compile_task_prompt(
    task_family: str,
    evidence_count: int,
    *,
    prompt_contract_id: str | None = None,
) -> str:
    """Compile one stable task contract without topic-specific prompt forks."""
    family = task_family if task_family in _TASK_PROMPTS else "evidence_research"
    evidence_rule = (
        f"当前可用证据 {max(0, int(evidence_count))} 条。"
        if evidence_count
        else "当前没有可用证据；必须返回证据不足，不得继续推测。"
    )
    contract_rule = (
        f"任务契约 ID：{prompt_contract_id}\n" if prompt_contract_id else ""
    )
    return f"## 当前任务契约\n{contract_rule}{_TASK_PROMPTS[family]}\n{evidence_rule}"


def extract_claim_verification_result(
    answer: str,
    allowed_evidence_ids: set[str],
) -> tuple[str, dict]:
    """Remove and validate the hidden claim-verification result."""
    matches = list(_CLAIM_RESULT_RE.finditer(str(answer or "")))
    display_answer = _CLAIM_RESULT_RE.sub("\n", str(answer or "")).strip()
    if len(matches) != 1:
        return display_answer, {
            "valid": False,
            "verdict": "insufficient",
            "errors": ["claim_result_missing" if not matches else "multiple_claim_results"],
            "evidence_ids": [],
            "unknown_evidence_ids": [],
            "missing_criteria": [],
        }

    errors = []
    try:
        payload = json.loads(matches[0].group(1))
    except (json.JSONDecodeError, TypeError):
        payload = {}
        errors.append("invalid_claim_result_json")

    verdict = str(payload.get("verdict") or "")
    if verdict not in _CLAIM_VERDICTS:
        errors.append("invalid_verdict")
    rationale = str(payload.get("rationale") or "").strip()
    if not rationale:
        errors.append("rationale_required")
    evidence_ids = [str(item) for item in payload.get("evidence_ids", []) if item]
    unknown = sorted(set(evidence_ids) - set(allowed_evidence_ids))
    if unknown:
        errors.append("unknown_evidence_ids")
    missing_criteria = [str(item) for item in payload.get("missing_criteria", []) if item]
    direct_refutation = payload.get("direct_refutation") is True
    if verdict == "contradicted" and not direct_refutation:
        errors.append("direct_refutation_required")
    if verdict == "insufficient" and not missing_criteria:
        errors.append("missing_criteria_required")

    return display_answer, {
        "valid": not errors,
        "schema_valid": not errors,
        "validation_scope": "format_and_evidence_reference_only",
        "verdict": verdict if verdict in _CLAIM_VERDICTS else "insufficient",
        "rationale": rationale,
        "evidence_ids": evidence_ids,
        "unknown_evidence_ids": unknown,
        "missing_criteria": missing_criteria,
        "direct_refutation": direct_refutation,
        "errors": errors,
    }
