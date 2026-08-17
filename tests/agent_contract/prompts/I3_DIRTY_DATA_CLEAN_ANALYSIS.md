# I3：物流脏数据清洗口径分析

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\09_complex_dirty_logistics.xlsx
测试场景：I3
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\logistics_clean_operations.xlsx

使用“物流订单流水”，只统计清洗状态为“有效”、审核状态为“通过”且是否取消为“否”的记录。

按运营区域、渠道分组，输出销售收入、毛利合计、运单数量（过滤后的记录行数）、客户编号非空数量和平均实际时效，按销售收入降序写入新工作表“清洗口径经营汇总”。

保留原始物流订单、异常规则、物流运营看板、历史月度基线、公式和图表，不修改输入文件，也不要使用总行数替代客户编号非空数量。完成后根据最终 task-status 报告执行状态、Task ID 和输出文件路径。
```
