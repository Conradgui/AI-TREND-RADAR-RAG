"""Live 100-round embedded-Chroma staging and snapshot-swap verification."""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import platform
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from rag.index_coordinator import IndexBuildCoordinator, VectorBuildResult
from rag.index_generation import IndexGenerationStore
from rag.retriever.vector_store import VectorStore


async def run(rounds: int = 100) -> dict:
    started = time.perf_counter()
    errors: list[dict] = []
    active_runtime: dict = {}

    with tempfile.TemporaryDirectory(prefix="rag-snapshot-stability-") as temporary:
        root = Path(temporary)
        store = IndexGenerationStore(root)
        coordinator = IndexBuildCoordinator(store)

        for index in range(rounds):
            marker = f"snapshot marker {index}"
            if active_runtime:
                try:
                    active_runtime["vector"].search(active_runtime["marker"], k=1)
                except Exception as exc:
                    errors.append({"round": index, "phase": "query_old", "error": repr(exc)})

            async def build(path: Path, marker=marker, index=index):
                vector = VectorStore(str(path))
                try:
                    vector.add_chunks(
                        [f"Evidence for {marker}"],
                        [{
                            "date": "2026-08-10",
                            "source": "snapshot-test",
                            "title": marker,
                            "citation_id": f"snapshot/{index}",
                        }],
                        [f"snapshot/{index}"],
                    )
                    return VectorBuildResult(1, ["2026-08-10"], f"revision-{index}")
                finally:
                    vector.close()

            async def prepare(path: Path, _manifest: dict, marker=marker):
                vector = VectorStore(str(path))
                if not vector.search(marker, k=1):
                    raise RuntimeError("verified generation cannot retrieve its marker")
                return {"vector": vector, "marker": marker}

            def publish(runtime):
                previous = active_runtime.get("vector")
                active_runtime.clear()
                active_runtime.update(runtime)
                if previous is not None:
                    previous.close()

            try:
                await coordinator.build_and_publish(
                    f"gen-{index:03d}",
                    build=build,
                    prepare_runtime=prepare,
                    publish_runtime=publish,
                )
                active_runtime["vector"].search(marker, k=1)
            except Exception as exc:
                errors.append({"round": index, "phase": "build_or_query_new", "error": repr(exc)})
                break

        active = store.resolve_active()
        final_generation = active.name if active else ""
        if active_runtime:
            active_runtime["vector"].close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rounds_requested": rounds,
        "rounds_completed": rounds if not errors else int(errors[-1]["round"]),
        "passed": not errors,
        "error_finding_id_count": sum("Error finding id" in row["error"] for row in errors),
        "errors": errors,
        "final_generation": final_generation,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "chromadb": importlib.metadata.version("chromadb"),
            "embedding_id": "chroma-default",
            "storage": "temporary-directory",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(run(args.rounds))
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
