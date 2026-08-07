from __future__ import annotations

from ..errors import ErrorCode, SheetPilotError
from ..models import HighLevelPlan, HighLevelStep, SemanticTask


class OperatingSummaryRecipe:
    recipe_id = "operating_summary"
    covers = frozenset({"dimension_summary", "business_reconciliation", "chart"})

    def match(self, task: SemanticTask) -> bool:
        dimensions = task.requested_output.get("dimensions", [])
        return "date" in task.concepts and "revenue" in task.concepts and 1 <= len(dimensions) <= 2

    def compile(self, task: SemanticTask) -> HighLevelPlan:
        if not self.match(task):
            raise SheetPilotError(ErrorCode.CAPABILITY_UNSUPPORTED, "经营汇总配方需要日期、金额和一至两个分类维度")
        dimensions = task.requested_output["dimensions"]
        mapped_dimensions = [task.concepts[name].field for name in dimensions]
        date_field = task.concepts["date"].field
        revenue_field = task.concepts["revenue"].field
        target = task.requested_output.get("target_sheet", "经营汇总")
        periods = task.business_definition
        filters = list(task.requested_output.get("filters", []))
        read_fields = [date_field, *mapped_dimensions, revenue_field]
        for condition in filters:
            read_fields.append(condition["field"])
        read_fields = list(dict.fromkeys(read_fields))
        steps = [
            HighLevelStep("read_source", "read_table", {"sheet": task.source["sheet"], "header_rows": task.source.get("header_rows", [1]), "fields": read_fields}),
        ]
        where = {"all": []}
        if periods.get("current_period"):
            where["all"].append({"field": date_field, "op": "between", "value": periods["current_period"], "value_type": "date"})
        where["all"].extend(filters)
        if where["all"]:
            steps.append(HighLevelStep("filter_source", "filter_rows", {"input": "read_source", "where": where, "invalid_value_policy": "exclude"}))
            aggregate_input = "filter_source"
        else:
            aggregate_input = "read_source"
        steps.append(HighLevelStep("aggregate_summary", "aggregate", {"input": aggregate_input, "group_by": mapped_dimensions, "metrics": [{"field": revenue_field, "function": "sum", "as": "销售收入"}]}))
        steps.append(HighLevelStep("sort_summary", "sort_rows", {"input": "aggregate_summary", "keys": [{"field": "销售收入", "direction": "desc"}]}))
        steps.extend([
            HighLevelStep("create_summary", "create_sheet", {"sheet": target}),
            HighLevelStep("write_summary", "write_table", {"input": "sort_summary", "sheet": target, "anchor": "A3"}),
            HighLevelStep("style_summary", "apply_style_preset", {"input": "write_summary", "preset": "business_table"}),
            HighLevelStep("freeze_summary", "freeze_header", {"sheet": target, "cell": "A4"}),
        ])
        if task.requested_output.get("chart"):
            steps.append(HighLevelStep("chart_summary", "create_chart", {"input": "write_summary", "sheet": target, "chart_type": task.requested_output["chart"], "anchor": "F3", "title": "经营汇总", "category_fields": mapped_dimensions, "series_fields": ["销售收入"]}))
        assertion = {"type": "aggregate_reconciliation", "source_step": "read_source", "result_step": "write_summary", "metric": revenue_field, "output_metric": "销售收入", "tolerance": 1e-6}
        return HighLevelPlan("1.0", task.task_id, "recipe_plus_operations", self.recipe_id, steps, [assertion])
