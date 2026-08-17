# E2：SaaS 已有工作簿增量汇总

```text
使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\08_complex_saas_renewals.xlsx
测试场景：E2
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\saas_renewal_analysis.xlsx

使用“客户月度经营”，只统计续费状态为“已续费”、回款状态为“正常”，且套餐属于“专业版”或“企业版”的记录。

按区域、行业分组，输出实收MRR合计、流失MRR合计、客户月度记录数量、客户编号非空数量和平均NPS，按实收MRR合计降序写入新工作表“区域行业续费汇总”。

保留原工作簿中的客户主数据、续费经营看板、口径说明、公式和图表，不修改输入文件。完成后根据最终 task-status 报告执行状态、Task ID 和输出文件路径。
```
