from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


FILTER_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in"}
METRIC_FUNCTIONS = {"sum", "average", "count"}


MINIMAL_EXAMPLE = {
    "schema_version": "1.0",
    "task_type": "summarize_table",
    "input_file": "D:/data/orders.xlsx",
    "output_file": "D:/result/city-summary.xlsx",
    "user_request": "仅统计有效且未退货订单，按城市汇总销售收入、订单数量和平均订单金额。",
    "source": {"sheet": "清洗明细", "header_row": 1},
    "filters": [
        {"id": "valid_rows", "field": "清洗状态", "operator": "eq", "value": "有效"},
        {"id": "not_returned", "field": "是否退货", "operator": "eq", "value": "否"},
    ],
    "dimensions": [{"id": "city", "field": "城市", "output_name": "城市"}],
    "metrics": [
        {"id": "sales_revenue", "function": "sum", "field": "销售额", "output_name": "销售收入"},
        {"id": "order_count", "function": "count", "mode": "rows", "output_name": "订单数量"},
        {"id": "average_order_amount", "function": "average", "field": "销售额", "output_name": "平均订单金额"},
    ],
    "output": {"sheet": "城市经营汇总", "anchor": "A1", "sort": [{"by": "sales_revenue", "direction": "desc"}]},
    "acceptance": {
        "required_filters": ["valid_rows", "not_returned"],
        "required_dimensions": ["city"],
        "required_metrics": ["sales_revenue", "order_count", "average_order_amount"],
        "required_sort": [{"by": "sales_revenue", "direction": "desc"}],
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def task_type_manifest() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "task_types": [{
            "name": "summarize_table",
            "contract_version": "1.0",
            "description": "过滤一个来源表，按一个或多个维度计算 sum、average、count 指标并写入新工作表。",
            "supported_features": {
                "filter_operators": sorted(FILTER_OPERATORS),
                "filter_combination": "all",
                "metric_functions": ["sum", "average", "count.rows", "count.non_empty"],
                "field_binding": "unique_exact_header_match",
                "output_policy": "create_new_sheet_and_new_file",
            },
            "request_schema": {
                "required": ["schema_version", "task_type", "input_file", "output_file", "user_request", "source", "filters", "dimensions", "metrics", "output", "acceptance"],
                "additionalProperties": False,
            },
            "minimal_example": copy.deepcopy(MINIMAL_EXAMPLE),
        }],
    }


def diagnostic(code: str, path: str, message: str, expected: dict | None = None, actual: dict | None = None) -> dict[str, Any]:
    item = {"code": code, "path": path, "message": message}
    if expected is not None:
        item["expected"] = expected
    if actual is not None:
        item["actual"] = actual
    return item


def invalid_response(errors: list[dict[str, Any]]) -> dict[str, Any]:
    errors = sorted(errors, key=lambda item: (item["path"], item["code"]))
    allowed = []
    for item in errors:
        constraint = item.get("expected", {})
        allowed.append({"op": "replace", "path": item["path"], "constraints": constraint})
    return {
        "schema_version": "1.0", "status": "REQUEST_INVALID", "task_id": None,
        "request_revision": None, "attempt_id": None,
        "error": {
            "code": errors[0]["code"] if len(errors) == 1 else "INVALID_VALUE",
            "phase": "contract_validation", "message": f"Task Request 包含 {len(errors)} 个契约错误。",
            "retryable": True, "diagnostics": errors,
            "recovery": {"action": "AMEND_REQUEST", "retryable": True, "base_revision": None, "allowed_amendments": allowed, "suggested_patch": []},
        },
    }


def validate_request(value: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not isinstance(value, dict):
        return [diagnostic("INVALID_TYPE", "", "请求根节点必须是对象。", {"kind": "object"})]
    allowed = {"schema_version", "task_type", "input_file", "output_file", "user_request", "source", "filters", "dimensions", "metrics", "output", "acceptance"}
    for key in sorted(set(value) - allowed):
        errors.append(diagnostic("UNKNOWN_FIELD", f"/{key}", "请求包含未知字段。"))
    for key in sorted(allowed - set(value)):
        errors.append(diagnostic("MISSING_REQUIRED_FIELD", f"/{key}", "缺少必填字段。"))
    if errors:
        return errors
    if value["schema_version"] != "1.0":
        errors.append(diagnostic("INVALID_ENUM", "/schema_version", "仅支持契约版本 1.0。", {"kind": "enum", "values": ["1.0"]}))
    if value["task_type"] != "summarize_table":
        errors.append(diagnostic("INVALID_ENUM", "/task_type", "不支持该 Task Type。", {"kind": "enum", "values": ["summarize_table"]}))
    for key in ("input_file", "output_file", "user_request"):
        if not isinstance(value[key], str) or not value[key].strip():
            errors.append(diagnostic("INVALID_TYPE", f"/{key}", "字段必须是非空字符串。", {"kind": "non_empty_string"}))
    _validate_object(value["source"], "/source", {"sheet", "header_row"}, errors)
    if isinstance(value["source"], dict):
        if "sheet" in value["source"] and (not isinstance(value["source"]["sheet"], str) or not value["source"]["sheet"]):
            errors.append(diagnostic("INVALID_VALUE", "/source/sheet", "sheet 必须是非空字符串。"))
        if "header_row" in value["source"] and (not isinstance(value["source"]["header_row"], int) or value["source"]["header_row"] < 1):
            errors.append(diagnostic("INVALID_VALUE", "/source/header_row", "header_row 必须是大于等于 1 的整数。"))
    component_ids: dict[str, str] = {}
    _validate_components(value["filters"], "/filters", "filter", component_ids, errors)
    _validate_components(value["dimensions"], "/dimensions", "dimension", component_ids, errors)
    _validate_components(value["metrics"], "/metrics", "metric", component_ids, errors)
    if isinstance(value["dimensions"], list) and not value["dimensions"]:
        errors.append(diagnostic("INVALID_VALUE", "/dimensions", "至少需要一个维度。"))
    if isinstance(value["metrics"], list) and not value["metrics"]:
        errors.append(diagnostic("INVALID_VALUE", "/metrics", "至少需要一个指标。"))
    _validate_output(value["output"], component_ids, errors)
    _validate_acceptance(value["acceptance"], component_ids, errors)
    output_names = [item.get("output_name") for item in value.get("dimensions", []) + value.get("metrics", []) if isinstance(item, dict)]
    if any(isinstance(name, str) and name.startswith("__sp_") for name in output_names):
        errors.append(diagnostic("INVALID_VALUE", "/output", "输出名称不能使用 Runtime 保留前缀 __sp_。"))
    if len(output_names) != len(set(output_names)):
        errors.append(diagnostic("INVALID_COMBINATION", "/output", "维度和指标的输出名称不能重复。"))
    return errors


def _validate_object(value: Any, path: str, allowed: set[str], errors: list[dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        errors.append(diagnostic("INVALID_TYPE", path, "字段必须是对象。", {"kind": "object"})); return
    for key in sorted(set(value) - allowed):
        errors.append(diagnostic("UNKNOWN_FIELD", f"{path}/{key}", "对象包含未知字段。"))


def _validate_components(items: Any, path: str, kind: str, ids: dict[str, str], errors: list[dict[str, Any]]) -> None:
    if not isinstance(items, list):
        errors.append(diagnostic("INVALID_TYPE", path, "字段必须是数组。", {"kind": "array"})); return
    allowed_by_kind = {
        "filter": {"id", "field", "operator", "value"},
        "dimension": {"id", "field", "output_name"},
        "metric": {"id", "function", "field", "mode", "output_name"},
    }
    required_by_kind = {"filter": {"id", "field", "operator", "value"}, "dimension": {"id", "field", "output_name"}, "metric": {"id", "function", "output_name"}}
    for index, item in enumerate(items):
        item_path = f"{path}/{index}"
        if not isinstance(item, dict):
            errors.append(diagnostic("INVALID_TYPE", item_path, "组件必须是对象。")); continue
        for key in sorted(set(item) - allowed_by_kind[kind]):
            errors.append(diagnostic("UNKNOWN_FIELD", f"{item_path}/{key}", "组件包含未知字段。"))
        for key in sorted(required_by_kind[kind] - set(item)):
            errors.append(diagnostic("MISSING_REQUIRED_FIELD", f"{item_path}/{key}", "组件缺少必填字段。"))
        component_id = item.get("id")
        if not isinstance(component_id, str) or not component_id:
            errors.append(diagnostic("INVALID_VALUE", f"{item_path}/id", "组件 id 必须是非空字符串。"))
        elif component_id in ids:
            errors.append(diagnostic("INVALID_COMBINATION", f"{item_path}/id", "组件 id 必须在请求内唯一。"))
        else:
            ids[component_id] = kind
        if kind == "filter" and item.get("operator") not in FILTER_OPERATORS:
            errors.append(diagnostic("INVALID_ENUM", f"{item_path}/operator", "不支持该过滤运算符。", {"kind": "enum", "values": sorted(FILTER_OPERATORS)}))
        if kind == "filter" and item.get("operator") == "in" and (not isinstance(item.get("value"), list) or not item["value"]):
            errors.append(diagnostic("INVALID_VALUE", f"{item_path}/value", "in 的 value 必须是非空数组。"))
        if kind == "metric":
            function, mode, field = item.get("function"), item.get("mode"), item.get("field")
            if function not in METRIC_FUNCTIONS:
                errors.append(diagnostic("INVALID_ENUM", f"{item_path}/function", "不支持该聚合函数。", {"kind": "enum", "values": sorted(METRIC_FUNCTIONS)}))
            elif function in {"sum", "average"} and (not field or "mode" in item):
                errors.append(diagnostic("INVALID_COMBINATION", item_path, "sum/average 必须提供 field 且不能提供 mode。"))
            elif function == "count" and mode not in {"rows", "non_empty"}:
                errors.append(diagnostic("INVALID_ENUM", f"{item_path}/mode", "count mode 必须是 rows 或 non_empty。", {"kind": "enum", "values": ["rows", "non_empty"]}))
            elif function == "count" and ((mode == "rows" and "field" in item) or (mode == "non_empty" and not field)):
                errors.append(diagnostic("INVALID_COMBINATION", item_path, "count.rows 禁止 field；count.non_empty 必须提供 field。"))


def _validate_output(value: Any, ids: dict[str, str], errors: list[dict[str, Any]]) -> None:
    _validate_object(value, "/output", {"sheet", "anchor", "sort"}, errors)
    if not isinstance(value, dict): return
    if not isinstance(value.get("sheet"), str) or not value.get("sheet"):
        errors.append(diagnostic("MISSING_REQUIRED_FIELD", "/output/sheet", "输出 Sheet 必填。"))
    if "sort" in value and not isinstance(value["sort"], list):
        errors.append(diagnostic("INVALID_TYPE", "/output/sort", "sort 必须是数组。")); return
    for index, item in enumerate(value.get("sort", [])):
        if not isinstance(item, dict) or set(item) != {"by", "direction"}:
            errors.append(diagnostic("INVALID_VALUE", f"/output/sort/{index}", "排序项必须只包含 by 和 direction。")); continue
        if item["by"] not in ids:
            errors.append(diagnostic("INVALID_REFERENCE", f"/output/sort/{index}/by", "排序引用不存在。"))
        if item["direction"] not in {"asc", "desc"}:
            errors.append(diagnostic("INVALID_ENUM", f"/output/sort/{index}/direction", "排序方向必须是 asc 或 desc。", {"kind": "enum", "values": ["asc", "desc"]}))


def _validate_acceptance(value: Any, ids: dict[str, str], errors: list[dict[str, Any]]) -> None:
    keys = {"required_filters", "required_dimensions", "required_metrics", "required_sort"}
    _validate_object(value, "/acceptance", keys, errors)
    if not isinstance(value, dict): return
    for key in keys:
        if key not in value:
            errors.append(diagnostic("MISSING_REQUIRED_FIELD", f"/acceptance/{key}", "Acceptance 缺少必填字段。")); continue
        if not isinstance(value[key], list):
            errors.append(diagnostic("INVALID_TYPE", f"/acceptance/{key}", "Acceptance 字段必须是数组。")); continue
        if key != "required_sort":
            expected_kind = key.removeprefix("required_").removesuffix("s")
            for index, component_id in enumerate(value[key]):
                if ids.get(component_id) != expected_kind:
                    errors.append(diagnostic("INVALID_REFERENCE", f"/acceptance/{key}/{index}", "Acceptance 引用不存在或类型不匹配。"))


def acceptance_snapshot(request: dict[str, Any]) -> dict[str, Any]:
    components = {
        item["id"]: copy.deepcopy(item)
        for key in ("filters", "dimensions", "metrics") for item in request[key]
    }
    acceptance = copy.deepcopy(request["acceptance"])
    acceptance["components"] = {component_id: components[component_id] for key in ("required_filters", "required_dimensions", "required_metrics") for component_id in acceptance[key]}
    acceptance["output"] = copy.deepcopy(request["output"])
    return acceptance
