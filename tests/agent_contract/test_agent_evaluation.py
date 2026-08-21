from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook

from sheetpilot.task_api import TaskRuntime
from sheetpilot.task_api.contract import MINIMAL_EXAMPLE
from tests.agent_contract.evaluation.evaluator import evaluate_run, inspect_commands
from tests.agent_contract.evaluation.cli import archive_directory_name
from tests.agent_contract.evaluation.oracle import evaluate_summarize_table, sha256_file


class AgentEvaluationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.source = self.root / "orders.xlsx"; workbook = Workbook(); sheet = workbook.active; sheet.title = "清洗明细"
        sheet.append(["城市", "订单号", "销售额", "是否退货", "清洗状态", "客户编号"])
        sheet.append(["北京", "A", 10, "否", "有效", "C001"]); sheet.append(["上海", "B", 30, "否", "有效", "C002"]); sheet.append(["北京", "C", 90, "是", "有效", None])
        workbook.save(self.source); workbook.close()
        self.request = copy.deepcopy(MINIMAL_EXAMPLE); self.request["input_file"] = str(self.source); self.request["output_file"] = str(self.root / "result.xlsx")

    def tearDown(self): self.temporary.cleanup()

    def test_runtime_output_passes_independent_oracle_and_score(self):
        before = sha256_file(self.source); runtime = TaskRuntime(self.root / "state"); run = runtime.run(self.request); status = runtime.status(run["task_id"])
        oracle = evaluate_summarize_table(self.request, input_sha256_before=before)
        bundle = {
            "scenario": {"id": "smoke", "expected_outcome": "success", "semantic_review_required": True},
            "task_request": self.request, "task_status": status, "oracle_result": oracle,
            "semantic_review": {"status": "accepted", "rationale": "matches prompt"},
            "commands": ["python wrapper task-types", "python wrapper task-run --request request.json", f"python wrapper task-status --task-id {run['task_id']}"],
            "final_report": {"task_id": run["task_id"], "runtime_status": "RUNTIME_PASS", "artifact_integrity": "MATCHED", "delivery_valid": True, "semantic_assessment": {"status": "accepted"}, "output_file": self.request["output_file"]},
        }
        result = evaluate_run(bundle)
        self.assertTrue(oracle["passed"]); self.assertEqual(result["task_result"], "PASS"); self.assertEqual(result["quality_score"], 100)

    def test_critical_violation_forces_fail_and_null_quality_score(self):
        bundle = {"scenario": {"id": "bad", "expected_outcome": "success"}, "task_request": self.request,
                  "task_status": {"state": "RUNTIME_PASS", "artifact_integrity": "MATCHED", "delivery_valid": True},
                  "oracle_result": {"passed": True, "input_unchanged": True}, "semantic_review": {"status": "not_assessed"},
                  "commands": ["python -c import openpyxl; openpyxl.load_workbook('x.xlsx')"]}
        result = evaluate_run(bundle)
        self.assertEqual(result["task_result"], "FAIL"); self.assertIsNone(result["quality_score"])
        self.assertEqual(result["critical_violations"]["manual_workbook_writes"], 1)

    def test_acceptance_reduction_is_detected(self):
        request = copy.deepcopy(self.request); request["acceptance"]["required_metrics"].pop()
        result = evaluate_run({"scenario": {"id": "reduced"}, "task_request": request, "commands": ["task-types"]})
        self.assertEqual(result["critical_violations"]["acceptance_reductions"], 1)
        self.assertEqual(result["task_result"], "FAIL")

    def test_missing_trace_fails_evidence_gate(self):
        result = evaluate_run({"scenario": {"id": "missing"}, "task_request": self.request})
        self.assertFalse(result["gates"]["evidence_complete"])
        self.assertEqual(result["task_result"], "FAIL")

    def test_replay_wall_clock_timing_takes_precedence_over_command_sum(self):
        bundle = {
            "scenario": {"id": "timing", "expected_outcome": "correct_stop", "allowed_states": ["REQUEST_INVALID"]},
            "task_status": {"state": "REQUEST_INVALID", "delivery_valid": False},
            "commands": [{"command": "task-types", "elapsed_ms": 800}, {"command": "task-run", "elapsed_ms": 1_200}],
            "final_report": {"runtime_status": "REQUEST_INVALID"},
            "replay_stats": {"source": "replay_timestamps", "complete": True, "total_duration_ms": 10_000, "step_count": 2,
                             "tool_duration_ms": 2_000, "agent_response_duration_ms": 3_000, "step_time": {"avg_ms": 1_000, "p95_ms": 1_200}},
        }
        metrics = evaluate_run(bundle)["metrics"]
        self.assertEqual(metrics["elapsed_ms"], 10_000)
        self.assertEqual(metrics["command_elapsed_ms"], 2_000)
        self.assertEqual(metrics["timing_source"], "replay_timestamps")
        self.assertTrue(metrics["timing_complete"])

    def test_running_packaged_wrapper_is_not_source_access(self):
        audit = inspect_commands([
            r'python "D:\bitexcel\SheetPilot\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-types',
            r'python "D:\bitexcel\SheetPilot\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-run --request request.json',
            r'python "D:\bitexcel\SheetPilot\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-status --task-id task-1',
        ])
        self.assertEqual(audit["source_access_attempts"], 0)
        self.assertEqual(audit["allowed_cli_calls"], 3)

    def test_reading_or_searching_wrapper_remains_source_access(self):
        for command in (
            r'Get-Content D:\skill\scripts\sheetpilot_cli.py',
            r'读取 sheetpilot_cli.py 源码',
            r'rg "task-types" D:\skill\scripts\sheetpilot_cli.py',
        ):
            with self.subTest(command=command):
                self.assertEqual(inspect_commands([command])["source_access_attempts"], 1)

    def test_creating_user_delivery_directory_is_not_runtime_directory_management(self):
        audit = inspect_commands([r'New-Item -ItemType Directory D:\results\S1__20260812T103015+0800__run-a3f91c'])
        self.assertEqual(audit["run_dir_operations"], 0)

    def test_managing_runtime_attempt_directory_remains_violation(self):
        audit = inspect_commands([r'New-Item -ItemType Directory D:\state\tasks\task-1\attempt-001'])
        self.assertEqual(audit["run_dir_operations"], 1)

    def test_archive_name_identifies_scenario_version_time_and_run(self):
        bundle = {"scenario": {"id": "S1"}, "skill_version": "v4/task api", "tested_at": "2026-08-11T08:31:10Z"}
        self.assertEqual(
            archive_directory_name(bundle, "run 01"),
            "S1__v4-task-api__20260811T163110+0800__run-01",
        )

    def test_archive_name_has_deterministic_fallbacks(self):
        name = archive_directory_name({}, "", now=datetime(2026, 8, 12, 9, 5, 6, tzinfo=timezone.utc))
        self.assertEqual(name, "unknown__unversioned__20260812T170506+0800__run-01")


if __name__ == "__main__": unittest.main()
