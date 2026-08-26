import unittest

from sheetpilot.atomic.catalog import ALL_OPERATIONS, PHASE_ONE, PHASE_TWO, PHASE_THREE, migration_inventory


class CapabilityCatalogTest(unittest.TestCase):
    def test_design_catalog_has_67_unique_operations(self):
        self.assertEqual(len(ALL_OPERATIONS), 67)
        self.assertEqual(len(set(ALL_OPERATIONS)), 67)
        self.assertEqual(len(PHASE_ONE), 52)
        self.assertEqual(len(PHASE_TWO), 5)
        self.assertEqual(len(PHASE_THREE), 10)

    def test_inventory_is_machine_auditable(self):
        result = migration_inventory({"table.read", "table.filter"})
        self.assertEqual(result["defined_total"], 67)
        self.assertEqual(result["phase_1"]["implemented"], 2)
        self.assertIn("table.join", result["phase_2"]["missing"])


if __name__ == "__main__":
    unittest.main()
