from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReplayParserTimezoneTest(unittest.TestCase):
    def test_parser_runs_with_normal_replay_fixture(self):
        raw = {"messages": [{"role": "user", "timestamp": 1700000000000, "content": "test"}], "steps": []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "replay.json"; target = root / "essential.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            parser = Path(__file__).parents[1] / ".." / "skills" / "sheetpilot-run-review" / "scripts" / "parse_agent_replay.py"
            result = subprocess.run([sys.executable, str(parser.resolve()), str(source), "--format", "essential", "-o", str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(target.is_file())
