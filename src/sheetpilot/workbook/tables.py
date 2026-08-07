from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from openpyxl.utils import column_index_from_string


@dataclass
class TableData:
    headers: list[str]
    rows: list[dict[str, Any]]


def parse_date_value(value: Any, source_format: str | None = None) -> date | None:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if not isinstance(value, str): return None
    text = value.strip()
    if source_format:
        return datetime.strptime(text, source_format).date()
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def read_table(engine, sheet: str, header_row: int, columns: dict[str, str]) -> TableData:
    ws = engine.worksheet(sheet)
    rows = []
    for row in range(header_row + 1, ws.max_row + 1):
        item = {field: ws.cell(row, column_index_from_string(column)).value for field, column in columns.items()}
        if any(value not in (None, "") for value in item.values()): rows.append(item)
    return TableData(list(columns), rows)


def aggregate(data: TableData, group_by: list[str], metrics: list[dict], date_field: str | None = None, current_period: list | None = None) -> TableData:
    buckets: dict[tuple, dict[str, Any]] = {}
    start, end = (current_period or [None, None])[:2]
    for row in data.rows:
        if date_field and start and end:
            value = row.get(date_field)
            normalized = parse_date_value(value)
            if isinstance(normalized, date):
                if not (date.fromisoformat(start) <= normalized <= date.fromisoformat(end)): continue
            else: continue
        key = tuple(row.get(field) if row.get(field) not in (None, "") else "(空)" for field in group_by)
        bucket = buckets.setdefault(key, {"__rows__": 0})
        bucket["__rows__"] += 1
        for metric in metrics:
            function, alias = metric["function"], metric["as"]
            value = row.get(metric.get("field")) if metric.get("field") else None
            if function == "count":
                if metric.get("mode") == "rows": bucket[alias] = bucket.get(alias, 0) + 1
                elif metric.get("mode") == "non_empty" and value not in (None, ""): bucket[alias] = bucket.get(alias, 0) + 1
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                if function == "sum": bucket[alias] = bucket.get(alias, 0) + value
                elif function == "average":
                    bucket.setdefault("__average__", {}).setdefault(alias, []).append(value)
    headers = [*group_by, *[m["as"] for m in metrics]]
    rows = []
    for key in sorted(buckets, key=lambda x: tuple(str(v) for v in x)):
        values = {}
        bucket = buckets[key]
        averages = bucket.get("__average__", {})
        for metric in metrics:
            alias = metric["as"]
            if metric["function"] == "average":
                numbers = averages.get(alias, [])
                values[alias] = sum(numbers) / len(numbers) if numbers else None
            else: values[alias] = bucket.get(alias, 0)
        rows.append({**dict(zip(group_by, key)), **values})
    return TableData(headers, rows)


def _match_condition(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    field, op, expected = condition["field"], condition["op"], condition.get("value")
    actual = row.get(field)
    if op == "is_null": return actual in (None, "")
    if op == "not_null": return actual not in (None, "")
    if op in {"between", "gt", "gte", "lt", "lte"} and condition.get("value_type") == "date":
        actual = parse_date_value(actual, condition.get("source_format"))
        expected = [date.fromisoformat(item) for item in expected] if op == "between" else date.fromisoformat(expected)
    if op == "eq": return actual == expected
    if op == "ne": return actual != expected
    if op == "gt": return actual is not None and actual > expected
    if op == "gte": return actual is not None and actual >= expected
    if op == "lt": return actual is not None and actual < expected
    if op == "lte": return actual is not None and actual <= expected
    if op == "in": return actual in expected
    if op == "not_in": return actual not in expected
    if op == "contains": return isinstance(actual, str) and str(expected) in actual
    if op == "starts_with": return isinstance(actual, str) and actual.startswith(str(expected))
    if op == "ends_with": return isinstance(actual, str) and actual.endswith(str(expected))
    if op == "between": return actual is not None and expected[0] <= actual <= expected[1]
    raise ValueError(f"unsupported filter op: {op}")


def filter_rows(data: TableData, where: dict[str, Any], invalid_value_policy: str = "exclude") -> TableData:
    fields = set(data.headers)
    conditions = []
    for branch in (where.get("all", []), where.get("any", [])):
        for condition in branch:
            if condition.get("field") not in fields: raise ValueError(f"unknown filter field: {condition.get('field')}")
            conditions.append(condition)
    output, invalid = [], 0
    for row in data.rows:
        try:
            all_ok = all(_match_condition(row, item) for item in where.get("all", []))
            any_ok = not where.get("any") or any(_match_condition(row, item) for item in where.get("any", []))
        except (TypeError, ValueError):
            invalid += 1
            if invalid_value_policy == "fail": raise
            all_ok = any_ok = invalid_value_policy == "keep"
        if all_ok and any_ok: output.append(row)
    return TableData(list(data.headers), output)


def select_columns(data: TableData, fields: list[dict[str, str]]) -> TableData:
    source = set(data.headers); output_headers = [item["as"] for item in fields]
    if len(output_headers) != len(set(output_headers)) or any(item["source"] not in source for item in fields): raise ValueError("invalid column selection")
    return TableData(output_headers, [{item["as"]: row.get(item["source"]) for item in fields} for row in data.rows])


def sort_rows(data: TableData, keys: list[dict[str, Any]]) -> TableData:
    if any(key["field"] not in data.headers or key.get("direction", "asc") not in {"asc", "desc"} for key in keys): raise ValueError("invalid sort key")
    rows = list(data.rows)
    for key in reversed(keys):
        field, reverse = key["field"], key.get("direction", "asc") == "desc"
        rows.sort(key=lambda row: (row.get(field) is None, row.get(field) if isinstance(row.get(field), (int, float, date, datetime)) else str(row.get(field)) if row.get(field) is not None else ""), reverse=reverse)
    return TableData(list(data.headers), rows)


def derive_column(data: TableData, name: str, template: str, arguments: dict[str, str]) -> TableData:
    if name in data.headers: raise ValueError("derived field already exists")
    if any(field not in data.headers for field in arguments.values()): raise ValueError("derived source field missing")
    def calculate(row):
        values = {key: row[field] for key, field in arguments.items()}
        if template == "add": return values["left"] + values["right"]
        if template == "subtract": return values["left"] - values["right"]
        if template == "multiply": return values["left"] * values["right"]
        if template == "safe_divide": return None if not values["denominator"] else values["numerator"] / values["denominator"]
        if template == "coalesce": return values["first"] if values["first"] not in (None, "") else values["second"]
        raise ValueError("unsupported derive template")
    return TableData([*data.headers, name], [{**row, name: calculate(row)} for row in data.rows])
