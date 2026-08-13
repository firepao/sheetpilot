from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .evaluator import evaluate_run
from .oracle import evaluate_summarize_table, sha256_file


def _read(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _path_token(value: object, fallback: str) -> str:
    token = re.sub(r"[^0-9A-Za-z._-]+", "-", str(value or "").strip()).strip("-._")
    return token[:64] or fallback


def archive_directory_name(bundle: dict, run_id: str, now: datetime | None = None) -> str:
    scenario = _path_token((bundle.get("scenario") or {}).get("id"), "unknown")
    version = _path_token(bundle.get("skill_version"), "unversioned")
    tested_at = bundle.get("tested_at")
    try:
        tested = datetime.fromisoformat(str(tested_at).replace("Z", "+00:00")) if tested_at else None
    except ValueError:
        tested = None
    tested = tested or now or datetime.now(ZoneInfo("Asia/Shanghai"))
    if tested.tzinfo is None: tested = tested.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    stamp = tested.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%dT%H%M%S%z")
    return f"{scenario}__{version}__{stamp}__{_path_token(run_id, 'run-01')}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SheetPilot Agent run evaluator")
    sub = parser.add_subparsers(dest="command", required=True)
    oracle = sub.add_parser("oracle", help="independently verify a summarize_table output")
    oracle.add_argument("--request", required=True); oracle.add_argument("--output", required=True)
    oracle.add_argument("--input-hash-before")
    evaluate = sub.add_parser("evaluate", help="score a complete run bundle")
    evaluate.add_argument("--bundle", required=True); evaluate.add_argument("--output", required=True)
    archive = sub.add_parser("archive", help="create an immutable timestamped result directory")
    archive.add_argument("--bundle", required=True); archive.add_argument("--results-root", required=True); archive.add_argument("--run-id", default="run-01")
    args = parser.parse_args(argv)
    if args.command == "oracle":
        result = evaluate_summarize_table(_read(args.request), input_sha256_before=args.input_hash_before)
        _write(Path(args.output), result); print(json.dumps(result, ensure_ascii=False)); return 0 if result["passed"] else 1
    bundle = _read(args.bundle)
    if args.command == "evaluate":
        result = evaluate_run(bundle); _write(Path(args.output), result); print(json.dumps(result, ensure_ascii=False)); return 0 if result["task_result"] == "PASS" else 1
    target = Path(args.results_root) / archive_directory_name(bundle, args.run_id)
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.bundle, target / "run-bundle.json")
    evaluation = evaluate_run(bundle); _write(target / "evaluation.json", evaluation)
    output_file = Path((bundle.get("task_request") or {}).get("output_file", ""))
    if output_file.is_file():
        shutil.copy2(output_file, target / output_file.name)
        _write(target / "artifact.json", {"sha256": sha256_file(output_file), "source": str(output_file)})
    print(str(target)); return 0 if evaluation["task_result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
