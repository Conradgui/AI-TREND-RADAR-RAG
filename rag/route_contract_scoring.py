"""Strict, reusable scoring primitives for Route Contract projections."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ProtectedTermScore:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


def score_protected_terms(actual: list[str], expected: list[str]) -> ProtectedTermScore:
    """Compare normalized independent spans and penalize missing and extra spans."""
    actual_set = {_normalize(term) for term in actual}
    expected_set = {_normalize(term) for term in expected}
    actual_set.discard("")
    expected_set.discard("")

    true_positive = len(actual_set & expected_set)
    false_positive = len(actual_set - expected_set)
    false_negative = len(expected_set - actual_set)
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    f1 = _ratio(2 * precision * recall, precision + recall)
    return ProtectedTermScore(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip(" \"'“”‘’")


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 1.0
