# 轻量 Skill 实测问题与实施交接 V1

## 1. 文档目的

本文复盘 `U3_builtin_dirty_orders_report.xlsx` 的首次轻量 Skill 测试，并把暴露的问题转化为下一轮可直接实施的工作项。

本次测试最终生成的数据看起来基本正确，但执行过程没有形成“原子能力 + 分子能力 + 受控动态脚本”的 SheetPilot MVP 闭环。主要原因不是 Agent 无法完成 Excel 任务，而是轻量 Runtime 目前只有能力声明和 Python 内部执行函数，没有完整 CLI 执行、动态变换和任务级验证入口。

## 2. 本次测试结论

| 评价项 | 结论 | 说明 |
|---|---|---|
| 业务结果 | 基本正确 | 城市汇总、订单数和平均金额最终存在，汇总值看起来合理 |
| 轻量 Skill 使用 | FAIL | Agent 被旧脚本引回 Recipe/Compiler 流程 |
| MVP Atom/Molecule 闭环 | FAIL | 只查询了能力，没有通过轻量入口执行 Molecule |
| 动态脚本合规性 | FAIL | 动态脚本直接用 openpyxl 读写工作簿 |
| 能力报告可信度 | FAIL | 混合报告了 MVP、旧注册表和自写脚本能力 |
| 验证完整性 | FAIL | 已验证的文件又被外部脚本修改，未重新经过 SheetPilot Validator |

## 3. 实际执行路径

Agent 最终走的是以下混合路径：

```text
inspect
  -> mvp-capabilities（仅查询）
  -> 找不到轻量执行入口
  -> 读取旧 prepare_operating_summary.py
  -> 生成旧 HighLevelPlan
  -> compile / run
  -> 发现缺少 count / average
  -> 手工修改 HighLevelPlan
  -> 生成空指标列
  -> 阅读源码确认 aggregate 只支持 sum
  -> 自写 openpyxl 脚本直接修改输出文件
  -> 自写验证脚本检查结果
```

目标路径应当是：

```text
inspect
  -> mvp-capabilities
  -> 构造轻量计划
  -> mvp-run
       -> Molecule 展开为 Atom
       -> 必要时执行受控 Dynamic Transform
       -> 固定写入 Atom 落盘
  -> mvp-validate
  -> publish
```

## 4. 问题与根因

### 4.1 轻量能力只能查询，不能通过 CLI 执行

当前 CLI 只暴露 `mvp-capabilities`。`src/sheetpilot/mvp.py` 中虽然存在 `execute()`，但 Agent 无法通过稳定命令提交计划并生成工作簿。

结果是 Agent 在查看 CLI 帮助后自动回退到旧的 `plan -> compile -> run` 流程。

必须新增：

```text
sheetpilot mvp-run --input <xlsx> --output <xlsx> --plan <plan.json> --run-dir <dir>
sheetpilot mvp-validate --run-dir <dir>
```

`mvp-run` 至少负责：复制输入为工作副本、校验计划、执行 Atom/Molecule、保存临时输出、记录执行证据。只有 `mvp-validate` 通过后才发布最终文件。

### 4.2 Skill 目录仍保留旧流程文件

精简后的 `SKILL.md` 已不要求 Recipe 流程，但 Skill 包中仍存在：

- `scripts/prepare_operating_summary.py`
- `references/planning.md`
- `references/contracts.md`
- `references/semantic-mapping.md`
- `references/troubleshooting.md`

Agent 根据文件名推断 `prepare_operating_summary.py` 是正确入口，从而重新进入旧架构。

轻量 Skill 交付包应只保留：

```text
sheetpilot-excel-agent/
  SKILL.md
  agents/openai.yaml
  scripts/sheetpilot_cli.py
```

需要继续保留的参考文档必须改为轻量 Runtime 契约，不能混入旧 Planner/Recipe 指令。

### 4.3 能力清单缺少参数级契约

当前清单只能看到存在 `aggregate`，看不到它仅支持 `sum`。Agent 因此自行加入 `count` 和 `average`，执行后得到全空列。

能力 Manifest 至少需要声明：

```json
{
  "name": "aggregate",
  "kind": "atom",
  "required": ["input", "group_by", "metrics"],
  "supported_functions": ["sum", "count", "average"],
  "input_kind": "TableData",
  "output_kind": "TableData"
}
```

参数校验必须发生在写入前。未知聚合函数应返回稳定的 `PLAN_INVALID`，不能静默生成空列。

### 4.4 通用聚合能力不完整

`count` 和 `average` 属于跨业务通用统计能力，不应反复由动态脚本实现。MVP 的 `aggregate` 应补齐：

| 函数 | 建议语义 |
|---|---|
| `sum` | 对有效数值求和 |
| `count` | 统计行数，或统计指定字段非空值数量；两者必须通过参数区分 |
| `average` | 对有效数值求平均；无有效值时返回 `None` |
| `min` / `max` | 可作为后续增量，不阻塞首轮闭环 |

订单数建议使用显式形式：

```json
{"function": "count", "field": "订单号", "mode": "non_empty", "as": "订单数量"}
```

若统计过滤后行数，则使用：

```json
{"function": "count", "mode": "rows", "as": "订单数量"}
```

### 4.5 Molecule 没有独立可执行契约

本次 Agent 声称使用了 `summarize_by_dimension`，实际执行的是旧 Recipe 生成的 `filter_rows + aggregate`，而不是轻量 Molecule。

Molecule Manifest 应公开：

- 参数 Schema；
- 展开的 Atom 名称；
- 支持的可选步骤；
- 输入输出类型；
- 所需验证器；
- 是否写工作簿。

`summarize_by_dimension` 的 MVP 契约建议为：

```text
输入：TableData、可选 where、group_by、metrics、可选 sort
展开：filter_rows? -> aggregate -> sort_rows?
输出：TableData
验证：输入过滤计数、分组行数、可加和指标对账
```

因此还需要把 `sort_rows` 纳入轻量 Atom；否则“按金额降序”仍需回退旧 Runtime 或动态脚本。

### 4.6 Dynamic Transform 尚未接入 Runtime

`mvp.execute()` 接受 Python Callable，但 CLI 没有安全加载和运行动态脚本的方式。Agent 最终直接使用 openpyxl 读写文件，绕过全部执行边界。

动态变换必须满足：

```text
TableData -> TableData 或 ScalarRef
```

禁止动态脚本：

- 打开、读取或保存任意文件；
- 导入 openpyxl 等工作簿库；
- 访问网络、子进程和环境变量；
- 自行决定写入 sheet/range；
- 绕过执行记录和 Validator。

建议复用现有 `runtime/transform.py` 的 AST 检查、子进程、超时和资源预算，在轻量 CLI 中增加：

```text
--dynamic-script <transform.py>
```

动态结果必须交回 `write_table`、`write_values` 等固定 Atom 落盘。

### 4.7 写入能力没有进入轻量能力闭环

轻量目录当前只有读取和内存变换能力，无法独立交付 Excel。MVP 至少需要增加：

| Atom | 作用 |
|---|---|
| `sort_rows` | 对 TableData 稳定排序 |
| `create_sheet` | 创建目标工作表 |
| `write_table` | 将 TableData 写入明确区域 |
| `apply_style_preset` | 应用有限的预设样式，可延后但建议保留 |
| `save_workbook` | 保存临时输出，不直接发布 |

图表、冻结窗格和 PNG 不应阻塞首个闭环。它们可以在基础写入和验证稳定后再加入。

### 4.8 Validator 只验证计划，没有验证完整用户需求

第一次输出缺少订单数和平均金额，但旧 Validator 仍返回 PASS。这说明验证的是计划内部一致性，而不是用户 Requirement 是否全部满足。

随后 Agent 又用外部脚本修改已经验证过的文件，原验证结果自然失效。

轻量任务必须生成最小 Requirement Manifest，例如：

```json
{
  "required_sheets": ["城市经营汇总"],
  "required_columns": {
    "城市经营汇总": ["城市", "销售收入", "订单数量", "平均订单金额"]
  },
  "checks": [
    {"type": "source_unchanged"},
    {"type": "row_filter_count"},
    {"type": "aggregate_reconciliation", "metric": "销售收入"},
    {"type": "sort_order", "field": "销售收入", "direction": "desc"}
  ]
}
```

Validator 必须重新打开最终临时文件验证。任何验证后的修改都必须使原验证证据失效，并要求重新验证。

### 4.9 能力使用报告没有唯一事实来源

最终报告把以下三组内容混在一起：

- 轻量 MVP Atom/Molecule；
- 旧能力注册表和 Recipe 展开步骤；
- Agent 自写 openpyxl 脚本。

执行记录应由 Runtime 自动生成，而不是由 Agent 回忆和总结。建议记录：

```json
{
  "requested_operations": [],
  "expanded_operations": [],
  "executed_atoms": [],
  "dynamic_transforms": [],
  "workbook_writes": [],
  "validation_results": []
}
```

Agent 最终只能引用该记录，不得自行声称使用了未执行的能力。

### 4.10 临时产物和运行目录管理不清晰

Agent 曾直接使用 `result` 目录中已有的 `workbook_profile.json`。这可能复用其他运行的画像，造成输入事实污染。

每次任务必须创建独立运行目录：

```text
runs/<run-id>/
  workbook_profile.json
  plan.json
  execution.json
  temporary_output.xlsx
  evidence.json
  result.json
```

所有文件都应包含输入绝对路径和 SHA-256，并在各阶段检查一致性。

## 5. MVP 目标范围

下一轮不恢复完整 Planner，也不实现脏订单专用 Recipe。只完成一个通用、可运行、可验证的闭环。

### 5.1 必须实现

原子能力：

```text
read_table
filter_rows
derive_column
aggregate(sum/count/average)
sort_rows
create_sheet
write_table
save_workbook
```

分子能力：

```text
summarize_by_dimension
add_metric
```

执行入口：

```text
mvp-capabilities
mvp-run
mvp-validate
```

运行保障：

- 输入文件不可覆盖；
- 每次使用独立运行目录；
- Molecule 必须确定性展开；
- 参数执行前校验；
- Dynamic Transform 只能处理 TableData/ScalarRef；
- 所有写入由注册 Atom 完成；
- Validator 通过后才能发布。

### 5.2 暂不实现

- 完整 Coverage Planner；
- LLM 自动生成复杂 DAG；
- 脏订单专用 Recipe；
- PNG 预览；
- 动态脚本直接操作工作簿；
- 复杂图表和高级 Excel 对象；
- 多引擎路由。

## 6. 建议接口

### 6.1 计划格式

```json
{
  "schema_version": "1.0",
  "input_file": "D:/data/input.xlsx",
  "output_file": "D:/data/output.xlsx",
  "steps": [
    {
      "id": "source",
      "op": "read_table",
      "sheet": "清洗明细",
      "header_row": 1,
      "columns": {
        "城市": "D",
        "销售额": "G",
        "是否退货": "J",
        "清洗状态": "L"
      }
    },
    {
      "id": "summary",
      "op": "summarize_by_dimension",
      "input": "source",
      "where": {
        "all": [
          {"field": "清洗状态", "op": "eq", "value": "有效"},
          {"field": "是否退货", "op": "eq", "value": "否"}
        ]
      },
      "group_by": ["城市"],
      "metrics": [
        {"field": "销售额", "function": "sum", "as": "销售收入"},
        {"function": "count", "mode": "rows", "as": "订单数量"},
        {"field": "销售额", "function": "average", "as": "平均订单金额"}
      ],
      "sort": [{"field": "销售收入", "direction": "desc"}]
    },
    {"id": "sheet", "op": "create_sheet", "sheet": "城市经营汇总"},
    {"id": "write", "op": "write_table", "input": "summary", "sheet": "城市经营汇总", "anchor": "A1"}
  ],
  "requirements": {
    "required_sheets": ["城市经营汇总"],
    "required_columns": {"城市经营汇总": ["城市", "销售收入", "订单数量", "平均订单金额"]},
    "checks": ["source_unchanged", "aggregate_reconciliation", "sort_order"]
  }
}
```

### 6.2 CLI 结果

成功时返回：

```json
{
  "status": "PASS",
  "run_dir": "...",
  "output_file": "...",
  "executed_atoms": [],
  "expanded_molecules": [],
  "dynamic_transforms": [],
  "validation": {}
}
```

失败时返回稳定错误码，至少区分：

```text
INPUT_INVALID
PLAN_INVALID
CAPABILITY_UNSUPPORTED
DYNAMIC_TRANSFORM_REJECTED
EXECUTION_FAILED
VALIDATION_FAILED
```

## 7. 建议实施顺序

### 阶段 A：打通固定能力执行

1. 给 Atom/Molecule 增加参数 Schema 和完整 Manifest。
2. 为 `aggregate` 实现 `count`、`average`，遇到未知函数立即失败。
3. 增加 `sort_rows`、`create_sheet`、`write_table`、`save_workbook`。
4. 实现计划加载、Molecule 展开、依赖结果传递和统一执行记录。
5. 暴露 `mvp-run`。

阶段 A 的完成标准：不依赖旧 Recipe，可以从脏订单工作簿生成城市经营汇总。

### 阶段 B：补任务级验证

1. 为计划增加最小 Requirement Manifest。
2. 实现输入哈希、必需 sheet/列、过滤计数、聚合对账和排序验证。
3. 实现 `mvp-validate` 和验证后发布。
4. 禁止发布后继续修改；若修改则强制重新验证。

### 阶段 C：接入受控动态变换

1. 复用现有动态运行时安全检查。
2. 定义唯一入口函数和 TableData 序列化协议。
3. 禁止文件、网络、子进程和工作簿库。
4. 动态结果交给固定写入 Atom。
5. 在执行记录中保存脚本哈希、预算、输入输出行列数和错误。

### 阶段 D：清理 Skill 交付包

1. 删除或移出旧 Recipe/Planner 文件。
2. 更新 `SKILL.md`，只说明三条路径和三个 CLI 命令。
3. 更新 `agents/openai.yaml`。
4. 运行 `quick_validate.py`。
5. 使用独立的新运行目录做一次端到端测试。

## 8. 测试要求

至少增加以下测试：

| 测试 | 预期 |
|---|---|
| Manifest 声明参数和支持函数 | Agent 无需读源码即可规划 |
| `sum/count/average` 多指标聚合 | 数值正确且无空列 |
| 未知聚合函数 | 写入前返回 `PLAN_INVALID` |
| Molecule 展开 | 展开步骤确定且可审计 |
| 带双条件过滤的城市汇总 | 行数、城市数和销售额正确 |
| 降序排序 | 输出顺序正确 |
| 输入文件保护 | 输入 SHA-256 不变 |
| 动态脚本文件访问 | 被拒绝 |
| 动态脚本返回 TableData | 由固定 Atom 成功写入 |
| 输出修改后复用旧证据 | 验证失败 |
| 端到端真实文件复核 | 重新打开 xlsx 后通过 |

完整验收场景继续使用：

```text
输入：tests/fixtures/legacy-mvp/U3_builtin_dirty_orders_report.xlsx
过滤：清洗状态=有效 且 是否退货=否
输出：按城市汇总销售收入、订单数量、平均订单金额，并按销售收入降序
```

不得针对这个场景注册专用 Recipe；它只是验证通用能力组合是否完整。

## 9. 完成定义

只有同时满足以下条件，轻量 Skill Demo 才算完成：

1. Agent 不读取 SheetPilot 源码也能从 Manifest 得到完整能力契约。
2. Agent 不使用旧 `prepare_operating_summary.py`。
3. 一条 `mvp-run` 命令可以执行 Atom/Molecule 计划。
4. `count` 和 `average` 由通用聚合 Atom 完成。
5. 长尾逻辑可由受控 Dynamic Transform 处理，但脚本不能直接操作 Excel。
6. 所有工作簿写入均经过注册 Atom。
7. Validator 对完整 Requirement 验收，而不是只验证计划自洽。
8. 真实输出文件重新打开后验证通过，输入文件哈希保持不变。
9. Runtime 自动生成真实能力执行记录，Agent 不自行编造能力使用情况。
10. Skill 官方校验和项目完整单元测试全部通过。


