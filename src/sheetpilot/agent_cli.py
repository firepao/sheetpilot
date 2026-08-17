from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .task_api import TaskRuntime


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sheetpilot-agent", description="SheetPilot Agent-facing Task API")
    commands = parser.add_subparsers(dest="command", required=True)
    types = commands.add_parser("task-types", help="Return the complete public Task Contract")
    types.add_argument("--input"); types.add_argument("--sheet"); types.add_argument("--header-row", type=int)
    run = commands.add_parser("task-run", help="Create or continue a Task")
    run.add_argument("--request", required=True)
    status = commands.add_parser("task-status", help="Return current delivery state")
    status.add_argument("--task-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime = TaskRuntime()
    if args.command == "task-types":
        result = runtime.task_types(args.input, args.sheet, args.header_row)
    elif args.command == "task-run":
        result = runtime.run(_read_json(args.request))
    else:
        result = runtime.status(args.task_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
