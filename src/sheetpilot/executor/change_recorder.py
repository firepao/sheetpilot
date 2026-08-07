from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import ErrorCode, SheetPilotError


class ChangeRecorder:
    def __init__(self, path: Path, budget: dict[str, int]):
        self.path = path
        self.budget = budget
        self.changes: list[dict[str, Any]] = []
        self.counts = {"new_sheets": 0, "written_cells": 0, "new_charts": 0, "modified_existing_formulas": 0}

    def record(self, kind: str, **details: Any) -> None:
        self.changes.append({"kind": kind, **details})
        key = {"create_sheet": "new_sheets", "write": "written_cells", "chart": "new_charts"}.get(kind)
        if key:
            self.counts[key] += int(details.get("count", 1))
            if self.counts[key] > self.budget.get(key, 0):
                raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "执行变更超过计划预算", {"budget": key})

    def snapshot(self) -> dict[str, Any]: return {"counts": self.counts, "changes": self.changes}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
