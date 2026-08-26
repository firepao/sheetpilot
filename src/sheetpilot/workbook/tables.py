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


def deduplicate(data: TableData, keys: list[str] | None = None, keep: str = "first") -> TableData:
    keys = keys or data.headers
    if any(key not in data.headers for key in keys) or keep not in {"first", "last"}:
        raise ValueError("invalid deduplicate arguments")
    rows = list(reversed(data.rows)) if keep == "last" else list(data.rows)
    seen, output = set(), []
    for row in rows:
        marker = tuple(row.get(key) for key in keys)
        if marker not in seen:
            seen.add(marker); output.append(row)
    if keep == "last": output.reverse()
    return TableData(list(data.headers), output)


def fill_missing(data: TableData, fields: list[str] | None = None, value: Any = "") -> TableData:
    fields = fields or data.headers
    if any(field not in data.headers for field in fields): raise ValueError("unknown fill field")
    return TableData(list(data.headers), [{**row, **{field: value for field in fields if row.get(field) in (None, "")}} for row in data.rows])


def value_counts(data: TableData, field: str, as_count: str = "数量") -> TableData:
    if field not in data.headers: raise ValueError("unknown value-count field")
    counts: dict[Any, int] = {}
    for row in data.rows: counts[row.get(field) if row.get(field) not in (None, "") else "(空)"] = counts.get(row.get(field) if row.get(field) not in (None, "") else "(空)", 0) + 1
    return TableData([field, as_count], [{field: key, as_count: counts[key]} for key in sorted(counts, key=str)])


def count_values(data: TableData, field: str | None = None, mode: str = "rows") -> int:
    """Count rows or non-empty values in a table with explicit, auditable modes."""
    if mode not in {"rows", "non_empty"}:
        raise ValueError("unsupported count mode")
    if mode == "rows":
        return len(data.rows)
    if not field or field not in data.headers:
        raise ValueError("unknown count field")
    return sum(row.get(field) not in (None, "") for row in data.rows)


def unique_values(data: TableData, field: str, sort: bool = True) -> TableData:
    """Return one deterministic row per distinct field value."""
    if field not in data.headers:
        raise ValueError("unknown unique field")
    values = {row.get(field) if row.get(field) not in (None, "") else "(空)" for row in data.rows}
    ordered = sorted(values, key=str) if sort else list(values)
    return TableData([field], [{field: value} for value in ordered])


def describe(data: TableData, fields: list[str] | None = None) -> TableData:
    fields = fields or data.headers
    rows = []
    for field in fields:
        values = [r.get(field) for r in data.rows]
        numeric = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        rows.append({"字段": field, "非空数": sum(v not in (None, "") for v in values), "数值和": sum(numeric) if numeric else None, "数值均值": sum(numeric) / len(numeric) if numeric else None})
    return TableData(["字段", "非空数", "数值和", "数值均值"], rows)


def rename_fields(data: TableData, mapping: dict[str, str]) -> TableData:
    if any(source not in data.headers for source in mapping) or len(set(mapping.get(h, h) for h in data.headers)) != len(data.headers): raise ValueError("invalid field mapping")
    headers = [mapping.get(field, field) for field in data.headers]
    return TableData(headers, [{mapping.get(field, field): row.get(field) for field in data.headers} for row in data.rows])


def concat_tables(tables: list[TableData]) -> TableData:
    headers = []
    for table in tables:
        for field in table.headers:
            if field not in headers: headers.append(field)
    return TableData(headers, [{field: row.get(field) for field in headers} for table in tables for row in table.rows])


def join_tables(left: TableData, right: TableData, on: list[str], how: str = "inner") -> TableData:
    if how not in {"inner", "left"} or any(key not in left.headers or key not in right.headers for key in on): raise ValueError("invalid join")
    right_fields = [field for field in right.headers if field not in on]
    collisions = set(left.headers) & set(right_fields)
    output_fields = [*left.headers, *[f"{field}_right" if field in collisions else field for field in right_fields]]
    index: dict[tuple, list[dict]] = defaultdict(list)
    for row in right.rows: index[tuple(row.get(key) for key in on)].append(row)
    output = []
    for left_row in left.rows:
        matches = index.get(tuple(left_row.get(key) for key in on), [])
        if not matches and how == "left": matches = [{}]
        for right_row in matches: output.append({**left_row, **{f"{field}_right" if field in collisions else field: right_row.get(field) for field in right_fields}})
    return TableData(output_fields, output)


def pivot_table(data: TableData, index: list[str], columns: str, values: str, function: str = "sum") -> TableData:
    if function not in {"sum", "count"}: raise ValueError("unsupported pivot function")
    column_values = sorted({row.get(columns) for row in data.rows}, key=str); buckets: dict[tuple, dict] = {}
    for row in data.rows:
        key=tuple(row.get(field) for field in index); bucket=buckets.setdefault(key,{field:value for field,value in zip(index,key)})
        label=str(row.get(columns)); value=row.get(values)
        if function == "count": bucket[label]=bucket.get(label,0)+1
        elif isinstance(value,(int,float)) and not isinstance(value,bool): bucket[label]=bucket.get(label,0)+value
    headers=[*index,*[str(value) for value in column_values]]
    return TableData(headers,[{field:row.get(field,0) for field in headers} for row in buckets.values()])


def melt_table(data: TableData, id_fields: list[str], value_fields: list[str], variable_name="变量", value_name="值") -> TableData:
    if any(field not in data.headers for field in [*id_fields,*value_fields]): raise ValueError("unknown melt field")
    rows=[]
    for row in data.rows:
        for field in value_fields: rows.append({**{key:row.get(key) for key in id_fields},variable_name:field,value_name:row.get(field)})
    return TableData([*id_fields,variable_name,value_name],rows)


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
