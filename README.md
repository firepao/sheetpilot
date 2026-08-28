# SheetPilot

SheetPilot 是面向 Agent 的确定性 Excel 执行 Runtime。当前公开产品接口是业务级 Task API；Agent 不构造内部计划、不管理运行目录，也不直接修改工作簿。

## 当前接口

```powershell
sheetpilot-agent task-types --input <input.xlsx>
sheetpilot-agent task-run --request request.json
sheetpilot-agent task-status --task-id <task-id>
```

`sheetpilot-agent` 和 `python -m sheetpilot.agent_cli` 通过独立的 Agent CLI 只暴露以上三个命令。`sheetpilot` 仍指向旧兼容 CLI，保留用于兼容测试，不属于 Agent 产品接口。

## 目录

```text
src/sheetpilot/
  agent_cli.py          Agent 唯一 CLI
  task_api/             Task Contract、Compiler、Runtime
  engines/, workbook/   当前 Runtime 复用的工作簿执行基础
  planning/, recipes/,
  mvp.py, cli.py        旧 Runtime 兼容实现

skills/                 唯一 Skill 源目录
tests/unit/             旧 Runtime 与共享基础单元测试
tests/integration/      Agent CLI、Skill、Task API 集成测试
tests/agent_contract/   黑盒用例、数据、Replay、Oracle、评分与结果
tests/fixtures/         测试固定输入
docs/current/           当前 Task API 和黑盒协议
docs/archive/           历史架构与交接材料
archive/                旧 Schema、实验、运行产物和重复文件
```

详细边界见 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)。

## 环境

- Python 3.11+
- `openpyxl` 3.1+

```powershell
python -m pip install -e .
$env:PYTHONPATH = "src;."
python -m unittest discover -s tests -p "test_*.py" -v
```

## 安全边界

- 输入文件不作为保存目标。
- Acceptance 在 Task 创建后不可静默缩减。
- Task/Attempt 目录由 Runtime 管理。
- `summarize_table` 临时产物在发布前必须通过独立结果重算和工作簿结构验收；完整报告写入 Attempt 的 `validation.json`，验收失败不发布最终文件。
- 只有 `RUNTIME_PASS + MATCHED + delivery_valid=true` 的当前产物可交付。
- Runtime 数学验证与 Agent 业务语义判断必须分开报告。
