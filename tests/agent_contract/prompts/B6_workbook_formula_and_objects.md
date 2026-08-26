# B6：运营看板公式与对象保真

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B6_workbook_objects.xlsx`
- 工作表：`运营看板`
- 表头行：1

## 用户需求（Prompt）

```text
请检查运营看板中的公式依赖和公式错误，保留现有公式；为销售额和订单数创建图表，使用月份作为分类轴；为“可发布”单元格创建命名区域并添加批注。完成后输出对象检查结果，不要破坏原工作表内容。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B6_workbook_objects.xlsx
输出文件：<自动生成>
```

## 验收重点

- 公式依赖和错误检查有明确结果。
- 图表系列和分类轴均来自原看板数据。
- 原有公式、单元格值和工作表结构保留。
