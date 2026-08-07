---
name: sheetpilot-excel-agent
description: Use SheetPilot to inspect Excel workbooks and execute auditable table transformations, summaries, and workbook writes through the lightweight Atom/Molecule runtime. Use for .xlsx/.xlsm tasks that require registered capabilities, controlled dynamic TableData transforms, input protection, execution evidence, and independent validation before publication.
---

# SheetPilot Excel Agent

把 SheetPilot 当作唯一 Excel 执行边界。不要直接用工作簿库修改文件，不要覆盖输入文件，不要调用旧 Planner、Recipe、Compiler 或自建旁路脚本。

## 执行流程

1. 为每次任务创建全新的空运行目录。
2. 检查输入事实并查询当前能力契约：

```powershell
python "$SKILL_DIR/scripts/sheetpilot_cli.py" inspect --input <input.xlsx> --run-dir <inspect-dir>
python "$SKILL_DIR/scripts/sheetpilot_cli.py" mvp-capabilities
```

3. 仅依据 Manifest 中的参数、类型和支持函数构造轻量计划。优先使用 Molecule；只有 Molecule 无法表达时才组合 Atom。
4. 执行计划。此命令只生成待验证文件和 Runtime 证据，不发布结果：

```powershell
python "$SKILL_DIR/scripts/sheetpilot_cli.py" mvp-run --input <input.xlsx> --output <output.xlsx> --plan <plan.json> --run-dir <empty-run-dir>
```

5. 独立验证并发布：

```powershell
python "$SKILL_DIR/scripts/sheetpilot_cli.py" mvp-validate --run-dir <run-dir>
```

只引用 `execution.json`、`evidence.json` 和 `result.json` 报告实际执行能力与结果。验证失败不得交付。

## 路径选择

- 使用 Atom 完成单个确定操作。
- 使用 Molecule 完成通用组合；`summarize_by_dimension` 可展开为过滤、聚合和排序。
- 仅当注册能力无法表达纯内存表变换时，添加 `dynamic_transform` 步骤并传入 `--dynamic-script`。

动态脚本必须只定义 `transform(table, params)`，输入输出均为 `TableData` 序列化对象。禁止文件、网络、子进程、环境变量和工作簿库；动态结果必须由 `write_table` 等注册 Atom 落盘。

## 计划约束

计划根节点必须包含 `schema_version`、`input_file`、`output_file`、`steps` 和 `requirements`。为交付结果至少声明必需 Sheet 与列；涉及汇总和排序时，添加可独立复算的 `aggregate_reconciliation` 与 `sort_order` 检查。未知参数或未知聚合函数必须视为 `PLAN_INVALID`，不得猜测或降级。
