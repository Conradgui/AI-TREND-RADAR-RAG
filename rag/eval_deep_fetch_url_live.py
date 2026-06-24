"""Run one live URL deep-fetch smoke against a known external source."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from rag.deep_fetch_policy import apply_deep_fetch_policy
from rag.runtime_tools import select_external_deep_fetcher


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/deep-fetch-url-live-smoke-2026-06-23.json")
DEFAULT_URL = "https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing"


def build_deep_fetch_url_smoke(url: str) -> dict:
    """Fetch one official URL through the same deep-fetch policy used by chat."""
    citation = {
        "evidence_type": "external",
        "provider": "manual_live_smoke",
        "source": "cloud.google.com",
        "source_type": "web",
        "title": "How the Open Knowledge Format can improve data sharing",
        "url": url,
        "retrieved_at": date.today().isoformat(),
        "excerpt": "Known official URL used to validate live URL deep-fetch behavior.",
        "source_quality": "official",
        "quality_score": 1.0,
        "needs_deep_fetch": False,
        "quality_notes": [],
    }
    citations, trace = apply_deep_fetch_policy(
        [citation],
        fetcher=select_external_deep_fetcher(True),
        max_urls=1,
        enabled=True,
    )
    deep_fetch = citations[0].get("deep_fetch", {})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "trace": trace,
        "citation": citations[0],
        "summary": {
            "attempted": trace.get("attempted"),
            "selected_count": trace.get("selected_count"),
            "success_count": trace.get("success_count"),
            "failure_count": trace.get("failure_count"),
            "fetch_ok": deep_fetch.get("ok"),
            "status_code": deep_fetch.get("status_code"),
            "content_type": deep_fetch.get("content_type"),
            "title": deep_fetch.get("title", ""),
            "text_excerpt_length": len(deep_fetch.get("text_excerpt", "")),
            "error": deep_fetch.get("error", ""),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one live URL deep-fetch smoke.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    smoke = build_deep_fetch_url_smoke(args.url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                **smoke["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
