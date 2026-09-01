import json
from pathlib import Path

import pytest

from rag.eval_important_news import evaluate_dataset


@pytest.mark.asyncio
async def test_confirmed_product_rules_distinguish_main_background_and_exclusions():
    dataset = json.loads(Path(
        "docs/rag-transformation/evals/important-news-calibration-v2.json"
    ).read_text(encoding="utf-8"))

    result = await evaluate_dataset(dataset)

    assert result["summary"] == {
        "total": 12,
        "passed": 12,
        "failed": 0,
        "gate_passed": True,
    }
