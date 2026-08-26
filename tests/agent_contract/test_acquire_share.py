from __future__ import annotations

import unittest

from tests.agent_contract.evaluation.acquire_share import _validate_share_payload


class ShareAcquisitionTest(unittest.TestCase):
    def test_accepts_valid_snapshot_payload(self):
        payload = {"code": "200", "data": {"snapshot_data": '{"messages":[{"id":"m1"}]}'}}
        self.assertEqual(_validate_share_payload(payload), (True, "ok"))

    def test_rejects_html_and_unauthorized_payloads(self):
        self.assertEqual(_validate_share_payload("<html>login</html>"), (False, "response_is_not_json_object"))
        self.assertEqual(_validate_share_payload({"code": "401", "data": {}}), (False, "share_api_status:401"))

    def test_rejects_incomplete_snapshot(self):
        payload = {"code": "200", "data": {"snapshot_data": "{}"}}
        self.assertEqual(_validate_share_payload(payload), (False, "snapshot_is_incomplete"))
