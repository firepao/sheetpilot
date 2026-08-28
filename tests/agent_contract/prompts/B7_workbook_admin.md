# B7：月度报表工作簿整理

## 输入文件

- 文件路径：`tests/agent_contract/data/B7_workbook_admin.xlsx`
- 工作表：`月度报表`、`模板`

## 用户需求（Prompt）

```text
请把月度报表复制为“管理层报表”，删除空白模板工作表，并在新报表中冻结表头、开启自动筛选、调整列宽、保护工作表；不要修改原始月度报表。

输入文件：tests/agent_contract/data/B7_workbook_admin.xlsx
输出文件：<自动生成>
```

## 验收重点

- 原始月度报表仍存在且内容不变。
- 新工作表名称、筛选、冻结、列宽和保护状态正确。
