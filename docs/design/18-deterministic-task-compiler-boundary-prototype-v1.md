# Task Type 到轻量 Runtime 的确定性编译边界原型 V1

## 1. 决策目标

Agent 只提交 `summarize_table` Task Request。Runtime 必须在不调用 LLM、不选择 Recipe、不读取 Agent 手写 Plan 的前提下，将冻结请求确定性编译为内部轻量计划。

本边界要解决：

- Manifest、Skill 和 Python 实现三份契约并存。
- Agent 手写 Atom DAG、步骤 ID、列字母和 Validator。
- 旧 Planner/Recipe 与轻量 Runtime 同时暴露。
- 输出显示名称被当作内部字段名，导致映射和重命名脆弱。
- 内部计划包含时间戳或随机 ID，无法稳定 hash 和复现。

## 2. 总体边界

```text
Agent
  → typed Task Request
Agent Task Runtime
  → validated Task Request
  → Acceptance Snapshot
  → Binding Snapshot
Deterministic Task Compiler
  → Internal Execution Plan
Lightweight Executor
  → temporary output
Acceptance Validator
  → Runtime Evidence
Publisher
  → final output
```

Agent 看不到也不提交 Internal Execution Plan。Validator 以 Acceptance Snapshot 为权威输入，不以 Internal Plan 中的自我声明作为验收范围。

## 3. Task Type Definition 是唯一事实来源

每个公开 Task Type 由一个类型化定义对象拥有：

```text
TaskTypeDefinition
├── name
├── contract_version
├── request_model
├── binding_requirements
├── compiler
├── acceptance_expander
├── validator_factory
├── supported_features
└── minimal_example
```

从该对象生成：

- `task-types` 公开 Manifest；
- JSON Schema；
- Task Request 运行时校验；
- Field Binding Slot 要求；
- Acceptance Snapshot 展开；
- Compiler 输入类型；
- Task Type 最小示例。

Skill 不复制字段结构、枚举、函数列表或示例，只调用 `task-types` 和 `task-run`。

Atom/Molecule 注册表是 Runtime 内部实现，不再承担 Agent 契约发现职责。

## 4. Compiler 输入

```json
{
  "task_id": "task-01K0...",
  "request_revision": 2,
  "task_contract_version": "1.0",
  "compiler_version": "summarize-table/1.0",
  "request": {},
  "workbook_profile": {},
  "acceptance_snapshot": {},
  "binding_snapshot": {},
  "hashes": {
    "input_sha256": "...",
    "request_revision_hash": "...",
    "acceptance_hash": "...",
    "binding_hash": "..."
  }
}
```

Compiler 只接受已经通过公开契约校验、Acceptance 固化和 Field Binding 的类型化对象。它不负责猜测业务字段或修复请求。

前置条件：

1. Task Type 和 contract version 受支持。
2. Task 固定 input hash 与 Workbook Profile 一致。
3. Acceptance、Revision 和 Binding hash 均有效。
4. 所有 Binding Slot 已解决且类型兼容。
5. Acceptance 引用的组件都存在于当前 Request Revision。

公开请求错误应在 Compiler 前被拒绝。Compiler 前置条件失败表示 Runtime 状态或持久化不一致，返回 `INTERNAL_ERROR`，不能伪装成 Agent 参数错误。

## 5. Compiler 输出

```json
{
  "schema_version": "1.0",
  "compiler_version": "summarize-table/1.0",
  "task_id": "task-01K0...",
  "request_revision": 2,
  "input_sha256": "...",
  "acceptance_hash": "...",
  "binding_hash": "...",
  "steps": [],
  "coverage": [],
  "effects": {
    "read_sheets": ["清洗明细"],
    "create_sheets": ["城市经营汇总"],
    "write_targets": ["城市经营汇总!A1"]
  }
}
```

Internal Plan 不包含：

- 运行目录或 Attempt 路径；
- 临时输出路径；
- 时间戳、随机 plan ID 或不稳定对象地址；
- Agent 自写 Requirement、Validator 或修复脚本；
- Dynamic Transform；
- 旧 Recipe、Planner strategy 或 rationale。

```text
internal_plan_hash = SHA-256(JCS(internal_execution_plan))
```

相同 Compiler 版本、Request Revision、Acceptance Snapshot、Binding Snapshot 和输入身份必须生成字节级相同的 Plan 和 hash。

## 6. 内部字段符号

Compiler 不使用业务显示名称作为内存字段身份。

按 Binding Slot 顺序生成：

```text
binding-001 → __sp_f001
binding-002 → __sp_f002
binding-003 → __sp_f003
```

按 Metric 顺序生成：

```text
sales_revenue       → __sp_m001
order_count         → __sp_m002
average_order_amount → __sp_m003
```

规则：

- Source read、filter、group_by 和 metric source 全部使用 `__sp_fNNN`。
- Aggregate 输出指标使用 `__sp_mNNN`。
- Sort 的组件 ID 编译为对应内部字段符号。
- 最后一个 `project_columns` 操作按契约顺序选择并重命名 Dimension 与 Metric。
- `__sp_` 前缀为 Runtime 保留；公开 output name 不能使用该前缀。

这样即使业务字段、Dimension 输出名称和 Metric 输出名称相同或包含 Unicode，内部引用仍稳定明确。

## 7. project_columns 内部操作

现有 `workbook.tables.select_columns()` 已具备选择、排序和重命名能力，但未进入轻量 Atom 注册表。第一阶段将它注册为 Runtime 内部操作：

```json
{
  "op": "project_columns",
  "input": "summary",
  "fields": [
    {
      "source": "__sp_f001",
      "as": "城市"
    },
    {
      "source": "__sp_m001",
      "as": "销售收入"
    },
    {
      "source": "__sp_m002",
      "as": "订单数量"
    },
    {
      "source": "__sp_m003",
      "as": "平均订单金额"
    }
  ]
}
```

`project_columns` 不向 Agent Manifest 暴露。它只允许选择已存在的内存字段，拒绝重复 output name 和未声明附加列。

## 8. summarize_table 编译算法

输入组件顺序来自 Task Request，不能由 dict 遍历偶然决定。

### 8.1 收集字段

按以下顺序收集并去重 Binding Slot：

```text
filters
→ dimensions
→ metrics with field
```

`count.rows` 不产生字段引用。

### 8.2 生成 read_table

```json
{
  "id": "read_source",
  "op": "read_table",
  "sheet": "清洗明细",
  "header_row": 1,
  "columns": {
    "__sp_f001": "L",
    "__sp_f002": "J",
    "__sp_f003": "D",
    "__sp_f004": "G"
  }
}
```

列字母只来自 Binding Snapshot，不来自 Agent Request。

### 8.3 生成 summarize_by_dimension

```json
{
  "id": "summarize",
  "op": "summarize_by_dimension",
  "input": "read_source",
  "where": {
    "all": [
      {
        "field": "__sp_f001",
        "op": "eq",
        "value": "有效"
      },
      {
        "field": "__sp_f002",
        "op": "eq",
        "value": "否"
      }
    ]
  },
  "group_by": ["__sp_f003"],
  "metrics": [
    {
      "field": "__sp_f004",
      "function": "sum",
      "as": "__sp_m001"
    },
    {
      "function": "count",
      "mode": "rows",
      "as": "__sp_m002"
    },
    {
      "field": "__sp_f004",
      "function": "average",
      "as": "__sp_m003"
    }
  ],
  "sort": [
    {
      "field": "__sp_m001",
      "direction": "desc"
    }
  ]
}
```

没有 filter 或 sort 时省略对应可选字段。Compiler 不生成空对象占位。

### 8.4 生成 output steps

```json
[
  {
    "id": "project_output",
    "op": "project_columns",
    "input": "summarize",
    "fields": []
  },
  {
    "id": "create_output_sheet",
    "op": "create_sheet",
    "sheet": "城市经营汇总"
  },
  {
    "id": "write_output",
    "op": "write_table",
    "input": "project_output",
    "sheet": "城市经营汇总",
    "anchor": "A1"
  }
]
```

工作簿保存由 Attempt Executor 的固定生命周期负责，不编译为 Agent 可见 `save_workbook` step。

## 9. Coverage

Compiler 生成内部 coverage，只用于证明编译没有遗漏冻结组件：

```json
[
  {
    "component_id": "valid_rows",
    "kind": "filter",
    "compiled_to": ["summarize.where.all[0]"]
  },
  {
    "component_id": "sales_revenue",
    "kind": "metric",
    "compiled_to": ["summarize.metrics[0]", "project_output.fields[1]"]
  }
]
```

编译完成必须满足：

- Acceptance 中每个业务组件恰好有一条 coverage。
- 每条 coverage 指向存在的内部字段。
- Internal Plan 没有未被 Task Request 或固定生命周期授权的业务操作。
- 输出列与 Acceptance Snapshot 完全一致。

Coverage 不替代独立 Validator。Validator 仍对实际输出逐分组复算。

## 10. Operation Registry 边界

当前系统有两套能力注册：

- `capabilities.DEFAULT_REGISTRY`：旧 Planner/Compiler 使用。
- `mvp.ATOMS/MOLECULES`：轻量 Runtime 使用。

第一阶段收敛为：

```text
task_types/*                 public Task Type contract
runtime/operations.py       internal Atom/Molecule registry
runtime/executor.py         internal plan executor
```

迁移方式：

1. 从 `mvp.py` 提取轻量 Operation 定义和执行器到内部 Runtime 模块。
2. 注册现有 `read_table`、`filter_rows`、`aggregate`、`sort_rows`、`create_sheet`、`write_table`，新增内部 `project_columns`。
3. 保留 `mvp.py` 兼容导入，但新 Agent Task Runtime 不调用 `run_plan()`、`validate_run()` 或其 Agent Plan 校验入口。
4. `capabilities.DEFAULT_REGISTRY`、旧 Planner、Recipe 和 Compiler 留在 legacy 包装层，不被新 Task Type Definition 引用。
5. Dynamic Transform 第一阶段不注册到 Agent Task Runtime。

## 11. 可复用与不可复用代码

### 11.1 直接复用

- `inspector.inspect_workbook()` 与 Header Candidate 数据。
- `workbook.tables` 中 read、filter、aggregate、sort、select/rename 纯表逻辑。
- `OpenPyxlEngine` 的工作簿打开、Sheet 创建和单元格写入。
- `sha256_file()` 文件 hash 逻辑。
- 受控工作副本原则。

### 11.2 提取后复用

- `mvp.py` 的轻量 Operation handlers。
- Molecule 的确定性展开逻辑。
- 执行记录中的 input/output row count。

### 11.3 不进入新路径

- `SemanticTask`、`HighLevelPlan`、旧 `ExecutionPlan`。
- `HybridPlanner`、`planning.compiler`、`planning.policy`。
- `DEFAULT_RECIPE_REGISTRY` 与业务 Recipe。
- 旧 `capabilities.DEFAULT_REGISTRY`。
- Agent 提交的 `requirements` 与检查列表。
- `mvp-run --plan --run-dir` 和 `mvp-validate --run-dir`。

## 12. Compiler 版本固定

Task 创建时固定：

```text
task_contract_version
compiler_version
validator_version
```

- 同一 Request Revision 的 Retry 必须复用已保存的 Internal Plan 和 `internal_plan_hash`，不重新编译。
- 新 Binding Revision 使用 Task 固定的 Compiler 版本重新编译。
- Runtime 升级后若无法加载 Task 固定版本，返回 `CAPABILITY_UNSUPPORTED + HUMAN_ACTION_REQUIRED`，不能用新 Compiler 静默替换。
- Compiler 语义变化提升 compiler version；内部重构但输出字节完全相同可以保留版本。

## 13. 错误边界

| 失败 | 归属 |
|---|---|
| Task Request 类型、枚举、引用不合法 | contract validation |
| 字段不存在或歧义 | field binding |
| 当前 Task Type 不支持业务操作 | capability unsupported |
| 已验证对象 hash 不一致 | internal error / input changed |
| Compiler 对合法冻结输入无法生成完整 coverage | internal error |
| Internal Plan 引用未注册 operation | internal error |
| Operation 执行参数因 Runtime 编译错误而失败 | internal error，不归咎 Agent |

Compiler 不把内部 `PLAN_INVALID` 暴露给 Agent。只有 Agent 可行动的公开契约错误才返回 Request Diagnostic。

## 14. 公开 CLI 收敛

Skill 只使用：

```text
sheetpilot task-types
sheetpilot task-run --request <request.json>
sheetpilot task-status --task-id <task-id>
```

主 Agent CLI 不再注册：

```text
capabilities
recipes
plan
compile
execute
validate
run
mvp-capabilities
mvp-run
mvp-validate
```

兼容命令实现暂时移动到 `sheetpilot.legacy_cli`，供旧测试和开发排障显式调用。Skill、`--help` 和 Agent-facing 测试不能看到 legacy 命令。

## 15. task-types 输出

```json
{
  "schema_version": "1.0",
  "task_types": [
    {
      "name": "summarize_table",
      "contract_version": "1.0",
      "input_schema": {},
      "binding_contract": {},
      "acceptance_schema": {},
      "supported_features": {
        "filter_operators": ["eq", "ne", "gt", "gte", "lt", "lte", "in"],
        "metric_functions": ["sum", "count", "average"],
        "count_modes": ["rows", "non_empty"],
        "sort_directions": ["asc", "desc"]
      },
      "minimal_example": {}
    }
  ]
}
```

这些字段全部从 `TaskTypeDefinition` 生成。Manifest 不手写重复支持列表。

## 16. 目录建议

```text
src/sheetpilot/
├── agent_api/
│   ├── cli.py
│   ├── errors.py
│   └── responses.py
├── task_types/
│   ├── base.py
│   └── summarize_table.py
├── task_runtime/
│   ├── service.py
│   ├── store.py
│   ├── state.py
│   ├── bindings.py
│   ├── acceptance.py
│   ├── compiler.py
│   └── publisher.py
├── runtime/
│   ├── operations.py
│   └── executor.py
└── legacy_cli.py
```

目录表达公开 Agent API、Task 编排、内部轻量执行和 legacy 兼容四个清晰边界。

## 17. 必须测试

```text
same frozen inputs → byte-identical plan and hash
different binding revision → different binding/plan hash, same acceptance hash
all accepted components → exactly one coverage entry
missing coverage → INTERNAL_ERROR before execution
dimension/metric display names → only appear in project_columns/output
count.rows → no source field binding
count.non_empty → requires source field binding
sort by component ID → resolves to internal symbol
unknown operation → cannot enter compiled plan
dynamic transform → absent from first-phase registry
legacy Planner/Recipe → never imported by Agent Task Runtime
task-types → schema, validation and example from one definition
dirty orders task → expected deterministic internal plan
```

## 18. Skill 影响

Skill 不再规划执行步骤。标准流程缩减为：

1. 查询 Task Type Contract。
2. 把用户语义翻译为 `summarize_table` Task Request。
3. 提交请求并处理 Binding/Recovery。
4. 引用 Runtime Evidence，独立给出语义判断。

Atom、Molecule、Plan、Workspace、Validator 和发布流程全部成为 Runtime 内部责任。
