from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sheetpilot.capabilities import DEFAULT_REGISTRY
from sheetpilot.errors import ErrorCode, SheetPilotError
from sheetpilot.models import Requirement
from sheetpilot.planning.hybrid import HybridPlanner
from sheetpilot.runtime import TransformManifest, TransformRunner, analyze_transform
from sheetpilot.models import ExecutionStep
from sheetpilot.executor.dispatcher import dispatch
from sheetpilot.workbook.tables import TableData


class HybridMvpTest(unittest.TestCase):
    def test_composite_handlers_are_executable_from_single_registry(self):
        data = TableData(["收入", "成本"], [{"收入": 100, "成本": 60}, {"收入": 0, "成本": 5}])
        definition = DEFAULT_REGISTRY.require("calculate_profitability")
        result = definition.handler(None, {"input": "source", "revenue_field": "收入", "cost_field": "成本"}, {"source": data})
        self.assertEqual(result.rows[0]["利润"], 40)
        self.assertEqual(result.rows[0]["利润率"], 0.4)
        self.assertIsNone(result.rows[1]["利润率"])

    def test_hybrid_planner_uses_declared_coverage(self):
        planner = HybridPlanner()
        task = type("Task", (), {})()
        task.requested_output = {}
        task.concepts = {}
        decision = planner.choose(task, [Requirement("profitability", "计算利润"), Requirement("kpi", "生成 KPI")])
        self.assertEqual(decision.strategy, "COMPOSED")
        self.assertEqual(set(decision.components), {"calculate_profitability", "build_kpi_block"})
        self.assertTrue(decision.executable)

    def test_recipe_does_not_claim_undeclared_requirement(self):
        planner = HybridPlanner()
        task = type("Task", (), {})()
        task.requested_output = {"dimensions": ["region"]}
        task.concepts = {"date": object(), "revenue": object()}
        decision = planner.choose(task, [Requirement("traceability", "保留原始行")])
        self.assertEqual(decision.strategy, "COMPOSED")
        self.assertEqual(decision.components, ["build_traceable_detail"])

    def test_transform_runs_in_separate_process(self):
        source = """def transform(table, params):
    rows = []
    for row in table[\"rows\"]:
        rows.append({**row, \"利润\": row[\"收入\"] - row[\"成本\"]})
    return {\"headers\": table[\"headers\"] + [\"利润\"], \"rows\": rows}
"""
        with tempfile.TemporaryDirectory() as temporary:
            result = TransformRunner().run(source, TableData(["收入", "成本"], [{"收入": 10, "成本": 4}]), {}, TransformManifest("profit"), Path(temporary))
            self.assertEqual(result.rows[0]["利润"], 6)
            self.assertTrue((Path(temporary) / "script" / "static_analysis.json").exists())

    def test_dispatcher_executes_transform_step(self):
        source = """def transform(table, params):
    return {\"headers\": table[\"headers\"], \"rows\": table[\"rows\"]}
"""
        with tempfile.TemporaryDirectory() as temporary:
            context = type("Context", (), {"run_dir": Path(temporary)})()
            step = ExecutionStep("custom", "dynamic_transform", ["source"], {"input": "source", "source": source}, kind="TRANSFORM")
            results = {"source": TableData(["值"], [{"值": 1}])}
            dispatch(context, step, results)
            self.assertEqual(results["custom"].rows, [{"值": 1}])

    def test_transform_rejects_file_access(self):
        source = """def transform(table, params):
    return open(params[\"path\"]).read()
"""
        with self.assertRaises(SheetPilotError) as caught:
            analyze_transform(source)
        self.assertEqual(caught.exception.code, ErrorCode.DYNAMIC_TRANSFORM_REJECTED)

    def test_transform_rejects_top_level_side_effect(self):
        source = """print(\"unexpected\")
def transform(table, params):
    return table
"""
        with self.assertRaises(SheetPilotError):
            analyze_transform(source)


if __name__ == "__main__":
    unittest.main()
