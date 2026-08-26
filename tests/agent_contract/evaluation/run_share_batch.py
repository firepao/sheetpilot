#!/usr/bin/env python3
"""One-command share-link acquisition and batch evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .acquire_share import acquire
from .evaluate_batch import evaluate_manifest


def _parse_links(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) == 2:
            key, url = parts; run_id = f"run-{line_number:03d}"
        elif len(parts) == 3:
            key, run_id, url = parts
        else:
            raise ValueError(f"links_file_line_{line_number}_must_be_key_tab_url_or_key_tab_run_id_tab_url")
        if not key or not url.startswith(("http://", "https://")):
            raise ValueError(f"invalid_link_entry_line_{line_number}")
        entries.append({"scenario_key": key, "run_id": run_id, "url": url})
    if not entries:
        raise ValueError("links_file_has_no_entries")
    pairs = [(item["scenario_key"], item["run_id"]) for item in entries]
    if len(pairs) != len(set(pairs)):
        raise ValueError("duplicate_scenario_key_and_run_id_in_links_file")
    return entries


def run(links_file: Path, scenario_root: Path, evidence_root: Path, output_dir: Path, user_data_dir: Path, executable_path: str | None, workers: int) -> dict[str, Any]:
    links = _parse_links(links_file)
    acquisition: list[dict[str, Any]] = []
    successful: list[dict[str, Any]] = []
    for item in links:
        try:
            report = acquire(item["url"], item["scenario_key"], item["run_id"], evidence_root, user_data_dir, executable_path)
        except Exception as exc:
            report = {"status": "ERROR", "error": str(exc), "source_url": item["url"], "scenario_key": item["scenario_key"], "run_id": item["run_id"]}
        acquisition.append(report)
        if report.get("status") == "OK":
            run_dir = evidence_root / item["scenario_key"] / item["run_id"]
            successful.append({"scenario_key": item["scenario_key"], "run_id": item["run_id"], "scenario_file": str((scenario_root / f"{item['scenario_key']}.json").resolve()), "replay_file": str((run_dir / "replay.raw.json").resolve())})
    output_dir.mkdir(parents=True, exist_ok=True)
    acquisition_report = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "total": len(acquisition), "success": sum(item.get("status") == "OK" for item in acquisition), "failed": sum(item.get("status") != "OK" for item in acquisition), "items": acquisition}
    (output_dir / "acquisition-summary.json").write_text(json.dumps(acquisition_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not successful:
        return {"status": "ACQUISITION_ERROR", "acquisition": acquisition_report, "runs": []}
    manifest = {"schema_version": "1.0", "scenario_root": str(scenario_root.resolve()), "workers": workers, "runs": successful}
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evaluation = evaluate_manifest(manifest_path, output_dir, use_cache=True)
    evaluation["acquisition"] = acquisition_report
    (output_dir / "batch-summary.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Acquire share links and evaluate them in one command")
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--scenario-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--user-data-dir", type=Path, required=True)
    parser.add_argument("--executable-path")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        result = run(args.links, args.scenario_root, args.evidence_root, args.output_dir, args.user_data_dir, args.executable_path, args.workers)
    except Exception as exc:
        print(json.dumps({"status": "CONFIG_ERROR", "error": str(exc)}, ensure_ascii=False, indent=2)); return 2
    print(json.dumps({
        "status": result.get("status", "completed"),
        "acquisition": result.get("acquisition"),
        "counts": result.get("counts"),
        "scores_file": result.get("scores_file"),
        "archive_note": result.get("archive_note"),
        "output_dir": str(args.output_dir.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "completed" and not result.get("counts", {}).get("ERROR") else 2


if __name__ == "__main__":
    raise SystemExit(main())
