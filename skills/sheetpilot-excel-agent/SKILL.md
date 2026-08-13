---
name: sheetpilot-excel-agent
description: Use SheetPilot's Agent-facing Task API to produce auditable Excel summaries from .xlsx or .xlsm files. Use for filtered grouping, sum, average, row/non-empty counts, sorting, immutable acceptance, Runtime-managed execution, and publication evidence through task-types, task-run, and task-status.
---

# SheetPilot Excel Agent

把 SheetPilot Agent API 作为唯一 Excel 执行边界。Agent 只提交业务级 Task Request；Runtime 负责字段绑定、内部计划、Task/Attempt 目录、执行、验证和发布。

## 最高优先级纪律

- 第一个执行类工具调用必须是已加载 Skill 路径下包装脚本的 `task-types`；不要先搜索 Skill、命令、源码、Schema、示例或工作簿内容。
- **停止门**：`CONFIGURATION_REQUIRED`、`INTERNAL_ERROR` 或 `recovery.action = HUMAN_ACTION_REQUIRED/NONE` 一旦出现，本次运行立即结束。下一步只能向用户报告；不得设置或修改 `SHEETPILOT_ROOT` 等环境变量，不得再次调用包装脚本，也不得读取源码、检查 Runtime 状态目录、复制输入、更换路径或使用外部工作簿库兜底。
- 任何情况下都禁止使用 openpyxl、pandas、Excel COM、LibreOffice 或自写脚本读取后修改并交付工作簿。Runtime 失败意味着本次任务未交付。

## 唯一入口

从本次已加载的 `SKILL.md` 绝对路径取得 `<skill-root>`，直接执行：

```powershell
python "<skill-root>\scripts\sheetpilot_cli.py" task-types
python "<skill-root>\scripts\sheetpilot_cli.py" task-run --request "<request.json>"
python "<skill-root>\scripts\sheetpilot_cli.py" task-status --task-id "<task-id>"
```

`<skill-root>` 是包含当前 `SKILL.md` 的目录。直接使用该已知路径；不要搜索可执行文件、列举 Skill 目录或读取包装脚本。若包装脚本报告找不到 SheetPilot 根目录，本次运行已经结束；请用户在新会话前配置 `SHEETPILOT_ROOT`。当前会话禁止自行设置环境变量后继续。

## 执行流程

1. 调用 `task-types`，只依据返回的 Task Type 契约、枚举和最小示例构造请求。
2. 解析用户输出路径：
   - 普通路径：原样使用。
   - 包含 `<AUTO-RESULT-DIR>`：仅使用下面的 PowerShell 片段生成并创建目录；不要自行设计日期格式：

```powershell
$scenarioId = "<Prompt中的测试场景ID>"
$beijingNow = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTimeOffset]::UtcNow, "China Standard Time")
$stamp = $beijingNow.ToString("yyyyMMdd'T'HHmmss") + "+0800"
$randomId = [Guid]::NewGuid().ToString("N").Substring(0, 6)
$resultDirName = "${scenarioId}__${stamp}__run-${randomId}"
$resultDir = Join-Path "<AUTO-RESULT-DIR的父目录>" $resultDirName
New-Item -ItemType Directory -LiteralPath $resultDir | Out-Null
```

   生成结果必须匹配 `^[A-Za-z0-9_-]+__\d{8}T\d{6}\+0800__run-[0-9a-f]{6}$`。目录名不得包含 `:`、`/`、`\` 或空格。若目录已存在，重新生成随机标识；不要清空或复用。
3. 在确定的用户交付目录写入一个 Task Request JSON。Request 只描述来源、过滤、维度、指标、排序、输出和 Acceptance。
4. 调用 `task-run --request`。不要提交 Runtime `run-dir`、Task ID、Attempt ID、列字母、内部步骤或 Validator。
5. 根据结构化响应继续：
   - `RUNTIME_PASS`：调用 `task-status` 核对当前交付状态。
   - `NEEDS_BINDING`：只选择响应给出的 Candidate ID；若当前 Runtime 未开放修订或要求人工处理，停止并报告。Candidate 可能包含语义（模糊）匹配，带 `confidence` 与 `sample_values`；Runtime 只对精确表头自动绑定，模糊候选仍需依据其 `header` 与 `sample_values` 确认业务口径后，重新提交精确表头名称或显式选择其 Candidate ID。
   - 错误响应：只执行 `recovery.action` 允许的动作，只修改 `allowed_amendments` 路径。
6. 仅当 `task-status` 同时满足以下条件时交付：
   - `state = RUNTIME_PASS`
   - `artifact_integrity = MATCHED`
   - `delivery_valid = true`

## 请求边界

- 使用稳定组件 ID 连接过滤、维度、指标、排序和 Acceptance。
- Acceptance 必须覆盖用户要求的全部过滤、维度、指标和排序，不得为通过执行而缩减。
- 业务字段只使用表头名称。字段到 Sheet、表头行和列字母的绑定由 Runtime 完成。
- 输出使用新文件和新工作表；不要覆盖输入或已有输出。
- `<AUTO-RESULT-DIR>` 只授权创建一个新的用户交付目录；它不授权查看、创建、清空或复用 Runtime 的 Task/Attempt 状态目录。
- `count.rows` 表示过滤后的行数；`count.non_empty` 表示指定字段的非空数量。不要把用户要求的唯一值计数改写为这两种定义。

## 黑盒纪律

只把 `task-types`、`task-run` 和 `task-status` 的 JSON 响应作为产品契约和执行证据。不要读取 SheetPilot 的 Python 文件、内部 Schema、设计文档、Task/Attempt 目录或旧命令帮助；不要调用 `inspect`、`capabilities`、`mvp-*`、`plan`、`compile`、`execute`、`run`、`validate`；不要手写内部 DAG，也不要用工作簿库或自写脚本修改输出。

## 最终报告

报告 `task_id`、`attempt_id`、`request_revision`、最终解析后的输出路径、Runtime 状态、`artifact_integrity`、`delivery_valid`、`acceptance_hash` 和 `internal_plan_hash`。

将业务语义判断与 Runtime 结论分开：

- `accepted`：Agent 有独立业务依据确认数学定义符合用户语义。
- `rejected`：数学定义与用户语义冲突。
- `not_assessed`：没有足够独立依据。默认使用此值。
