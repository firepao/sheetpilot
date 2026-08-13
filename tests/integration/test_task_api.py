from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from sheetpilot.task_api import TaskRuntime
from sheetpilot.task_api.compiler import compile_plan
from sheetpilot.task_api.contract import MINIMAL_EXAMPLE, acceptance_snapshot, stable_hash


class TaskApiTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "orders.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "清洗明细"
        sheet.append(["城市", "订单号", "销售额", "是否退货", "清洗状态"])
        sheet.append(["北京", "A", 10, "否", "有效"])
        sheet.append(["上海", "B", 30, "否", "有效"])
        sheet.append(["北京", "C", 90, "是", "有效"])
        workbook.save(self.source); workbook.close()
        self.runtime = TaskRuntime(self.root / "state")

    def tearDown(self):
        self.temporary.cleanup()

    def request(self) -> dict:
        value = copy.deepcopy(MINIMAL_EXAMPLE)
        value["input_file"] = str(self.source)
        value["output_file"] = str(self.root / "result.xlsx")
        return value

    def test_task_types_is_the_complete_public_contract(self):
        manifest = self.runtime.task_types(); definition = manifest["task_types"][0]
        self.assertEqual(definition["name"], "summarize_table")
        self.assertIn("minimal_example", definition)
        self.assertEqual(definition["supported_features"]["metric_functions"], ["sum", "average", "count.rows", "count.non_empty"])

    def test_contract_failure_does_not_create_task(self):
        request = self.request(); request["metrics"][1]["mode"] = "row"
        result = self.runtime.run(request)
        self.assertEqual(result["status"], "REQUEST_INVALID")
        self.assertIsNone(result["task_id"])
        self.assertEqual(result["error"]["diagnostics"][0]["path"], "/metrics/1/mode")
        tasks = self.root / "state" / "tasks"
        self.assertTrue(not tasks.exists() or not list(tasks.iterdir()))

    def test_runtime_manages_attempt_and_publishes(self):
        request = self.request(); result = self.runtime.run(request)
        self.assertEqual(result["status"], "RUNTIME_PASS")
        self.assertTrue(result["delivery_valid"])
        self.assertNotIn("run_dir", result)
        task_dir = self.root / "state" / "tasks" / result["task_id"]
        self.assertTrue((task_dir / "attempts" / "attempt-001" / "internal-plan.json").is_file())
        workbook = load_workbook(request["output_file"], data_only=True)
        rows = list(workbook["城市经营汇总"].iter_rows(min_row=2, values_only=True)); workbook.close()
        self.assertEqual(rows, [("上海", 30, 1, 30), ("北京", 10, 1, 10)])
        repeated = self.runtime.run(request)
        self.assertEqual(repeated["task_id"], result["task_id"])
        self.assertEqual(len(list((task_dir / "attempts").iterdir())), 1)

    def test_ambiguous_exact_headers_return_needs_binding_without_attempt(self):
        workbook = load_workbook(self.source); sheet = workbook["清洗明细"]
        sheet.insert_cols(4); sheet["D1"] = "销售额"; sheet["D2"] = 10; sheet["D3"] = 30; sheet["D4"] = 90
        workbook.save(self.source); workbook.close()
        result = self.runtime.run(self.request())
        self.assertEqual(result["status"], "NEEDS_BINDING")
        sales = next(item for item in result["binding_slots"] if item["logical_field"] == "销售额")
        self.assertEqual(sales["status"], "AMBIGUOUS")
        task_dir = self.root / "state" / "tasks" / result["task_id"]
        self.assertFalse((task_dir / "attempts").exists())

    def test_compiler_is_byte_deterministic_and_hides_display_names(self):
        request = self.request(); binding = self.runtime._bind(request, "input-hash")
        snapshot = {"source": binding["source"], "slots": binding["slots"]}
        acceptance_hash = stable_hash(acceptance_snapshot(request))
        first, first_hash = compile_plan("task-abc", 1, request, acceptance_hash, snapshot, "input-hash")
        second, second_hash = compile_plan("task-abc", 1, request, acceptance_hash, snapshot, "input-hash")
        self.assertEqual(json.dumps(first, ensure_ascii=False, sort_keys=True), json.dumps(second, ensure_ascii=False, sort_keys=True))
        self.assertEqual(first_hash, second_hash)
        summarize = next(step for step in first["steps"] if step["id"] == "summarize")
        self.assertTrue(all(field.startswith("__sp_") for field in summarize["group_by"]))
        self.assertNotIn("销售收入", json.dumps(summarize, ensure_ascii=False))

    def test_status_detects_modified_publication(self):
        result = self.runtime.run(self.request())
        workbook = load_workbook(self.root / "result.xlsx"); workbook["城市经营汇总"]["B2"] = 999; workbook.save(self.root / "result.xlsx"); workbook.close()
        status = self.runtime.status(result["task_id"])
        self.assertEqual(status["artifact_integrity"], "MODIFIED")
        self.assertFalse(status["delivery_valid"])

    def test_existing_target_sheet_fails_without_publishing(self):
        request=self.request(); request["output"]["sheet"]="清洗明细"
        request["output_file"]=str(self.root/"conflict.xlsx")
        result=self.runtime.run(request)
        self.assertEqual(result["status"],"EXECUTION_FAILED")
        self.assertEqual(result["error"]["code"],"OUTPUT_CONFLICT")
        self.assertFalse(Path(request["output_file"]).exists())

    def test_unsized_worksheet_is_bound_and_executed(self):
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(Path(__file__).resolve().parents[1] / "agent_contract" / "data" / "01_simple_department_sales.xlsx")
        request["output_file"] = str(self.root / "unsized-result.xlsx")
        request["source"] = {"sheet": "销售明细", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "department", "field": "部门", "output_name": "部门"}]
        request["metrics"] = [{"id": "total_sales", "function": "sum", "field": "销售额", "output_name": "销售总额"}]
        request["output"] = {"sheet": "部门销售汇总", "anchor": "A1", "sort": [{"by": "total_sales", "direction": "desc"}]}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["department"]
        request["acceptance"]["required_metrics"] = ["total_sales"]
        request["acceptance"]["required_sort"] = [{"by": "total_sales", "direction": "desc"}]
        result = self.runtime.run(request)
        self.assertEqual(result["status"], "RUNTIME_PASS")


if __name__ == "__main__": unittest.main()
