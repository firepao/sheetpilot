from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.agent_contract.evaluation.benchmark_batch import benchmark


class BenchmarkBatchTest(unittest.TestCase):
    def test_records_cold_warm_latency_and_score_equivalence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); runs = []
            for index in range(5):
                bundle = {"scenario": {"id": f"S{index}", "expected_outcome": "success"}, "commands": ["task-run"], "task_request": {"filters": [], "dimensions": [], "metrics": [], "output": {"sort": []}, "acceptance": {"required_filters": [], "required_dimensions": [], "required_metrics": [], "required_sort": []}}, "task_status": {"state": "RUNTIME_PASS", "artifact_integrity": "MATCHED", "delivery_valid": True}, "oracle_result": {"passed": True, "input_unchanged": True}, "final_report": {"runtime_status": "RUNTIME_PASS"}}
                path = root / f"b{index}.json"; path.write_text(json.dumps(bundle), encoding="utf-8")
                runs.append({"scenario_key": f"S{index}", "run_id": "r1", "bundle_file": str(path)})
            manifest = root / "manifest.json"; manifest.write_text(json.dumps({"schema_version": "1.0", "runs": runs}), encoding="utf-8")
            report = benchmark(manifest, root / "benchmark.json", sizes=(1, 5, 31))
            self.assertEqual([item["run_count"] for item in report["samples"]], [1, 5, 5])
            self.assertTrue(all(item["scores_identical"] for item in report["samples"]))
            self.assertTrue((root / "benchmark.json").is_file())
