from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from ..workbook.tables import TableData, aggregate, parse_date_value


def _table(results: dict[str, Any], params: dict[str, Any]) -> TableData:
    value = results[params["input"]]
    if not isinstance(value, TableData):
        raise ValueError("Composite 输入必须是 TableData")
    return value


def build_traceable_detail(context, params, results):
    data = _table(results, params)
    header = params.get("row_number_header", "原始行号")
    start = int(params.get("first_data_row", 2))
    if header in data.headers:
        raise ValueError("原始行号字段已存在")
    return TableData([header, *data.headers], [{header: start + index, **row} for index, row in enumerate(data.rows)])


def _matches(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    value = row.get(rule["field"])
    operation = rule.get("op", "required")
    if operation == "required":
        return value in (None, "")
    if operation == "not_in":
        return value not in rule.get("values", [])
    if operation == "lt":
        return value is None or value < rule["value"]
    if operation == "lte":
        return value is None or value <= rule["value"]
    if operation == "invalid_date":
        return parse_date_value(value, rule.get("source_format")) is None
    raise ValueError(f"不支持的异常规则: {operation}")


def classify_invalid_rows(context, params, results):
    data = _table(results, params)
    status_header = params.get("status_header", "清洗状态")
    reason_header = params.get("reason_header", "异常原因")
    valid_label = params.get("valid_label", "有效")
    invalid_label = params.get("invalid_label", "异常")
    rules = params["rules"]
    rows = []
    for row in data.rows:
        reasons = [rule.get("reason", rule["field"]) for rule in rules if _matches(row, rule)]
        rows.append({**row, status_header: invalid_label if reasons else valid_label, reason_header: ";".join(reasons)})
    return TableData([*data.headers, status_header, reason_header], rows)


def calculate_profitability(context, params, results):
    data = _table(results, params)
    revenue = params["revenue_field"]
    cost = params["cost_field"]
    profit_header = params.get("profit_header", "利润")
    margin_header = params.get("margin_header", "利润率")
    rows = []
    for row in data.rows:
        revenue_value, cost_value = row.get(revenue), row.get(cost)
        profit = revenue_value - cost_value if isinstance(revenue_value, (int, float)) and isinstance(cost_value, (int, float)) else None
        margin = profit / revenue_value if profit is not None and revenue_value else None
        rows.append({**row, profit_header: profit, margin_header: margin})
    return TableData([*data.headers, profit_header, margin_header], rows)


def summarize_by_dimension(context, params, results):
    return aggregate(_table(results, params), params["group_by"], params["metrics"])


def summarize_by_period(context, params, results):
    data = _table(results, params)
    field = params["date_field"]
    period_header = params.get("period_header", "月份")
    rows = []
    for row in data.rows:
        parsed = parse_date_value(row.get(field), params.get("source_format"))
        period = parsed.strftime("%Y-%m") if parsed else params.get("invalid_period", "(无效日期)")
        rows.append({**row, period_header: period})
    enriched = TableData([*data.headers, period_header], rows)
    return aggregate(enriched, [period_header], params["metrics"])


def build_kpi_block(context, params, results):
    data = _table(results, params)
    row: dict[str, Any] = {}
    for metric in params["metrics"]:
        values = [item.get(metric.get("field")) for item in data.rows]
        function = metric["function"]
        numeric = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if function == "count":
            value = len(data.rows)
        elif function == "sum":
            value = sum(numeric)
        elif function == "average":
            value = sum(numeric) / len(numeric) if numeric else None
        elif function == "count_if":
            value = sum(item == metric.get("value") for item in values)
        else:
            raise ValueError(f"不支持的 KPI 函数: {function}")
        row[metric["as"]] = value
    return TableData(list(row), [row])


def build_reconciliation_sheet(context, params, results):
    rows = []
    for check in params["checks"]:
        left = results[check["left"]]
        right = results[check["right"]]
        tolerance = float(check.get("tolerance", 0))
        difference = left - right
        rows.append({"检查项": check["name"], "源值": left, "结果值": right, "差异": difference, "状态": "PASS" if abs(difference) <= tolerance else "FAIL"})
    return TableData(["检查项", "源值", "结果值", "差异", "状态"], rows)
