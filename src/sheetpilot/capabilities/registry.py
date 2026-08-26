from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..errors import ErrorCode, SheetPilotError
from ..composites import (
    build_kpi_block,
    build_reconciliation_sheet,
    build_traceable_detail,
    calculate_profitability,
    classify_invalid_rows,
    summarize_by_dimension,
    summarize_by_period,
)
from ..atomic.catalog import PHASE_ONE, PHASE_TWO, PHASE_THREE
from .atomic_handlers import handler as atomic_handler


Validator = Callable[[dict[str, Any]], dict[str, Any]]
Handler = Callable[[Any, dict[str, Any], dict[str, Any]], Any]


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    version: str
    input_kind: str
    output_kind: str
    risk_level: str
    supported_engines: frozenset[str]
    required_validations: tuple[str, ...]
    side_effects: frozenset[str]
    validator: Validator
    handler: Handler
    kind: str = "CAPABILITY"
    covers: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "input_kind": self.input_kind,
            "output_kind": self.output_kind,
            "risk_level": self.risk_level,
            "supported_engines": sorted(self.supported_engines),
            "required_validations": list(self.required_validations),
            "side_effects": sorted(self.side_effects),
            "kind": self.kind,
            "covers": list(self.covers),
        }


class CapabilityRegistry:
    def __init__(self, definitions: list[CapabilityDefinition] | None = None):
        self._definitions: dict[str, CapabilityDefinition] = {}
        self._frozen = False
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: CapabilityDefinition) -> None:
        if self._frozen:
            raise RuntimeError("能力注册表已冻结")
        if definition.name in self._definitions:
            raise ValueError(f"能力重复注册: {definition.name}")
        if not definition.name or not definition.handler or not definition.validator:
            raise ValueError("能力必须具有名称、handler 和 validator")
        self._definitions[definition.name] = definition

    def freeze(self) -> "CapabilityRegistry":
        self._frozen = True
        return self

    def require(self, name: str, engine: str = "openpyxl") -> CapabilityDefinition:
        definition = self._definitions.get(name)
        if definition is None:
            raise SheetPilotError(ErrorCode.CAPABILITY_UNSUPPORTED, "能力未注册", {"handler": name})
        if engine not in definition.supported_engines:
            raise SheetPilotError(ErrorCode.CAPABILITY_UNSUPPORTED, "当前引擎不支持该能力", {"handler": name, "engine": engine})
        return definition

    def definitions(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._definitions.values())

    def public_manifest(self, engine: str = "openpyxl") -> dict[str, Any]:
        return {"schema_version": "1.0", "engine": engine, "capabilities": [d.public_dict() for d in self.definitions() if engine in d.supported_engines]}


def _required(*names: str) -> Validator:
    def validate(params: dict[str, Any]) -> dict[str, Any]:
        allowed = set(names) | {"input", "inputs", "left", "right", "on", "how", "mapping", "columns", "header_row", "header_rows", "fields", "id_fields", "value_fields", "variable_name", "value_name", "function", "field", "value", "values", "keep", "title", "sheet", "name", "visibility", "anchor", "range", "source", "target", "source_sheet", "source_range", "target_sheet", "target_range", "include_style", "include_header", "row", "column", "index", "amount", "width", "height", "format", "formula", "required_sheets", "forbidden_sheets", "enabled", "style", "target", "preset", "cell", "chart_type", "data_ref", "group_by", "metrics", "date_field", "current_period", "where", "invalid_value_policy", "keys", "as", "template", "arguments", "category_fields", "series_fields", "header", "number_format", "rules", "row_number_header", "first_data_row", "status_header", "reason_header", "valid_label", "invalid_label", "revenue_field", "cost_field", "profit_header", "margin_header", "period_header", "source_format", "invalid_period", "checks"}
        unknown = sorted(set(params) - allowed)
        missing = [name for name in names if name not in params]
        if unknown:
            raise SheetPilotError(ErrorCode.PLAN_INVALID, "能力参数包含未知字段", {"unknown": unknown})
        if missing:
            raise SheetPilotError(ErrorCode.PLAN_INVALID, "能力缺少必需参数", {"missing": missing})
        return params
    return validate


# Handler 统一签名：handler(ctx, params, results) -> Any
# ctx 为 ExecutionContext，提供 read_table/filter_rows/aggregate 等方法；
# results 为上游步骤 id → 输出的映射，供 params["input"] 引用。

def _read(ctx, params, results):
    # header_row (int, Task API path) が header_rows (list, legacy MVP path) の両方を受け付ける
    header_row = params.get("header_row") or max(params.get("header_rows", [1]))
    return ctx.read_table(params["sheet"], header_row, params["columns"])

def _aggregate(ctx, params, results):
    extra = {k: v for k, v in params.items() if k not in {"input"}}
    return ctx.aggregate(results[params["input"]], **extra)

def _filter(ctx, params, results):
    return ctx.filter_rows(results[params["input"]], params["where"], params.get("invalid_value_policy", "exclude"))

def _select(ctx, params, results):
    return ctx.select_columns(results[params["input"]], params["fields"])

def _sort(ctx, params, results):
    return ctx.sort_rows(results[params["input"]], params["keys"])

def _deduplicate(ctx, params, results):
    return ctx.deduplicate(results[params["input"]], params.get("keys"), params.get("keep", "first"))

def _fill_missing(ctx, params, results):
    return ctx.fill_missing(results[params["input"]], params.get("fields"), params.get("value", ""))

def _value_counts(ctx, params, results):
    return ctx.value_counts(results[params["input"]], params["field"], params.get("as", "数量"))

def _describe(ctx, params, results):
    return ctx.describe(results[params["input"]], params.get("fields"))

def _derive(ctx, params, results):
    return ctx.derive_column(results[params["input"]], params["as"], params["template"], params["arguments"])

def _formula(ctx, params, results):
    return ctx.add_formula_column(
        results[params["input"]], params["header"], params["template"],
        params["arguments"], params.get("number_format"),
    )

def _create_sheet(ctx, params, results):
    return ctx.create_sheet(params["sheet"])

def _write(ctx, params, results):
    return ctx.write_table(params["sheet"], params["anchor"], results[params["input"]])

def _style(ctx, params, results):
    return ctx.apply_style(results[params["input"]], params["preset"])

def _freeze(ctx, params, results):
    return ctx.freeze(params["sheet"], params["cell"])

def _chart(ctx, params, results):
    return ctx.create_chart(
        results[params["input"]], params["chart_type"], params["anchor"],
        params.get("title", ""), params.get("category_fields"), params.get("series_fields"),
    )


def definition(name, input_kind, output_kind, risk, validations, effects, validator, handler, *, kind="CAPABILITY", covers=()):
    return CapabilityDefinition(name, "1.0", input_kind, output_kind, risk, frozenset({"openpyxl"}), tuple(validations), frozenset(effects), validator, handler, kind, tuple(covers))


_CANONICAL_REQUIRED = {
    "workbook.validate_structure": (), "sheet.inspect": ("sheet",), "sheet.create": ("sheet",), "sheet.delete": ("sheet",), "sheet.rename": ("sheet","name"), "sheet.copy": ("sheet","name"), "sheet.set_visibility": ("sheet","visibility"),
    "cell.read": ("sheet","row","column"), "cell.write": ("sheet","row","column"), "cell.clear": ("sheet","row","column"), "range.read": ("sheet","range"), "range.write": ("sheet","anchor","values"), "range.write_table": ("input","sheet"), "range.append_rows": ("sheet","values"), "range.copy": ("source_sheet","source_range","target_sheet","anchor"), "range.clear": ("sheet","range"), "range.merge": ("sheet","range"), "range.unmerge": ("sheet","range"),
    "rows.insert": ("sheet","index"), "rows.delete": ("sheet","index"), "columns.insert": ("sheet","index"), "columns.delete": ("sheet","index"),
    "formula.read": ("sheet","cell"), "formula.write": ("sheet","cell","formula"), "formula.fill": ("sheet","source","target"), "formula.copy": ("sheet","source","target"),
    "style.apply": ("input","preset"), "style.copy": ("source_sheet","source_range","target_sheet","target_range"), "style.apply_table_default": ("input",), "number_format.apply": ("sheet","range","format"), "column.set_width": ("sheet","column","width"), "row.set_height": ("sheet","row","height"), "freeze_panes.set": ("sheet",), "auto_filter.set": ("sheet","range"), "protection.set": ("sheet",),
    "table.read": ("sheet","columns"), "table.select": ("input","fields"), "table.filter": ("input","where"), "table.group": ("input","fields"), "table.aggregate": ("input","metrics"), "table.sort": ("input","keys"), "table.deduplicate": ("input",), "table.fill_missing": ("input",), "table.describe": ("input",), "table.value_counts": ("input","field"), "table.count": ("input",), "table.unique": ("input","field"),
    "excel_table.create": ("sheet","name","range"), "chart.create": ("sheet","range","chart_type","anchor"), "hyperlink.create": ("sheet","cell","target"),
    "table.rename_fields": ("input","mapping"), "table.concat": ("inputs",), "table.join": ("left","right","on"), "table.pivot": ("input","index","columns","values"), "table.melt": ("input","id_fields","value_fields"),
    "formula.inspect_dependencies": ("sheet","cell"), "formula.find_errors": ("sheet",), "chart.add_series": ("sheet","chart_index","range"), "chart.set_categories": ("sheet","chart_index","range"), "chart.inspect": ("sheet","chart_index"), "validation.create": ("sheet","range","validation_type"), "conditional_format.create": ("sheet","range","operator"), "named_range.create": ("name","sheet","range"), "comment.create": ("sheet","cell","text"), "image.insert": ("sheet","path"),
}


def _canonical_definitions():
    for name in sorted(PHASE_ONE | PHASE_TWO | PHASE_THREE):
        yield definition(name, "any", "any", "write" if any(token in name for token in ("write","create","delete","rename","copy","insert","clear","set","apply")) else "read", (), (), _required(*_CANONICAL_REQUIRED.get(name, ())), atomic_handler(name))


DEFAULT_REGISTRY = CapabilityRegistry([
    *_canonical_definitions(),
    definition("read_table", "workbook", "table", "read", (), ("read_workbook",), _required("sheet"), _read),
    definition("aggregate", "table", "table", "transform", ("business_reconciliation",), (), _required("group_by", "metrics"), _aggregate),
    definition("filter_rows", "table", "table", "transform", ("business_reconciliation",), (), _required("where"), _filter),
    definition("select_columns", "table", "table", "transform", (), (), _required("fields"), _select),
    definition("sort_rows", "table", "table", "transform", (), (), _required("keys"), _sort),
    definition("deduplicate", "table", "table", "transform", (), (), _required("input"), _deduplicate),
    definition("fill_missing", "table", "table", "transform", (), (), _required("input"), _fill_missing),
    definition("value_counts", "table", "table", "transform", (), (), _required("input", "field"), _value_counts),
    definition("describe_table", "table", "table", "read", (), (), _required("input"), _describe),
    definition("derive_column", "table", "table", "transform", (), (), _required("as", "template", "arguments"), _derive),
    definition("add_formula_column", "range", "range", "write", ("formula_scan",), ("write_formulas",), _required("header", "template", "arguments"), _formula),
    definition("create_sheet", "workbook", "sheet", "write", (), ("create_sheet",), _required("sheet"), _create_sheet),
    definition("write_table", "table", "range", "write", ("declared_change_match",), ("write_values",), _required("sheet", "anchor"), _write),
    definition("apply_style_preset", "range", "range", "object_write", ("layout",), ("write_styles",), _required("preset"), _style),
    definition("freeze_header", "workbook", "layout", "object_write", ("layout",), ("freeze_panes",), _required("sheet", "cell"), _freeze),
    definition("create_chart", "range", "chart", "object_write", ("layout",), ("create_chart",), _required("chart_type", "anchor"), _chart),
    definition("build_traceable_detail", "table", "table", "transform", ("business_reconciliation",), (), _required("input"), build_traceable_detail, kind="COMPOSITE", covers=("traceability",)),
    definition("classify_invalid_rows", "table", "table", "transform", ("business_reconciliation",), (), _required("input", "rules"), classify_invalid_rows, kind="COMPOSITE", covers=("invalid_classification",)),
    definition("calculate_profitability", "table", "table", "transform", ("business_reconciliation",), (), _required("input", "revenue_field", "cost_field"), calculate_profitability, kind="COMPOSITE", covers=("profitability",)),
    definition("summarize_by_period", "table", "table", "transform", ("business_reconciliation",), (), _required("input", "date_field", "metrics"), summarize_by_period, kind="COMPOSITE", covers=("period_summary",)),
    definition("summarize_by_dimension", "table", "table", "transform", ("business_reconciliation",), (), _required("input", "group_by", "metrics"), summarize_by_dimension, kind="COMPOSITE", covers=("dimension_summary",)),
    definition("build_kpi_block", "table", "table", "transform", ("business_reconciliation",), (), _required("input", "metrics"), build_kpi_block, kind="COMPOSITE", covers=("kpi",)),
    definition("build_reconciliation_sheet", "values", "table", "transform", ("business_reconciliation",), (), _required("checks"), build_reconciliation_sheet, kind="COMPOSITE", covers=("reconciliation",)),
]).freeze()
