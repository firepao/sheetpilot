#!/usr/bin/env python3
"""Locate SheetPilot and delegate only to the Agent-facing Task API."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_root() -> Path:
    configured = os.environ.get("SHEETPILOT_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend(Path(__file__).resolve().parents)
    current = Path.cwd().resolve()
    candidates.extend([current, *current.parents])
    for candidate in candidates:
        if (candidate / "src" / "sheetpilot" / "agent_cli.py").is_file():
            return candidate.resolve()
    raise SystemExit(
        '{"schema_version":"1.0","status":"CONFIGURATION_REQUIRED",'
        '"message":"找不到 SheetPilot Runtime；本次运行已停止。请用户在新会话前配置 SHEETPILOT_ROOT。",'
        '"recovery":{"action":"HUMAN_ACTION_REQUIRED","retryable":false,'
        '"allowed_amendments":[]}}'
    )


def main() -> int:
    root = find_root()
    sys.path.insert(0, str(root / "src"))
    from sheetpilot.agent_cli import main as sheetpilot_main

    return sheetpilot_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
