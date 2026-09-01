"""Validated machine contract between one-pass answer composition and UI rendering."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


SCHEMA_VERSION = "answer-envelope/1.0"
_EVIDENCE_ID = re.compile(r"^E\d+$")
_VISIBLE_MARKER = re.compile(r"\[(E\d+)\]")
_CLAIM_VERDICTS = {"supported", "contradicted", "insufficient"}


@dataclass(frozen=True)
class AnswerEnvelope:
    body_markdown: str
    evidence_ids: tuple[str, ...]
    claim_verification: dict | None = None
    schema_version: str = SCHEMA_VERSION


def _validate_claim_verification(
    payload: object,
    known_evidence_ids: set[str],
    declared_evidence_ids: set[str],
) -> tuple[dict | None, list[str]]:
    if not isinstance(payload, dict):
        return None, ["claim_verification_missing"]

    errors: list[str] = []
    verdict = str(payload.get("verdict") or "")
    if verdict not in _CLAIM_VERDICTS:
        errors.append("invalid_verdict")
    rationale = str(payload.get("rationale") or "").strip()
    if not rationale:
        errors.append("rationale_required")
    raw_evidence_ids = payload.get("evidence_ids")
    if not isinstance(raw_evidence_ids, list) or any(
        not isinstance(value, str) or not _EVIDENCE_ID.fullmatch(value)
        for value in (raw_evidence_ids if isinstance(raw_evidence_ids, list) else [])
    ):
        errors.append("invalid_claim_evidence_ids")
        evidence_ids: list[str] = []
    else:
        evidence_ids = list(raw_evidence_ids)
    unknown = sorted(set(evidence_ids) - known_evidence_ids)
    if unknown:
        errors.append("unknown_claim_evidence_ids")
    if set(evidence_ids) - declared_evidence_ids:
        errors.append("undeclared_claim_evidence_ids")
    raw_missing = payload.get("missing_criteria")
    if not isinstance(raw_missing, list) or any(
        not isinstance(value, str) or not value.strip()
        for value in (raw_missing if isinstance(raw_missing, list) else [])
    ):
        errors.append("invalid_missing_criteria")
        missing_criteria: list[str] = []
    else:
        missing_criteria = [value.strip() for value in raw_missing]
    direct_refutation = payload.get("direct_refutation") is True
    if verdict == "contradicted" and not direct_refutation:
        errors.append("direct_refutation_required")
    if verdict == "contradicted" and not evidence_ids:
        errors.append("contradicting_evidence_required")
    if verdict == "insufficient" and not missing_criteria:
        errors.append("missing_criteria_required")
    if verdict == "supported" and not evidence_ids:
        errors.append("supporting_evidence_required")

    result = {
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
    return result, errors


def parse_answer_envelope(
    raw: str,
    known_evidence_ids: set[str],
    *,
    require_claim_verification: bool = False,
) -> dict:
    """Parse and validate a direct-composer result without a repair model call."""
    text = str(raw or "").strip()
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return {"valid": False, "errors": ["invalid_json"], "envelope": None}
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["not_an_object"], "envelope": None}

    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")
    body = payload.get("body_markdown")
    if not isinstance(body, str) or not body.strip():
        errors.append("missing_body_markdown")
        body = ""
    else:
        # Some OpenAI-compatible providers double-escape Markdown newlines
        # inside an otherwise valid JSON string. Normalize presentation-only
        # line breaks without changing evidence IDs or factual content.
        body = body.replace("\\r\\n", "\n").replace("\\n", "\n")
    declared = payload.get("evidence_ids")
    if not isinstance(declared, list) or any(
        not isinstance(value, str) or not _EVIDENCE_ID.fullmatch(value)
        for value in (declared if isinstance(declared, list) else [])
    ):
        errors.append("invalid_evidence_ids")
        declared = []
    declared_ids = list(declared)
    if len(set(declared_ids)) != len(declared_ids):
        errors.append("duplicate_evidence_id")
    marker_ids = list(dict.fromkeys(_VISIBLE_MARKER.findall(body)))
    if declared_ids != marker_ids:
        errors.append("evidence_marker_mismatch")
    if any(evidence_id not in known_evidence_ids for evidence_id in declared_ids):
        errors.append("unknown_evidence_id")

    claim_verification = None
    if "claim_verification" in payload or require_claim_verification:
        claim_verification, claim_errors = _validate_claim_verification(
            payload.get("claim_verification"),
            known_evidence_ids,
            set(declared_ids),
        )
        errors.extend(claim_errors)

    if errors:
        return {"valid": False, "errors": errors, "envelope": None}
    return {
        "valid": True,
        "errors": [],
        "envelope": AnswerEnvelope(
            body_markdown=body.strip(),
            evidence_ids=tuple(declared_ids),
            claim_verification=claim_verification,
        ),
    }


def answer_envelope_instruction(*, require_claim_verification: bool = False) -> str:
    """Return the provider-neutral JSON contract appended to direct prompts."""
    instruction = (
        "只输出一个 JSON 对象，不要输出代码围栏或额外文字。格式必须为："
        '{"schema_version":"answer-envelope/1.0",'
        '"body_markdown":"面向用户的 Markdown 正文，证据写为 [E1]",'
        '"evidence_ids":["E1"]}。'
        "evidence_ids 必须按正文首次出现顺序列出全部且仅列出正文使用的证据编号。"
    )
    if require_claim_verification:
        instruction += (
            "本任务还必须在同一 JSON 顶层加入 claim_verification："
            '{"verdict":"supported|contradicted|insufficient",'
            '"rationale":"简短理由","evidence_ids":["E1"],'
            '"missing_criteria":[],"direct_refutation":false}。'
            "insufficient 必须列出 missing_criteria；contradicted 必须有直接反证并将 "
            "direct_refutation 设为 true。不要输出 HTML 注释。"
        )
    return instruction
