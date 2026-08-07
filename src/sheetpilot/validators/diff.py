from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from ..models import ValidationCheck


def check_original_sheets_unchanged(input_path: Path, output_path: Path) -> ValidationCheck:
    left = load_workbook(input_path, read_only=True, data_only=False)
    right = load_workbook(output_path, read_only=True, data_only=False)
    differences = []
    try:
        for name in left.sheetnames:
            if name not in right.sheetnames:
                differences.append({"sheet": name, "reason": "missing"}); continue
            a, b = left[name], right[name]
            if (a.max_row, a.max_column) != (b.max_row, b.max_column): differences.append({"sheet": name, "reason": "dimensions"}); continue
            changed = any(left_row != right_row for left_row, right_row in zip(a.iter_rows(values_only=True), b.iter_rows(values_only=True)))
            if changed: differences.append({"sheet": name, "reason": "values_or_formulas"})
    finally:
        left.close(); right.close()
    return ValidationCheck("declared_change_match", "critical", not differences, "原有工作表值与公式未发生计划外变化", {"differences": differences})
