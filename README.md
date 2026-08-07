# SheetPilot

SheetPilot 是一个确定性 Excel Agent MVP 内核。它将已经完成语义映射的任务编译为不可变执行计划，在工作副本上执行，并通过独立校验后发布结果。

## 环境

- Python 3.11+
- `openpyxl` 3.1+

开发安装：

```powershell
python -m pip install -e .
```

## CLI

```powershell
sheetpilot inspect --input source.xlsx --run-dir runs\run-001
sheetpilot capabilities
sheetpilot compile --task semantic_task.json --high-level-plan high_level_plan.json --run-dir runs\run-001
sheetpilot execute --plan runs\run-001\execution_plan.json --run-dir runs\run-001
sheetpilot validate --run-dir runs\run-001
```

也可使用 `run` 一次完成 compile、execute 和 validate。CLI 标准输出始终为单个 JSON 对象；需要确认时不读取交互式输入。

## 安全边界

- 原输入不会作为保存目标。
- MVP 仅允许在计划中新建的工作表写入结果。
- VBA、ActiveX、OLE、外链、数据连接、透视缓存、切片器和数据模型默认阻断。
- 输入哈希、handler 白名单、变更预算和独立业务对账在执行链路中强制检查。

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
