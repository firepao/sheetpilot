#!/usr/bin/env python3
"""Locate the SheetPilot source tree and delegate to its stable CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_root() -> Path:
    configured = os.environ.get("SHEETPILOT_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend(Path(__file__).resolve().parents)
    candidates.extend(Path.cwd().resolve().parents)
    for candidate in candidates:
        if (candidate / "src" / "sheetpilot" / "cli.py").is_file() and (candidate / "schemas").is_dir():
            return candidate.resolve()
    raise SystemExit("找不到 SheetPilot 根目录；请设置 SHEETPILOT_ROOT。")


def main() -> int:
    root = find_root()
    sys.path.insert(0, str(root / "src"))
    from sheetpilot.cli import main as sheetpilot_main

    return sheetpilot_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
