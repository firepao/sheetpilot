import unittest

from sheetpilot.workbook.tables import TableData, deduplicate, describe, fill_missing, value_counts


class TableCapabilityTest(unittest.TestCase):
    def setUp(self):
        self.data = TableData(["客户", "金额", "状态"], [
            {"客户": "A", "金额": 10, "状态": "有效"},
            {"客户": "A", "金额": 10, "状态": "有效"},
            {"客户": "B", "金额": None, "状态": ""},
        ])

    def test_deduplicate_preserves_first_order(self):
        result = deduplicate(self.data, ["客户"])
        self.assertEqual([row["客户"] for row in result.rows], ["A", "B"])

    def test_fill_missing_only_selected_fields(self):
        result = fill_missing(self.data, ["金额", "状态"], 0)
        self.assertEqual(result.rows[-1]["金额"], 0)
        self.assertEqual(result.rows[-1]["状态"], 0)
        self.assertEqual(result.rows[0]["状态"], "有效")

    def test_value_counts_and_describe(self):
        counts = value_counts(self.data, "状态")
        self.assertEqual(counts.rows, [{"状态": "(空)", "数量": 1}, {"状态": "有效", "数量": 2}])
        summary = describe(self.data, ["金额"])
        self.assertEqual(summary.rows[0]["非空数"], 2)
        self.assertEqual(summary.rows[0]["数值和"], 20)


if __name__ == "__main__":
    unittest.main()
