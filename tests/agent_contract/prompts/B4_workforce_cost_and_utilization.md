# B4：人力成本与预算使用率

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B4_workforce.xlsx`
- 工作表：`员工月度绩效`、`部门目标`
- 表头行：1

## 用户需求（Prompt）

```text
请排除离职员工，按部门汇总实发工资、员工人数、平均实际工时和加班人数，并关联部门目标计算预算使用率。预算使用率超过90%的部门标记为“重点关注”，结果按预算使用率降序写入新工作表。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B4_workforce.xlsx
输出文件：<自动生成>
```

## 验收重点

- 离职员工不进入任何指标。
- 人数和加班人数必须是过滤后的行数。
- 预算连接后才计算预算使用率。
