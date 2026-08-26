# B5：营销月度投放透视

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B5_marketing_funnel.xlsx`
- 工作表：`投放明细`
- 表头行：1

## 用户需求（Prompt）

```text
请将投放明细按投放月份和渠道制作透视表，输出每月投放金额、点击量和归因销售额。结果写入新工作表，冻结表头并设置金额格式；原始投放明细保持不变。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B5_marketing_funnel.xlsx
输出文件：<自动生成>
```

## 验收重点

- 月份从投放日期正确提取。
- 透视结果按月份和渠道可核对到原始明细。
