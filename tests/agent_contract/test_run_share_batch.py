from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.agent_contract.evaluation.run_share_batch import _parse_links


class ShareBatchTest(unittest.TestCase):
    def test_parses_key_url_and_optional_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "links.txt"
            path.write_text("# comment\nS2_single_dim_metric\thttps://example.com/a\nM3_inventory_turnover\trun-7\thttps://example.com/b\n", encoding="utf-8")
            entries = _parse_links(path)
            self.assertEqual(entries[0]["run_id"], "run-002")
            self.assertEqual(entries[1]["run_id"], "run-7")

    def test_rejects_url_only_because_scenario_key_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "links.txt"; path.write_text("https://example.com/a\n", encoding="utf-8")
            with self.assertRaises(ValueError): _parse_links(path)
