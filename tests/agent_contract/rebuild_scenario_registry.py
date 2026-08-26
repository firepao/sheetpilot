#!/usr/bin/env python3
"""Rebuild the canonical 31-scenario registry from prompt documents and fixtures."""
from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"
DATA = ROOT / "data"
SCENARIOS = ROOT / "scenarios"

SCENARIO_FILES = {
    "S1_department_sales": "01_simple_department_sales.xlsx",
    "S3_count_rows": "S3_count_rows.xlsx",
    "S4_count_non_empty": "S4_count_non_empty.xlsx",
    "S5_average": "S5_average.xlsx",
    "S6_single_filter": "S6_single_filter.xlsx",
    "S7_two_dims": "S7_two_dims.xlsx",
    "S8_multi_metrics": "S8_multi_metrics.xlsx",
    "S9_multi_filter": "S9_multi_filter.xlsx",
    "M1_ecommerce_orders": "M1_ecommerce_orders.xlsx",
    "M2_employee_performance": "M2_employee_performance.xlsx",
    "M4_marketing_roi": "M4_marketing_roi.xlsx",
    "M6_supplier_analysis": "M6_supplier_analysis.xlsx",
    "H1_date_ambiguity": "H1_date_ambiguity.xlsx",
    "H2_field_similarity": "H2_field_similarity.xlsx",
    "H3_ambiguous_field": "H3_sales_multi_amount.xlsx",
    "H4_complex_filter": "H4_complex_filter.xlsx",
    "H5_three_dims": "H5_three_dims.xlsx",
    "R1_finance_reconciliation": "R1_finance_ledger.xlsx",
    "R2_inventory_alert": "R2_inventory_sku.xlsx",
    "R3_hr_payroll": "R3_hr_payroll.xlsx",
    "R4_customer_rfm": "R4_customer_rfm.xlsx",
    "R5_ad_roi": "R5_ad_roi.xlsx",
    "R6_logistics_timeout": "R6_logistics_timeout.xlsx",
    "E2_EDIT_EXISTING_WORKBOOK_SUMMARY": "08_complex_saas_renewals.xlsx",
    "I3_DIRTY_DATA_CLEAN_ANALYSIS": "09_complex_dirty_logistics.xlsx",
    "N1_CREATE_COMPLEX_OPERATING_SUMMARY": "07_complex_retail_operations.xlsx",
}


def _prompt(markdown: str, scenario_key: str) -> str:
    section = re.search(r"^## 用户需求（Prompt）\s*$([\s\S]*?)(?=^## |\Z)", markdown, re.MULTILINE)
    scope = section.group(1) if section else markdown
    block = re.search(r"```(?:text|plaintext)?\s*\n([\s\S]*?)```", scope)
    if not block:
        raise ValueError(f"No prompt block found for {scenario_key}")
    prompt = block.group(1).strip()
    prompt = re.sub(r"测试场景：[A-Z]+\d+", f"测试场景：{scenario_key}", prompt)
    return prompt


def _expected_fields(markdown: str) -> list[str]:
    for block in re.findall(r"```json\s*\n([\s\S]*?)```", markdown):
        if '"task_type"' not in block:
            continue
        fields = re.findall(r'"field"\s*:\s*"([^"]+)"', block)
        return sorted(set(fields))
    return []


def _source(data_file: Path, markdown: str) -> dict[str, object]:
    workbook = load_workbook(data_file, read_only=True, data_only=True)
    try:
        source_match = re.search(r'"sheet"\s*:\s*"([^"]+)"[^\n}]*"header_row"\s*:\s*(\d+)', markdown)
        mentioned_sheets = [name for name in workbook.sheetnames if name in markdown]
        requested_sheet = source_match.group(1) if source_match and source_match.group(1) in workbook.sheetnames else (mentioned_sheets[0] if mentioned_sheets else workbook.sheetnames[0])
        if requested_sheet not in workbook.sheetnames:
            raise ValueError(f"Prompt source sheet {requested_sheet!r} not found in {data_file}")
        sheet = workbook[requested_sheet]
        if source_match and source_match.group(1) == requested_sheet:
            return {"sheet": sheet.title, "header_row": int(source_match.group(2))}
        for row_number in range(1, min(sheet.max_row, 20) + 1):
            values = [cell.value for cell in sheet[row_number]]
            if sum(value not in (None, "") for value in values) >= 2:
                return {"sheet": sheet.title, "header_row": row_number}
    finally:
        workbook.close()
    raise ValueError(f"No header row found in {data_file}")


def rebuild() -> None:
    SCENARIOS.mkdir(parents=True, exist_ok=True)
    expected_names = {f"{key}.json" for key in SCENARIO_FILES}
    for stale in SCENARIOS.glob("*.json"):
        if stale.name not in expected_names:
            stale.unlink()
    for key, data_name in SCENARIO_FILES.items():
        prompt_path = PROMPTS / f"{key}.md"
        data_path = DATA / data_name
        if not prompt_path.is_file() or not data_path.is_file():
            raise FileNotFoundError(f"Missing prompt or fixture for {key}")
        markdown = prompt_path.read_text(encoding="utf-8")
        title = markdown.splitlines()[0].lstrip("# ").strip()
        scenario = {
            "schema_version": "1.0",
            "scenario_key": key,
            "id": key,
            "short_id": key.split("_", 1)[0],
            "name": title,
            "status": "active",
            "evaluation_mode": "semantic",
            "prompt_file": prompt_path.name,
            "data_file": data_name,
            "source": _source(data_path, markdown),
            "expected_source_fields": _expected_fields(markdown),
            "user_prompt": _prompt(markdown, key),
            "expected_outcome": "success",
        }
        (SCENARIOS / f"{key}.json").write_text(
            json.dumps(scenario, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    rebuild()
