from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.agent_contract.validate_scenarios import validate


ROOT = Path(__file__).parent
SCENARIOS = ROOT / "scenarios"


class ScenarioRegistryTest(unittest.TestCase):
    def test_registry_status_matches_runnable_evidence(self):
        results = validate(ROOT)
        self.assertEqual(len(results), 26)
        self.assertTrue(all(item["valid"] for item in results), results)
        self.assertEqual(sum(item["status"] == "active" for item in results), 26)

    def test_scenario_keys_are_unique_and_match_file_names(self):
        keys = []
        for path in SCENARIOS.glob("*.json"):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(scenario["scenario_key"], path.stem)
            self.assertEqual(scenario["id"], path.stem)
            keys.append(scenario["scenario_key"])
        self.assertEqual(len(keys), len(set(keys)))

    def test_data_files_are_names_relative_to_the_data_directory(self):
        for path in SCENARIOS.glob("*.json"):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            data_file = scenario["data_file"]
            self.assertEqual(data_file, Path(data_file).name, path.name)

    def test_active_prompts_use_full_scenario_key(self):
        for path in SCENARIOS.glob("*.json"):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            if scenario["status"] != "active" or "测试场景：" not in scenario["user_prompt"]:
                continue
            self.assertIn(f"测试场景：{scenario['scenario_key']}", scenario["user_prompt"])

    def test_default_execution_manifest_is_a_valid_subset(self):
        manifest = json.loads((ROOT / "default_execution_manifest.json").read_text(encoding="utf-8"))
        keys = manifest["scenario_keys"]
        registered = {path.stem for path in SCENARIOS.glob("*.json")}
        self.assertEqual(len(keys), 26)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(set(keys) <= registered)


if __name__ == "__main__":
    unittest.main()
