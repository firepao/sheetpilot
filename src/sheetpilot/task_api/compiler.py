from __future__ import annotations

from typing import Any

from .contract import stable_hash


COMPILER_VERSION = "summarize-table/1.0"


def collect_fields(request: dict[str, Any]) -> list[tuple[str, list[str]]]:
    ordered: list[tuple[str, list[str]]] = []
    indexes: dict[str, int] = {}
    components = (("filters", request["filters"]), ("dimensions", request["dimensions"]), ("metrics", request["metrics"]))
    for group, items in components:
        for index, item in enumerate(items):
            field = item.get("field")
            if not field:
                continue
            reference = f"/{group}/{index}/field"
            if field in indexes:
                ordered[indexes[field]][1].append(reference)
            else:
                indexes[field] = len(ordered)
                ordered.append((field, [reference]))
    return ordered


def compile_plan(task_id: str, revision: int, request: dict[str, Any], acceptance_hash: str, binding_snapshot: dict[str, Any], input_hash: str) -> tuple[dict[str, Any], str]:
    slots = binding_snapshot["slots"]
    field_symbols = {slot["logical_field"]: f"__sp_f{index:03d}" for index, slot in enumerate(slots, 1)}
    metric_symbols = {item["id"]: f"__sp_m{index:03d}" for index, item in enumerate(request["metrics"], 1)}
    dimension_symbols = {item["id"]: field_symbols[item["field"]] for item in request["dimensions"]}
    columns = {field_symbols[slot["logical_field"]]: slot["resolution"]["column"] for slot in slots}
    steps: list[dict[str, Any]] = [{
        "id": "read_source", "op": "read_table", "sheet": binding_snapshot["source"]["sheet"],
        "header_row": binding_snapshot["source"]["header_row"], "columns": columns,
    }]
    summarize: dict[str, Any] = {
        "id": "summarize", "op": "summarize_by_dimension", "input": "read_source",
        "group_by": [dimension_symbols[item["id"]] for item in request["dimensions"]],
        "metrics": [],
    }
    if request["filters"]:
        summarize["where"] = {"all": [{"field": field_symbols[item["field"]], "op": item["operator"], "value": item["value"]} for item in request["filters"]]}
    for item in request["metrics"]:
        metric = {"function": item["function"], "as": metric_symbols[item["id"]]}
        if "field" in item: metric["field"] = field_symbols[item["field"]]
        if "mode" in item: metric["mode"] = item["mode"]
        summarize["metrics"].append(metric)
    component_symbols = {**dimension_symbols, **metric_symbols}
    if request["output"].get("sort"):
        summarize["sort"] = [{"field": component_symbols[item["by"]], "direction": item["direction"]} for item in request["output"]["sort"]]
    steps.append(summarize)
    fields = ([{"source": dimension_symbols[item["id"]], "as": item["output_name"]} for item in request["dimensions"]]
              + [{"source": metric_symbols[item["id"]], "as": item["output_name"]} for item in request["metrics"]])
    steps.extend([
        {"id": "project_output", "op": "project_columns", "input": "summarize", "fields": fields},
        {"id": "create_output_sheet", "op": "create_sheet", "sheet": request["output"]["sheet"]},
        {"id": "write_output", "op": "write_table", "input": "project_output", "sheet": request["output"]["sheet"], "anchor": request["output"].get("anchor", "A1")},
    ])
    coverage = []
    for index, item in enumerate(request["filters"]): coverage.append({"component_id": item["id"], "kind": "filter", "compiled_to": [f"summarize.where.all[{index}]"]})
    for index, item in enumerate(request["dimensions"]): coverage.append({"component_id": item["id"], "kind": "dimension", "compiled_to": [f"summarize.group_by[{index}]", f"project_output.fields[{index}]"]})
    offset = len(request["dimensions"])
    for index, item in enumerate(request["metrics"]): coverage.append({"component_id": item["id"], "kind": "metric", "compiled_to": [f"summarize.metrics[{index}]", f"project_output.fields[{offset + index}]"]})
    plan = {
        "schema_version": "1.0", "compiler_version": COMPILER_VERSION, "task_id": task_id,
        "request_revision": revision, "input_sha256": input_hash, "acceptance_hash": acceptance_hash,
        "binding_hash": stable_hash(binding_snapshot), "steps": steps, "coverage": coverage,
        "effects": {"read_sheets": [binding_snapshot["source"]["sheet"]], "create_sheets": [request["output"]["sheet"]], "write_targets": [f"{request['output']['sheet']}!{request['output'].get('anchor', 'A1')}"]},
    }
    return plan, stable_hash(plan)
