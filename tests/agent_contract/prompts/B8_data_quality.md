# B8：客户订单数据清洗

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B8_data_quality.xlsx`
- 工作表：`客户订单`、`字段说明`

## 用户需求（Prompt）

```text
请清洗客户订单：按客户编号去重，补齐缺失负责人为“待分配”，将订单状态为“待补”或订单金额为空的记录列入异常清单；重命名输出字段为业务人员易懂的名称，并给出字段非空数和金额分布概览。原始客户订单保持不变。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B8_data_quality.xlsx
输出文件：<自动生成>
```

## 验收重点

- 去重键为客户编号，保留第一条记录。
- 缺失负责人只填“待分配”，不能覆盖已有负责人。
- 异常记录必须保留原始订单字段。
