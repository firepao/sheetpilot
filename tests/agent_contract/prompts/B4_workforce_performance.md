# B4：员工绩效与项目工时

## 输入文件

- 文件路径：`D:/bitexcel/SheetPilot/tests/agent_contract/data/B4_workforce.xlsx`
- 工作表：`员工月度绩效`
- 表头行：1

## 用户需求（Prompt）

```text
请统计绩效等级为“优秀”或“良好”的在职员工，按部门和项目编号汇总员工人数、实发工资和实际工时，并保留员工编号非空数。结果先按部门排序，再按实发工资降序输出。

输入文件：D:/bitexcel/SheetPilot/tests/agent_contract/data/B4_workforce.xlsx
输出文件：<自动生成>
```

## 验收重点

- “优秀”或“良好”是 OR 条件，“在职”是必选条件。
- 员工编号非空数不能直接等于记录数。
