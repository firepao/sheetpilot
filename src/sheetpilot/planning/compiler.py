from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openpyxl.utils.cell import coordinate_to_tuple
from openpyxl.utils.cell import range_boundaries

from ..errors import ErrorCode, SheetPilotError
from ..models import ExecutionPlan, ExecutionStep, HighLevelPlan, Requirement, RequirementCoverage, SemanticTask, WorkbookProfile
from ..capabilities import DEFAULT_REGISTRY


def _topological(steps):
    ids = [step.id for step in steps]
    if len(ids) != len(set(ids)):
        raise SheetPilotError(ErrorCode.PLAN_INVALID, "步骤 ID 必须唯一")
    known, ordered = set(), []
    remaining = list(steps)
    while remaining:
        ready = [s for s in remaining if set(_dependencies(s)).issubset(known)]
        if not ready:
            missing = {d for s in remaining for d in _dependencies(s) if d not in ids}
            message = "步骤引用不存在" if missing else "步骤依赖存在循环"
            raise SheetPilotError(ErrorCode.PLAN_INVALID, message, {"dependencies": sorted(missing)})
        for step in ready:
            ordered.append(step); known.add(step.id); remaining.remove(step)
    return ordered


def _dependencies(step) -> list[str]:
    value = step.parameters.get("input")
    return [value] if isinstance(value, str) else []


def compile_plan(task: SemanticTask, high_plan: HighLevelPlan, profile: WorkbookProfile, registry=DEFAULT_REGISTRY) -> ExecutionPlan:
    if task.task_id != high_plan.task_id:
        raise SheetPilotError(ErrorCode.PLAN_INVALID, "任务 ID 与高层计划不一致")
    profile_sheet = next((s for s in profile.sheets if s.name == task.source.get("sheet")), None)
    if not profile_sheet:
        raise SheetPilotError(ErrorCode.PLAN_INVALID, "源工作表不存在")
    header = profile_sheet.header_candidates[0] if profile_sheet.header_candidates else None
    columns = {field.header: field.column for field in header.fields} if header else {}
    for concept in task.concepts.values():
        if concept.field not in columns or columns[concept.field] != concept.column:
            raise SheetPilotError(ErrorCode.PLAN_INVALID, "字段映射与工作簿画像不一致", {"field": concept.field, "column": concept.column})
    ordered = _topological(high_plan.steps)
    existing = {sheet.name for sheet in profile.sheets}
    created = set()
    output_steps = []
    written_cells = charts = 0
    required_validations = {"file_integrity", "input_unchanged", "business_reconciliation", "declared_change_match"}
    for step in ordered:
        definition = registry.require(step.op, "openpyxl")
        required_validations.update(definition.required_validations)
        params = dict(step.parameters)
        definition.validator(params)
        reads, writes = [], []
        if step.op == "read_table":
            _, _, _, max_row = range_boundaries(profile_sheet.used_range)
            reads = [f"'{params['sheet']}'!{columns[f]}{header.row_end + 1}:{columns[f]}{max_row}" for f in params["fields"]]
            params["columns"] = {field: columns[field] for field in params["fields"]}
        if step.op == "create_sheet":
            if params["sheet"] in existing or params["sheet"] in created:
                raise SheetPilotError(ErrorCode.PLAN_INVALID, "目标工作表已存在", {"sheet": params["sheet"]})
            created.add(params["sheet"])
        if step.op == "write_table":
            if params["sheet"] not in created:
                raise SheetPilotError(ErrorCode.PLAN_INVALID, "MVP 仅允许写入本计划新建工作表")
            row, col = coordinate_to_tuple(params["anchor"])
            writes = [f"'{params['sheet']}'!{params['anchor']}:XFD1048576"]
            written_cells += max(1, (1048576 - row + 1) * min(20, 16384 - col + 1))
        if step.op == "create_chart": charts += 1
        output_steps.append(ExecutionStep(step.id, step.op, _dependencies(step), params, reads, writes, definition.kind))
    budget = {"new_sheets": len(created), "written_cells": max(written_cells, 1000), "new_charts": charts, "modified_existing_formulas": 0}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    requirements = [Requirement(item.get("id", f"assertion-{index}"), item.get("description", item.get("type", "业务断言")), True, "business_reconciliation") for index, item in enumerate(high_plan.assertions, 1)]
    coverage = [RequirementCoverage(item.id, "COVERED", [step.id for step in output_steps], "由显式业务断言和独立 Validator 覆盖") for item in requirements]
    strategy = "RECIPE" if high_plan.recipe else "COMPOSED"
    return ExecutionPlan("1.1", f"plan-{task.task_id}-{stamp}", task.task_id, task.input_file, task.output_file, profile.input["sha256"], "openpyxl", output_steps, budget, sorted(required_validations), high_plan.assertions, strategy, requirements, coverage, ["由兼容 HighLevelPlan 编译为单一 ExecutionPlan"])
