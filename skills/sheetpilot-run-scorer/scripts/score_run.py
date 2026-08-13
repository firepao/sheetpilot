#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "tests" / "agent_contract" / "evaluation" / "evaluator.py").is_file(): return parent
    raise RuntimeError("SheetPilot repository root not found")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically score one SheetPilot Agent run")
    parser.add_argument("bundle", type=Path); parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(); sys.path.insert(0, str(_repo_root()))
    from tests.agent_contract.evaluation.evaluator import evaluate_run
    bundle = json.loads(args.bundle.read_text(encoding="utf-8")); result = evaluate_run(bundle)
    result.update({key: bundle.get(key) for key in ("prompt", "platform", "model", "skill_version", "runtime_version", "git_commit", "skill_sha256", "tested_at", "failure_class", "review_notes") if bundle.get(key) is not None})
    result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
    result["run_id"] = bundle.get("run_id") or f"run-{uuid.uuid4().hex[:12]}"
    result["bundle_sha256"] = hashlib.sha256(args.bundle.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False)); return 0 if result["task_result"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
