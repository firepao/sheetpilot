# N1：多门店零售复杂经营汇总

```text
使用 $sheetpilot-excel-agent 处理：

输入：tests/agent_contract/data/07_complex_retail_operations.xlsx
测试场景：N1
输出：tests\agent_contract\results\<AUTO-RESULT-DIR>\retail_regional_category_summary.xlsx

使用“门店订单明细”，只统计审核状态为“通过”且是否取消为“否”的订单。

按区域、产品品类分组，输出净销售收入、交易数量（过滤后的记录行数）、客户编号非空数量、平均订单金额和毛利合计，按净销售收入降序写入新工作表“区域品类经营汇总”。

保留原工作簿中的所有工作表、公式和图表，不修改输入文件。完成后根据最终 task-status 报告执行状态、Task ID 和输出文件路径。
```
