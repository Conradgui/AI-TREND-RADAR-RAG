"""Request-scoped evidence bookkeeping for grounded chat answers."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass, field


_EVIDENCE_MARKER = re.compile(r"\[(E\d+)\]")
_active_ledger: ContextVar["EvidenceLedger | None"] = ContextVar("active_evidence_ledger", default=None)


def _record_key(record: dict) -> str:
    citation_id = str(record.get("citation_id", "")).strip()
    if citation_id:
        return f"citation:{citation_id.casefold()}"
    return "|".join(
        str(record.get(field, "")).casefold().strip()
        for field in ("evidence_type", "title", "source", "url")
    )


@dataclass
class EvidenceLedger:
    """The evidence admitted for exactly one chat request."""

    records: list[dict] = field(default_factory=list)
    _by_key: dict[str, dict] = field(default_factory=dict, init=False, repr=False)

    def admit(self, candidates: list[dict]) -> list[dict]:
        """Admit unique records in order and assign request-local E identifiers."""
        admitted = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            key = _record_key(candidate)
            if not key.strip("|"):
                continue
            existing = self._by_key.get(key)
            if existing is not None:
                continue
            record = dict(candidate)
            record["evidence_id"] = f"E{len(self.records) + 1}"
            self.records.append(record)
            self._by_key[key] = record
            admitted.append(record)
        return admitted

    def resolve(self, candidates: list[dict]) -> list[dict]:
        """Return the ledger records corresponding to candidates, in candidate order."""
        resolved = []
        seen_ids = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            record = self._by_key.get(_record_key(candidate))
            if record is None or record["evidence_id"] in seen_ids:
                continue
            resolved.append(record)
            seen_ids.add(record["evidence_id"])
        return resolved


def activate_evidence_ledger(ledger: EvidenceLedger) -> Token:
    """Make a ledger available to async Agent tools for the current request only."""
    return _active_ledger.set(ledger)


def deactivate_evidence_ledger(token: Token) -> None:
    _active_ledger.reset(token)


def admit_active_evidence(candidates: list[dict]) -> list[dict]:
    """Admit tool evidence when a chat request ledger is active.

    Direct tool use outside chat still returns the source records, but without a
    request-local identifier because there is no user-visible answer to bind.
    """
    ledger = _active_ledger.get()
    if ledger is None:
        return [dict(candidate) for candidate in candidates if isinstance(candidate, dict)]
    ledger.admit(candidates)
    return ledger.resolve(candidates)


def collect_tool_message_evidence(messages: list, ledger: EvidenceLedger) -> list[dict]:
    """Recover evidence from LangGraph ToolMessages as a defensive fallback."""
    collected = []
    for message in messages:
        if getattr(message, "type", None) != "tool":
            continue
        content = getattr(message, "content", "")
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            continue
        evidence = payload.get("evidence", []) if isinstance(payload, dict) else []
        if isinstance(evidence, list):
            collected.extend(ledger.admit(evidence))
    return collected


def validate_evidence_markers(answer: str, records: list[dict]) -> dict:
    """Parse visible markers and reject references outside this request's ledger."""
    marker_ids = []
    for evidence_id in _EVIDENCE_MARKER.findall(answer or ""):
        if evidence_id not in marker_ids:
            marker_ids.append(evidence_id)

    known_ids = {str(record.get("evidence_id", "")) for record in records}
    unknown_ids = [evidence_id for evidence_id in marker_ids if evidence_id not in known_ids]
    claim_evidence = []
    for line in (answer or "").splitlines():
        line_ids = []
        for evidence_id in _EVIDENCE_MARKER.findall(line):
            if evidence_id in known_ids and evidence_id not in line_ids:
                line_ids.append(evidence_id)
        if not line_ids:
            continue
        claim = _EVIDENCE_MARKER.sub("", line).strip(" -\t")
        if claim:
            claim_evidence.append({"claim": claim, "evidence_ids": line_ids})

    return {
        "is_valid": bool(marker_ids) and not unknown_ids,
        "marker_ids": marker_ids,
        "unknown_evidence_ids": unknown_ids,
        "missing_evidence_markers": not marker_ids,
        "claim_evidence": claim_evidence,
    }
