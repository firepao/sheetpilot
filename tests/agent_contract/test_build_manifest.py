from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.agent_contract.evaluation.build_manifest import build


class BuildManifestTest(unittest.TestCase):
    def test_builds_all_exact_runs_and_reports_missing_scenarios(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); scenarios = root / "scenarios"; evidence = root / "evidence"; scenarios.mkdir(); evidence.mkdir()
            for key in ("S2_full", "M3_full"):
                (scenarios / f"{key}.json").write_text(json.dumps({"scenario_key": key, "status": "active"}), encoding="utf-8")
            run = evidence / "S2_full" / "run-a"; run.mkdir(parents=True)
            (run / "replay.raw.json").write_text("{}", encoding="utf-8")
            manifest = build(scenarios, evidence, root / "manifest.json")
            self.assertEqual(manifest["build"]["run_count"], 1)
            self.assertIn("missing_evidence_directory:M3_full", manifest["build"]["errors"])
            self.assertEqual(manifest["runs"][0]["scenario_key"], "S2_full")
            self.assertEqual(manifest["runs"][0]["run_id"], "run-a")
            self.assertTrue(Path(manifest["runs"][0]["scenario_file"]).is_absolute())

    def test_does_not_pick_non_directory_or_latest_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); scenarios = root / "scenarios"; evidence = root / "evidence"; scenarios.mkdir(); (evidence / "S2").mkdir(parents=True)
            (scenarios / "S2.json").write_text(json.dumps({"scenario_key": "S2", "status": "active"}), encoding="utf-8")
            (evidence / "S2" / "latest-replay.json").write_text("{}", encoding="utf-8")
            manifest = build(scenarios, evidence, root / "manifest.json")
            self.assertEqual(manifest["runs"], [])
            self.assertIn("missing_run_directory:S2", manifest["build"]["errors"])
