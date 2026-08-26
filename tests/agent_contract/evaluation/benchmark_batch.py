#!/usr/bin/env python3
"""Measure batch preparation/evaluation latency for 1/5/31-run samples."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from .evaluate_batch import evaluate_manifest


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def benchmark(manifest_path: Path, output_path: Path, sizes: tuple[int, ...] = (1, 5, 31)) -> dict[str, Any]:
    manifest = _read(manifest_path)
    runs = manifest.get("runs", [])
    results = []
    with tempfile.TemporaryDirectory(prefix="sheetpilot-benchmark-") as temporary:
        root = Path(temporary)
        for size in sizes:
            selected = runs[:size]
            if not selected:
                continue
            sample = {key: value for key, value in manifest.items() if key != "runs"}
            sample["runs"] = selected
            sample_path = root / f"manifest-{size}.json"
            sample_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
            out = root / f"out-{size}"
            start = time.perf_counter(); cold = evaluate_manifest(sample_path, out, use_cache=False); cold_ms = round((time.perf_counter() - start) * 1000, 2)
            start = time.perf_counter(); warm = evaluate_manifest(sample_path, out, use_cache=True); warm_ms = round((time.perf_counter() - start) * 1000, 2)
            cold_scores = [(item.get("scenario_key"), item.get("run_id"), item.get("task_result"), item.get("benchmark_score")) for item in cold.get("runs", [])]
            warm_scores = [(item.get("scenario_key"), item.get("run_id"), item.get("task_result"), item.get("benchmark_score")) for item in warm.get("runs", [])]
            results.append({"run_count": len(selected), "cold_ms": cold_ms, "warm_ms": warm_ms, "cache_speedup": round(cold_ms / warm_ms, 2) if warm_ms else None, "scores_identical": cold_scores == warm_scores, "counts": warm.get("counts", {})})
    report = {"schema_version": "1.0", "manifest": str(manifest_path.resolve()), "samples": results}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark SheetPilot batch evaluation")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = benchmark(args.manifest, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
