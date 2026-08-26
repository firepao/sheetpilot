# B1：零售销售透视与明细变换

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B1_retail_operations.xlsx`
- 工作表：`订单明细`
- 表头行：1

## 用户需求（Prompt）

```text
请将已完成且未退货的订单按区域和下单月份制作销售额透视表，并把订单明细转换成长表供核查。结果写入新的工作表，原始数据保持不变；透视表需要有清晰表头并冻结首行。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B1_retail_operations.xlsx
输出文件：<自动生成>
```

## 验收重点

- 只使用已完成且未退货订单。
- 透视维度为区域和月份，值为销售额。
- 长表保留订单号、区域、月份和销售额，不覆盖原表。
