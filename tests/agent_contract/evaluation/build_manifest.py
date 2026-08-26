#!/usr/bin/env python3
"""Build an explicit batch manifest from the active scenario registry.

Evidence is matched only by exact scenario-key directory and run directory.
The tool never selects a latest file and never silently drops a scenario.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def build(scenario_root: Path, evidence_root: Path, output: Path) -> dict[str, Any]:
    scenario_root = scenario_root.resolve()
    evidence_root = evidence_root.resolve()
    output = output.resolve()
    scenarios = []
    errors = []
    for scenario_path in sorted(scenario_root.glob("*.json")):
        try:
            scenario = _read(scenario_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid_scenario:{scenario_path.name}:{exc}")
            continue
        key = scenario.get("scenario_key")
        if scenario.get("status") != "active" or not isinstance(key, str) or key != scenario_path.stem:
            errors.append(f"scenario_not_active_or_key_mismatch:{scenario_path.name}")
            continue
        scenarios.append((key, scenario_path))

    runs: list[dict[str, Any]] = []
    for key, scenario_path in scenarios:
        scenario_dir = evidence_root / key
        if not scenario_dir.is_dir():
            errors.append(f"missing_evidence_directory:{key}")
            continue
        run_dirs = sorted(path for path in scenario_dir.iterdir() if path.is_dir())
        if not run_dirs:
            errors.append(f"missing_run_directory:{key}")
            continue
        for run_dir in run_dirs:
            bundle = run_dir / "run-bundle.json"
            replay = run_dir / "replay.raw.json"
            if not bundle.is_file() and not replay.is_file():
                errors.append(f"missing_bundle_and_replay:{key}:{run_dir.name}")
                continue
            entry = {"scenario_key": key, "run_id": run_dir.name, "scenario_file": str(scenario_path.resolve())}
            if bundle.is_file(): entry["bundle_file"] = str(bundle)
            if replay.is_file(): entry["replay_file"] = str(replay)
            runs.append(entry)

    pairs = [(item["scenario_key"], item["run_id"]) for item in runs]
    if len(pairs) != len(set(pairs)):
        errors.append("duplicate_scenario_key_and_run_id")
    manifest = {"schema_version": "1.0", "runs": runs, "build": {"scenario_count": len(scenarios), "run_count": len(runs), "errors": errors}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an explicit SheetPilot batch manifest")
    parser.add_argument("--scenario-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = build(args.scenario_root, args.evidence_root, args.output)
    print(json.dumps(manifest["build"], ensure_ascii=False, indent=2))
    return 1 if manifest["build"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
