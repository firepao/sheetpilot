# B9：月度经营简报发布

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B9_report_publication.xlsx`
- 工作表：`经营数据`、`参数`

## 用户需求（Prompt）

```text
请发布月度经营简报：检查并填充利润公式到全部月份，创建包含收入、成本和利润的柱状图，在结果表写入报告标题；设置金额数字格式、冻结首行、调整列宽，并保留原始工作表。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B9_report_publication.xlsx
输出文件：<自动生成>
```

## 验收重点

- 每个月份的利润公式均存在且引用本行收入和成本。
- 图表包含收入、成本和利润系列。
- 原始经营数据表保留。
