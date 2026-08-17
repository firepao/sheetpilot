---
name: sheetpilot-excel-agent
description: Use SheetPilot's Agent-facing Task API to produce auditable Excel summaries from .xlsx or .xlsm files. Use for filtered grouping, sum, average, row/non-empty counts, sorting, immutable acceptance, Runtime-managed execution, and publication evidence through task-types, task-run, and task-status.
---

# SheetPilot Excel Agent

把 SheetPilot Agent API 作为唯一 Excel 执行边界。Agent 只提交业务级 Task Request；Runtime 负责字段绑定、执行、验证和发布。

## 快速开始

```powershell
# 假设本 SKILL.md 路径为：C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\SKILL.md
# 则脚本路径为：C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py

# 1. 查询字段清单（可选）
python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-types --input orders.xlsx --sheet 交易流水 --header-row 1

# 2. 构造请求并写入文件（UTF-8 无 BOM）
@"
{"schema_version": "1.0", "task_type": "summarize_table", ...}
"@ | Out-File -FilePath request.json -Encoding UTF8

# 3. 提交任务
python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-run --request request.json --auto-result-dir D:\results

# 4. 复核状态
python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-status --task-id task-abc123
```

## 入口与路径发现

**方法1（推荐）**：从本 SKILL.md 的绝对路径取得 `<skill-root>`：

```powershell
python "<skill-root>\scripts\sheetpilot_cli.py" task-types
python "<skill-root>\scripts\sheetpilot_cli.py" task-run --request "<request.json>"
python "<skill-root>\scripts\sheetpilot_cli.py" task-status --task-id "<task-id>"
```

**方法2（兜底）**：如果从 SKILL.md 路径拼接的脚本路径不存在，按以下顺序查找：

1. **环境变量**：`$env:SHEETPILOT_ROOT\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py`
2. **向上递归**：从当前目录向上查找含 `src/sheetpilot/agent_cli.py` 的 SheetPilot 根目录
3. **文件搜索**：在常见路径下搜索 `sheetpilot_cli.py`（最后手段）

**如找不到**，包装脚本返回 `CONFIGURATION_REQUIRED` 错误，本次运行结束，向用户报告。

**不要**读取包装脚本源码、直接读写工作簿或调用其他命令。

## 环境要求

包装脚本会按以下顺序查找 SheetPilot Runtime：
1. 环境变量 `SHEETPILOT_ROOT`（如已设置）
2. 从脚本自身路径向上递归查找含 `src/sheetpilot/agent_cli.py` 的目录
3. 从当前工作目录向上递归查找

**如果找不到**，返回 `CONFIGURATION_REQUIRED` 错误：
```json
{
  "schema_version": "1.0",
  "status": "CONFIGURATION_REQUIRED",
  "message": "找不到 SheetPilot Runtime；本次运行已停止。请用户在新会话前配置 SHEETPILOT_ROOT。"
}
```

**配置示例**（PowerShell）：
```powershell
$env:SHEETPILOT_ROOT = "D:\bitexcel\SheetPilot"
```

## 工作流程

### 1. 获取契约与字段清单（可选）

**请求前查询（推荐）**：
```powershell
task-types --input <file> --sheet <名称> --header-row <行号>
```

返回：
- 完整 Task Contract manifest（任务类型、字段结构、函数列表）
- `input_profile.field_inventory`：工作簿的全部字段清单

**字段清单条目结构**：
```json
{
  "id": "candidate-8f1472c1",
  "header": "净销售额",
  "column": "G",
  "sheet": "交易流水",
  "header_row_start": 1,
  "inferred_type": "number",
  "null_ratio": 0.02,
  "sample_values": [128.5, 300, 99.9],
  "neighbor_headers": ["数量", "单价"]
}
```

**字段清单用途**：
- 了解工作簿实际字段名（避免用户描述与实际表头不一致）
- 通过样本值、类型、相邻表头做语义判断
- 优先写精确表头名，减少 `NEEDS_BINDING` 修订

**注意**：
- 清单最多 64 列 / 64 KB；超限时 Runtime 返回 `INVENTORY_TOO_LARGE`，要求用 `--sheet` 收窄
- 敏感值已掩码：手机号 `138****1234`、身份证号前6后4、邮箱 `u***@domain`
- 字符串样本最多 64 字符，每列最多 3 个样本

### 2. 构造并提交 Task Request

**重要**：`--request` 参数接受**文件路径**，不是内联 JSON 字符串。

**步骤**：

1. **构造 Task Request JSON**（从 `task-types` 返回的契约构造）
2. **写入文件**（UTF-8 无 BOM 编码）
3. **提交任务**

**PowerShell 示例**：
```powershell
# 1. 构造请求
$request = @"
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\\data\\orders.xlsx",
  "output_file": "<AUTO-RESULT-DIR>\\summary.xlsx",
  "user_request": "按城市汇总销售额",
  "source": {"sheet": "交易流水", "header_row": 1},
  "filters": [],
  "dimensions": [{"id": "city", "field": "城市", "output_name": "城市"}],
  "metrics": [{"id": "total", "function": "sum", "field": "销售额", "output_name": "总销售额"}],
  "output": {"sheet": "汇总", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["city"],
    "required_metrics": ["total"],
    "required_sort": []
  }
}
"@

# 2. 写入文件（UTF-8 无 BOM）
$request | Out-File -FilePath request.json -Encoding UTF8

# 3. 提交任务
python "<skill-root>\scripts\sheetpilot_cli.py" task-run --request request.json --auto-result-dir D:\results
```

**编码要求（关键）**：
- ✅ **正确**：UTF-8 无 BOM
  ```powershell
  # PowerShell
  $json | Out-File request.json -Encoding UTF8
  
  # 或使用 .NET API（更可靠）
  [System.IO.File]::WriteAllText("request.json", $json, [System.Text.UTF8Encoding]::new($false))
  ```
  ```python
  # Python
  import json
  with open("request.json", "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False)
  ```

- ❌ **错误**：UTF-8 BOM（导致 JSON 解析失败）
  ```powershell
  $json | Out-File request.json  # PowerShell 默认写 BOM
  ```

**输出路径规则**：
- **首次请求**：写 `<AUTO-RESULT-DIR>/<文件名>.xlsx`，并带 `--auto-result-dir <父目录>`
- **包装脚本**：自动生成结果目录并在响应中返回 `generated_result_dir`
- **修正重提**：复用 `generated_result_dir` 的真实路径，不再带占位符

**字段名选择策略**：
- 如用户描述的字段名与 `field_inventory` 中的表头名一致，**优先使用精确表头名**
- 精确匹配可直接通过自动绑定，无需进入 `NEEDS_BINDING` 修订流程
- 如无法确定，可故意写模糊名称触发 `NEEDS_BINDING`，获取完整清单后再选择

### 3. 响应处理决策表

| 判断条件 | 下一步 |
|---------|--------|
| `status = RUNTIME_PASS` | 调用 `task-status` 复核：必须同时满足 `state=RUNTIME_PASS` + `artifact_integrity=MATCHED` + `delivery_valid=true` 才交付 |
| `status = NEEDS_BINDING` | 进入字段绑定流程（见下节） |
| `status = REQUEST_INVALID` | 读 `error.recovery.action`：<br>• `AMEND_REQUEST` → 只按 `allowed_amendments` 修改后重提<br>• `CREATE_NEW_TASK` → 停止并报告<br>• `HUMAN_ACTION_REQUIRED` → 停止并报告 |
| `status = CAPABILITY_UNSUPPORTED` | 停止并报告（当前任务类型无法表达该需求） |
| `status = EXECUTION_FAILED` | 读 `error.recovery.action`：<br>• `RETRY_ATTEMPT` → 停止并报告（Runtime 未开放重试入口）<br>• 其他 → 停止并报告 |
| `status = VALIDATION_FAILED` | 停止并报告（Runtime 验收失败） |
| `status = PUBLICATION_FAILED` | 停止并报告（文件发布失败） |
| `status = INPUT_CHANGED` | 停止并报告（输入文件被修改） |
| `error.code = INTERNAL_ERROR` | **立即停止**，只向用户报告（Runtime 内部错误） |
| `status = CONFIGURATION_REQUIRED` | **立即停止**，向用户报告配置问题 |

**停止门**：
- `status = CONFIGURATION_REQUIRED`
- 任意响应的 `error.code = INTERNAL_ERROR`
- 任意响应的 `recovery.action ∈ {HUMAN_ACTION_REQUIRED, NONE}`

## 字段绑定流程（NEEDS_BINDING）

当 Runtime 返回 `NEEDS_BINDING` 时，说明某些字段无法精确匹配自动绑定。

### 1. 理解绑定状态

响应中的 `binding_slots` 包含待绑定字段：

```json
{
  "status": "NEEDS_BINDING",
  "task_id": "task-abc123",
  "request_revision": 1,
  "binding_slots": [
    {
      "id": "binding-001",
      "logical_field": "净销售收入",
      "references": ["/dimensions/0/field"],
      "requirements": {
        "accepted_types": ["number"],
        "uses": ["dimension"]
      },
      "status": "UNRESOLVED",
      "candidate_ids": ["candidate-001", "candidate-002", "candidate-003"]
    }
  ],
  "field_inventory": [
    {
      "id": "candidate-001",
      "header": "净销售额",
      "column": "B",
      "inferred_type": "number",
      "sample_values": [100, 200, 150]
    },
    {
      "id": "candidate-002",
      "header": "销售额",
      "column": "C",
      "inferred_type": "number",
      "sample_values": [113, 226, 169.5]
    }
  ]
}
```

**Slot 状态**：
- `UNRESOLVED`：无精确匹配，需要 Agent 语义判断
- `AMBIGUOUS`：多列同名，需要通过样本值、相邻表头区分

### 2. 语义判断流程

**对照字段清单进行判断**：
1. 查看 `logical_field`（用户需求中的字段名）
2. 对照 `field_inventory` 中的候选：
   - 表头名称相似度
   - `sample_values` 是否符合业务语义
   - `inferred_type` 是否满足 `requirements.accepted_types`
   - `neighbor_headers` 上下文是否合理
3. 从 `candidate_ids` 中选择最匹配的 `candidate_id`

**示例：区分两个"销售额"列**
```
用户要求："净销售收入"
候选1：header="净销售额", samples=[100, 200, 150]
候选2：header="销售额", samples=[113, 226, 169.5]

判断：113/100=1.13, 226/200=1.13 → 候选2是含税金额（×1.13）
结论：选择候选1（净销售额）作为"净销售收入"的绑定
```

### 3. 提交修订（Amendment）

**只修改绑定，不改原请求字段**：

```json
{
  "task_id": "task-abc123",
  "base_revision": 1,
  "amendments": [
    {
      "op": "add",
      "path": "/bindings/binding-001",
      "value": {"candidate_id": "candidate-001"}
    }
  ]
}
```

**修订约束**：
- **只能**提交 `/bindings/<slot-id>` 路径的修订
- **只能**从 `allowed_amendments.constraints.candidate_ids` 中选择
- **不得**修改原请求的 `field`（如 `/dimensions/0/field`）
- 修改原请求字段会返回 `CREATE_NEW_TASK` 错误，需重建 Task

**一次修订必须解决全部待绑定 Slot**，否则返回 `INVALID_COMBINATION` 错误。

### 4. 修订冲突处理

如果其他进程已修改 Task，返回 `REVISION_CONFLICT`：
```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "recovery": {"base_revision": 2}
  }
}
```

处理：重新调用 `task-status --task-id <id>` 获取最新状态，不要只替换 `base_revision` 数字后重放旧修订。

## 黑盒纪律

**必须遵守**：
- 不读取 SheetPilot 源码、Schema、设计文档
- 不直接读写工作簿文件（用 `task-types --input` 获取字段清单）
- 不调用 `task-types`/`task-run`/`task-status` 之外的命令
- 不管理 Runtime state root（由部署配置注入）

**请求不合规是正常路径**：Runtime 会返回精确修订指令（`allowed_amendments`），照做即可，不要自行猜测或翻源码。

## 最终报告

交付前必须报告以下内容：

**Runtime 证据**（来自 `task-status` 响应）：
- `task_id`
- `attempt_id`
- `request_revision`
- 最终输出文件路径
- `runtime_status`（最终状态）
- `artifact_integrity`（MATCHED/MODIFIED/MISSING）
- `delivery_valid`（true/false）
- `acceptance_hash`
- `internal_plan_hash`

**语义判断**（独立于 Runtime 结论）：
```json
{
  "semantic_assessment": {
    "status": "accepted",
    "rationale": "Runtime 通过验收；输出与用户需求一致；字段绑定语义正确（净销售额 vs 含税销售额已正确区分）",
    "based_on_evidence_hash": "<acceptance_hash>"
  }
}
```

**语义判断状态**：
- `accepted`：Runtime Pass 且业务语义正确
- `rejected`：Runtime Pass 但业务语义错误（如字段绑定错误）
- `not_assessed`：Runtime 未通过，无法评估语义

**区分 Runtime Pass 与业务语义**：Runtime 只验证机械正确性（类型、非空、排序），不理解业务语义；Agent 需独立判断输出是否满足用户真实需求。

## 错误码速查

| 错误码 | 含义 | 处理 |
|--------|------|------|
| `INTERNAL_ERROR` | Runtime 内部错误 | 立即停止 |
| `INVALID_ENUM` / `INVALID_VALUE` | 字段值不合法 | 按 `allowed_amendments` 修改 |
| `INVALID_REFERENCE` | 引用不存在的对象 | 检查 ID/路径 |
| `INVALID_COMBINATION` | 字段组合冲突 | 按错误提示调整 |
| `REVISION_CONFLICT` | 并发修改冲突 | 重新查询 `task-status` |
| `INPUT_NOT_FOUND` | 输入文件不存在 | 停止并报告 |
| `INVENTORY_TOO_LARGE` | 字段清单超限 | 用 `--sheet` 收窄查询 |

## 示例：完整流程

```powershell
# 前提：假设 SKILL.md 在 C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\SKILL.md
# 则脚本路径为：C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py

# 0. 设置环境变量（如需要）
$env:SHEETPILOT_ROOT = "D:\bitexcel\SheetPilot"

# 1. 查询字段清单（可选但推荐）
python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-types --input orders.xlsx --sheet 交易流水 --header-row 1

# 2. 根据清单构造请求并写入文件
@"
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:\\data\\orders.xlsx",
  "output_file": "<AUTO-RESULT-DIR>\\summary.xlsx",
  "user_request": "按城市汇总销售额",
  "source": {"sheet": "交易流水", "header_row": 1},
  "filters": [],
  "dimensions": [{"id": "city", "field": "城市", "output_name": "城市"}],
  "metrics": [{"id": "total", "function": "sum", "field": "销售额", "output_name": "总销售额"}],
  "output": {"sheet": "汇总", "anchor": "A1", "sort": []},
  "acceptance": {
    "required_filters": [],
    "required_dimensions": ["city"],
    "required_metrics": ["total"],
    "required_sort": []
  }
}
"@ | Out-File -FilePath request.json -Encoding UTF8

# 3. 提交任务
python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-run --request request.json --auto-result-dir D:\results

# 4. 如返回 NEEDS_BINDING，对照 field_inventory 判断后提交修订
@"
{
  "task_id": "task-abc123",
  "base_revision": 1,
  "amendments": [
    {"op": "add", "path": "/bindings/binding-001", "value": {"candidate_id": "candidate-8f1472c1"}}
  ]
}
"@ | Out-File -FilePath amendment.json -Encoding UTF8

python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-run --request amendment.json

# 5. 返回 RUNTIME_PASS 后复核
python "C:\Users\nine\bit-Agent\skills\sheetpilot-excel-agent\scripts\sheetpilot_cli.py" task-status --task-id task-abc123

# 6. 确认 artifact_integrity=MATCHED + delivery_valid=true 后交付
```

## 常见问题排查

### 问题1：找不到脚本路径

**症状**：
```
FileNotFoundError: [Errno 2] No such file or directory: 'C:\Users\...\sheetpilot_cli.py'
```

**排查步骤**：
1. 检查从 SKILL.md 路径拼接的脚本路径是否存在
2. 检查环境变量 `$env:SHEETPILOT_ROOT` 是否已设置
3. 尝试文件搜索：
   ```powershell
   Get-ChildItem -Path . -Filter sheetpilot_cli.py -Recurse -ErrorAction SilentlyContinue
   ```
4. 如找到，使用完整绝对路径

### 问题2：JSON 解析失败

**症状**：
```
json.decoder.JSONDecodeError: Unexpected UTF-8 BOM
```

**原因**：PowerShell 默认写入 UTF-8 BOM

**解决**：
```powershell
# 使用 -Encoding UTF8 参数
$json | Out-File request.json -Encoding UTF8
```

### 问题3：CONFIGURATION_REQUIRED

**症状**：
```json
{"status": "CONFIGURATION_REQUIRED", "message": "找不到 SheetPilot Runtime"}
```

**解决**：
```powershell
# 设置环境变量
$env:SHEETPILOT_ROOT = "D:\bitexcel\SheetPilot"

# 重新运行命令
python "<skill-root>\scripts\sheetpilot_cli.py" task-types
```

### 问题4：字段绑定失败（高频）

**症状**：
```json
{"status": "NEEDS_BINDING", "binding_slots": [...]}
```

**不是错误**：这是正常流程，说明字段无法精确匹配，需要 Agent 语义判断。

**解决**：参见"字段绑定流程"章节。

### 问题5：--request 参数错误

**症状**：
```
error: argument --request: expected one argument
```

**原因**：直接传 JSON 字符串而非文件路径

**解决**：
```powershell
# ❌ 错误
task-run --request '{"schema_version": ...}'

# ✅ 正确
$json | Out-File request.json -Encoding UTF8
task-run --request request.json
```

## 附录：字段清单数据边界

- **条目上限**：64 列
- **字节上限**：64 KB（序列化后）
- **样本数量**：每列最多 3 个非空值
- **样本长度**：字符串最多 64 字符
- **敏感值掩码**：
  - 手机号（11位）：`138****1234`
  - 身份证号（18位）：`110101********1234`
  - 邮箱：`zhangsan***@example.com`
- **排除内容**：公式源码、环境变量、外部链接、隐藏 Sheet
