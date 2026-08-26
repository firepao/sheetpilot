import unittest

from sheetpilot.workbook.tables import TableData, concat_tables, count_values, join_tables, melt_table, pivot_table, rename_fields, unique_values


class AdvancedTableCapabilityTest(unittest.TestCase):
    def test_join_and_concat(self):
        left=TableData(["订单","客户"],[{"订单":"O1","客户":"C1"},{"订单":"O2","客户":"C2"}])
        right=TableData(["客户","等级"],[{"客户":"C1","等级":"A"}])
        joined=join_tables(left,right,["客户"],"left")
        self.assertEqual(joined.rows[1]["等级"],None)
        self.assertEqual(len(concat_tables([left,left]).rows),4)

    def test_pivot_melt_and_rename(self):
        data=TableData(["区域","月份","金额"],[{"区域":"北","月份":"一月","金额":10},{"区域":"北","月份":"二月","金额":20}])
        pivoted=pivot_table(data,["区域"],"月份","金额")
        self.assertEqual(pivoted.rows[0]["一月"],10)
        melted=melt_table(pivoted,["区域"],["一月","二月"])
        self.assertEqual(len(melted.rows),2)
        self.assertEqual(rename_fields(data,{"金额":"销售额"}).headers[-1],"销售额")

    def test_count_and_unique(self):
        data = TableData(["客户", "金额"], [{"客户": "C1", "金额": 10}, {"客户": "C1", "金额": None}, {"客户": "C2", "金额": 5}, {"客户": None, "金额": 0}])
        self.assertEqual(count_values(data), 4)
        self.assertEqual(count_values(data, "金额", "non_empty"), 3)
        self.assertEqual(unique_values(data, "客户").rows, [{"客户": "(空)"}, {"客户": "C1"}, {"客户": "C2"}])
        with self.assertRaises(ValueError): count_values(data, "缺失", "non_empty")


if __name__ == "__main__": unittest.main()
