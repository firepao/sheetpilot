# SheetPilot 109 原子能力运行时设计方案

状态：设计草案  
日期：2026-08-20  
适用范围：SheetPilot 当前 Agent Task Runtime 的能力扩展  
关联文档：`docs/current/18-deterministic-task-compiler-boundary-prototype-v1.md`

## 1. 背景

SheetPilot 当前对 Agent 暴露业务级 Task API。Agent 描述来源、过滤条件、维度、指标、输出和验收要求，Runtime 负责字段绑定、确定性编译、执行、验证、证据生成和原子发布。

当前实现已经具备可靠的任务边界，但内部执行能力仍主要围绕 `summarize_table` 固化：`read_table`、`summarize_by_dimension`、`project_columns`、`create_sheet` 和 `write_table` 等步骤直接连接具体实现。新增业务能力时，容易再次编写工作簿操作、数据处理、错误处理和验证逻辑。

Bread Excel Agent 提供了一个可参考的 Excel Action Space：将工作簿、工作表、单元格、范围、样式、公式、图表和数据分析拆成一组可组合操作。其价值在于能力拆分，而不是“109”这个固定数量，也不是将全部底层工具直接交给 LLM。

本方案在 SheetPilot 内部引入一套 Bread 风格的原子能力运行时，使业务 Task Type 只负责定义契约和编译组合，所有 Excel 与表格操作统一落到内部原子能力层。

## 2. 设计目标

### 2.1 核心目标

1. 保留现有业务级 Agent 接口：公开入口仍为 `task-types`、`task-run`、`task-status`。
2. 建立统一的内部原子能力目录，覆盖工作簿、工作表、范围、公式、样式、表格分析和高级 Excel 对象。
3. 业务 Task Type 不直接调用 openpyxl、pandas 或文件系统写入 API，只生成类型化内部计划。
4. 将业务计划确定性展开为可验证、可执行、可审计的原子计划。
5. 相同冻结输入和版本必须产生字节级一致的计划及 `plan_hash`。
6. 任何不完整、不可展开、不可执行或不能覆盖 Acceptance 的计划必须在写文件前失败。
7. 保留 SheetPilot 当前的工作副本、不可变 Attempt、独立验收、证据和原子发布机制。
8. 新增业务能力时优先组合已有原子能力，不重复实现底层操作。

### 2.2 非目标

1. 不把 109 个原子操作直接暴露为 Agent 工具。
2. 不允许 Agent 提交 Atomic Plan、DAG、步骤 ID、工作目录或物理列坐标。
3. 不原样复制 Bread 的函数名、`if/elif` 路由和隐式 `active_sheet`/`last_df_id` 状态。
4. 不要求第一阶段一次实现准确的 109 个操作。
5. 不用 LLM 生成或修复 Runtime 内部计划。
6. 不以计划自身声明的 coverage 代替独立结果验收。

## 3. 设计原则

### 3.1 公共接口保持业务语义

Agent 只表达“做什么”，例如：

```text
过滤审核通过且未取消的交易，按区域和产品类别汇总净销售额，按净销售额降序写入新工作表。
```

Agent 不表达：

```text
读取 G 列，调用 groupby，创建 Sheet，再逐格写入 A1:D20。
```

### 3.2 Compiler 是确定性程序

LLM 可以负责理解用户语义、构造 Task Request，以及在 Runtime 给出的完整候选集中选择 Field Binding。Compiler 只接受已验证、已冻结和已完成绑定的类型化输入，不做语义猜测。

### 3.3 原子能力是内部指令集

原子能力负责“怎样执行一个最小且稳定的操作”。Task Type Compiler 负责“哪些能力以什么顺序组合”。Runtime 负责“是否允许、安全且正确地执行”。

### 3.4 显式状态优于活动对象

每个操作显式引用 `workbook_ref`、`sheet_ref`、`table_ref` 或上游步骤输出。禁止依赖“最后打开的工作簿”“当前活动 Sheet”或“最后一个 DataFrame”。

### 3.5 验收独立于执行

Compiler coverage 证明“计划没有遗漏请求组件”；Oracle 验证“最终结果在业务上正确”。两者不能互相替代。

## 4. 目标架构

```text
Agent / LLM
    ↓
Agent-facing Task API
    ↓
Task Contract Validator
    ↓
Acceptance Snapshot + Field Binding
    ↓
Deterministic Business Compiler
    ↓
Composite Plan
    ↓
Deterministic Atomic Expander
    ↓
Atomic Plan
    ↓
Independent Plan Validator
    ↓
Atomic Runtime
    ↓
Workbook Adapter / Table Engine
    ↓
Temporary Artifact
    ↓
Acceptance Validator + Independent Oracle
    ↓
Runtime Evidence + Atomic Publisher
```

### 4.1 责任边界

| 组件 | 负责 | 不负责 |
|---|---|---|
| Agent | 理解用户、提交 Task Request、选择 Binding Candidate | 编写计划、操作 Excel、声明 Runtime Pass |
| Contract Validator | 请求结构、枚举、引用和组合合法性 | 字段语义猜测、执行 |
| Field Binding | 逻辑字段到工作簿物理字段的绑定 | 业务计算 |
| Business Compiler | Task Request 到 Composite Plan | 直接写文件、动态试错 |
| Atomic Expander | Composite Operation 到 Atomic Operation | 业务语义判断 |
| Plan Validator | 类型、依赖、效果、权限和 Acceptance coverage | 执行结果正确性 |
| Atomic Runtime | 执行已验证原子计划、记录事实 | 修改任务要求 |
| Oracle | 独立复算和检查最终业务结果 | 执行生产计划 |
| Publisher | 验证后无覆盖原子发布 | 修复结果 |

## 5. 领域术语

### 5.1 Task Type

Agent 可见的业务能力类型，例如 `summarize_table`、`clean_table`、`join_tables` 或 `create_report`。Task Type 拥有公开请求契约、绑定要求、Compiler 和 Acceptance Validator。

### 5.2 Composite Operation

表达有明确业务或数据处理语义、但可继续展开的内部操作，例如 `summarize_table_data`、`write_formatted_table`。它不是公共 Task Type，也不是最终执行单位。

### 5.3 Atomic Operation

Runtime 的最小稳定执行单位。它拥有明确输入、输出、前置条件、后置条件和副作用，并且不再由 Runtime 展开为其他已注册操作。

### 5.4 Composite Plan

Business Compiler 产生的类型化内部流程，由 Composite Operation 与必要控制节点组成，强调业务可读性。

### 5.5 Atomic Plan

Composite Plan 完全展开后的确定性执行表示，只包含已注册 Atomic Operation 和 Runtime 固定生命周期行为。

### 5.6 Capability Registry

Atomic Operation 的唯一事实来源，记录能力名称、版本、类型 Schema、效果、后端、实现和测试状态。

## 6. 计划模型

### 6.1 三层表示

```text
Task Request
  “按区域汇总净销售额”

Composite Plan
  read source → summarize → write formatted output

Atomic Plan
  table.read → table.filter → table.group → table.aggregate
  → table.sort → sheet.create → range.write → style.apply
```

### 6.2 Composite Plan 示例

```json
{
  "schema_version": "1.0",
  "compiler_version": "summarize-table/2.0",
  "steps": [
    {
      "id": "read_source",
      "op": "table.read",
      "args": {
        "sheet": "交易流水",
        "header_row": 1,
        "columns": {
          "__sp_f001": "B",
          "__sp_f002": "D",
          "__sp_f003": "G"
        }
      }
    },
    {
      "id": "summarize",
      "op": "table.summarize",
      "args": {
        "table": {"$ref": "read_source.table"},
        "filters": [{"field": "__sp_f001", "operator": "eq", "value": "通过"}],
        "group_by": ["__sp_f002"],
        "metrics": [{"function": "sum", "field": "__sp_f003", "as": "__sp_m001"}],
        "sort": [{"field": "__sp_m001", "direction": "desc"}]
      }
    },
    {
      "id": "write_output",
      "op": "table.write_formatted",
      "args": {
        "table": {"$ref": "summarize.table"},
        "sheet": "区域汇总",
        "anchor": "A1"
      }
    }
  ]
}
```

### 6.3 Atomic Plan 示例

```json
{
  "schema_version": "1.0",
  "compiler_version": "summarize-table/2.0",
  "atomic_registry_version": "1.0",
  "task_id": "task-...",
  "request_revision": 1,
  "input_sha256": "...",
  "acceptance_hash": "...",
  "binding_hash": "...",
  "steps": [
    {
      "id": "a001",
      "origin": {"composite_step": "read_source"},
      "op": "table.read",
      "args": {
        "workbook": {"$ref": "runtime.working_workbook"},
        "sheet": "交易流水",
        "header_row": 1,
        "columns": {"__sp_f001": "B", "__sp_f002": "D", "__sp_f003": "G"}
      }
    },
    {
      "id": "a002",
      "origin": {"composite_step": "summarize"},
      "op": "table.filter",
      "args": {
        "table": {"$ref": "a001.table"},
        "conditions": [{"field": "__sp_f001", "operator": "eq", "value": "通过"}]
      }
    },
    {
      "id": "a003",
      "origin": {"composite_step": "summarize"},
      "op": "table.group",
      "args": {"table": {"$ref": "a002.table"}, "fields": ["__sp_f002"]}
    },
    {
      "id": "a004",
      "origin": {"composite_step": "summarize"},
      "op": "table.aggregate",
      "args": {
        "groups": {"$ref": "a003.groups"},
        "metrics": [{"function": "sum", "field": "__sp_f003", "as": "__sp_m001"}]
      }
    },
    {
      "id": "a005",
      "origin": {"composite_step": "summarize"},
      "op": "table.sort",
      "args": {
        "table": {"$ref": "a004.table"},
        "keys": [{"field": "__sp_m001", "direction": "desc"}]
      }
    },
    {
      "id": "a006",
      "origin": {"composite_step": "write_output"},
      "op": "sheet.create",
      "args": {"workbook": {"$ref": "runtime.working_workbook"}, "name": "区域汇总"}
    },
    {
      "id": "a007",
      "origin": {"composite_step": "write_output"},
      "op": "range.write_table",
      "args": {
        "workbook": {"$ref": "runtime.working_workbook"},
        "sheet": {"$ref": "a006.sheet"},
        "anchor": "A1",
        "table": {"$ref": "a005.table"}
      }
    },
    {
      "id": "a008",
      "origin": {"composite_step": "write_output"},
      "op": "style.apply_table_default",
      "args": {
        "workbook": {"$ref": "runtime.working_workbook"},
        "range": {"$ref": "a007.written_range"}
      }
    }
  ],
  "effects": {
    "read_sheets": ["交易流水"],
    "create_sheets": ["区域汇总"],
    "write_targets": ["区域汇总!A1"]
  },
  "coverage": []
}
```

`workbook.open`、`workbook.save` 和 `workbook.close` 不必作为普通业务步骤。工作副本打开、临时输出保存和句柄关闭属于 Attempt Executor 的固定生命周期，防止 Compiler 漏掉保存或将文件写到未授权路径。只有在确实需要多工作簿或中途持久化语义时，才引入受限制的生命周期原子操作。

## 7. 原子能力目录

“109”是版本代号和能力建设目标，不是不可变的函数数量。最终目录以原子边界、可组合性和验证能力为准。

### 7.1 工作簿与工作表

```text
workbook.inspect
workbook.list_sheets
workbook.validate_structure
sheet.inspect
sheet.create
sheet.delete
sheet.rename
sheet.copy
sheet.set_visibility
```

### 7.2 单元格、范围与结构

```text
cell.read
cell.write
cell.clear
range.read
range.write
range.write_table
range.append_rows
range.copy
range.clear
range.merge
range.unmerge
rows.insert
rows.delete
columns.insert
columns.delete
```

### 7.3 公式

```text
formula.read
formula.write
formula.fill
formula.copy
formula.inspect_dependencies
formula.find_errors
```

### 7.4 样式与布局

```text
style.apply
style.copy
style.apply_table_default
number_format.apply
column.set_width
row.set_height
freeze_panes.set
auto_filter.set
protection.set
```

### 7.5 内存表格处理

```text
table.read
table.select
table.filter
table.group
table.aggregate
table.sort
table.join
table.concat
table.pivot
table.melt
table.deduplicate
table.fill_missing
table.rename_fields
table.describe
table.value_counts
table.count
table.unique
```

### 7.6 Excel 对象

```text
excel_table.create
chart.create
chart.add_series
chart.set_categories
chart.inspect
validation.create
conditional_format.create
named_range.create
comment.create
hyperlink.create
image.insert
```

### 7.7 第一阶段不纳入核心

- PDF 操作：属于文档摄取边界，不属于 Excel 原子运行时。
- `system.reset`、`system.close_files`：属于 Runtime 生命周期管理。
- Bread 的 `workbook_get_item`/`sheet.activate`：依赖隐式活动状态。
- 任意 Python/pandas 表达式：破坏确定性和安全边界。
- 依赖桌面 Excel 的公式计算桥：单独作为受控后端能力评估。

## 8. Capability Registry

### 8.1 注册定义

```python
@atomic_operation(
    name="range.write_table",
    version="1.0",
    input_model=WriteTableInput,
    output_model=WriteTableOutput,
    effects={"workbook_mutation", "range_write"},
    backend="openpyxl",
    reversible=True,
)
def write_table(context: AtomicContext, value: WriteTableInput) -> WriteTableOutput:
    ...
```

### 8.2 每个操作必须声明

| 字段 | 含义 |
|---|---|
| `name` | 稳定的领域操作名 |
| `version` | 行为语义版本 |
| `input_model` | 类型化输入及约束 |
| `output_model` | 可供下游引用的结构化输出 |
| `preconditions` | 执行前必须成立的事实 |
| `postconditions` | 成功后保证成立的事实 |
| `effects` | 读取、修改、创建、删除等副作用 |
| `backend` | openpyxl、table-engine 或其他适配器 |
| `reversible` | 是否支持事务内撤销 |
| `implementation` | 唯一执行实现 |

### 8.3 单一事实来源

Registry 自动生成：

- Atomic Plan Schema；
- Plan Validator 的操作和类型目录；
- 内部能力清单与版本指纹；
- 文档和测试覆盖矩阵；
- 未注册实现、无实现定义和版本冲突报告。

禁止同时维护“JSON 工具定义 + `if/elif` 路由 + 独立文档统计”三套事实来源。

## 9. Compiler 设计

### 9.1 Compiler 输入

```text
Validated Task Request
+ Acceptance Snapshot
+ Binding Snapshot
+ input_sha256
+ task_contract_version
+ compiler_version
+ atomic_registry_version
```

Compiler 不接受：自然语言补充、未解决字段、Agent Plan、运行目录、时间戳或随机 ID。

### 9.2 编译阶段

```text
1. Normalize：将请求转换为类型化业务 IR
2. Bind：把业务字段替换为稳定内部符号
3. Lower：Task Type 降级为 Composite Plan
4. Expand：Composite Operation 递归展开为 Atomic Plan
5. Analyze：计算依赖、effects 和 Acceptance coverage
6. Validate：独立 Plan Validator 检查
7. Canonicalize：稳定排序和规范化序列化
8. Hash：生成 internal_plan_hash
```

### 9.3 确定性规则

- 步骤 ID 由稳定遍历顺序生成，不使用 UUID。
- 字段符号按 Binding Slot 顺序生成，例如 `__sp_f001`。
- 指标符号按请求顺序生成，例如 `__sp_m001`。
- 可选字段为空时省略，不输出语义相同但字节不同的空结构。
- JSON 使用固定键顺序和规范化编码。
- Compiler 不读取当前时间、环境变量或不属于输入快照的文件状态。
- 同一 Task Revision 的 Retry 复用已保存 Atomic Plan，不重新编译。

### 9.4 Compiler 正确性义务

每个 Task Type Compiler 必须证明：

1. 请求中的每个 Acceptance 组件都有且只有一个有效 coverage 映射。
2. 所有读取字段来自 Binding Snapshot。
3. 所有写入目标来自 Task Request 或 Runtime 固定策略。
4. 没有超出 Task Contract 的额外业务操作。
5. Composite Plan 能完全展开，不遗留未知操作。
6. Atomic Plan 的所有引用存在并且类型兼容。
7. 计划效果不覆盖输入文件或非授权范围。

## 10. Plan Validator

Plan Validator 必须独立于 Compiler 实现，至少执行以下检查。

### 10.1 注册和 Schema 检查

- 每个 `op` 已注册且版本可用；
- 参数满足操作输入模型；
- 不存在未知参数；
- 输出引用使用已声明字段。

### 10.2 依赖与类型检查

- 步骤 ID 唯一；
- `$ref` 指向已存在的上游步骤或 Runtime 输入；
- 引用图无环；
- 上游输出类型与下游输入类型兼容；
- 不允许隐式活动工作簿、Sheet 或 DataFrame。

### 10.3 效果和安全检查

- 输入文件只读；
- 写入只发生在 working copy；
- 输出 Sheet 和目标范围符合 Task Contract；
- 删除、覆盖、宏处理等高风险效果必须被 Task Type 显式授权；
- 没有任意表达式、任意代码或逃逸路径。

### 10.4 Acceptance coverage 检查

- 每个 required filter 都映射到具体过滤条件；
- 每个 required dimension 都进入 group/project 输出；
- 每个 required metric 都进入 aggregate/project 输出；
- 每个 required sort 都进入排序操作；
- 最终输出列、顺序和名称与 Acceptance Snapshot 一致。

缺少任何 coverage 时返回 Runtime 内部错误，不进入执行阶段，也不能归咎 Agent。

## 11. Atomic Runtime

### 11.1 Atomic Context

```python
AtomicContext(
    working_workbook=...,
    input_identity=...,
    task_identity=...,
    allowed_effects=...,
    results=TypedResultStore(),
    audit=ExecutionJournal(),
)
```

### 11.2 执行规则

1. 仅执行通过 Plan Validator 的计划。
2. 每一步执行前再次校验动态前置条件。
3. 每一步输出经过输出模型校验后才进入 Result Store。
4. 每一步记录开始、结束、输入摘要、输出摘要、状态变化和错误码。
5. 禁止将 Worksheet、DataFrame 等不可序列化对象直接写入证据；使用受控引用。
6. 失败立即停止当前事务；默认不发布任何部分结果。
7. 文件保存、关闭和临时产物管理由 Attempt Executor 固定生命周期负责。

### 11.3 结构化结果

```json
{
  "step_id": "a007",
  "op": "range.write_table",
  "status": "success",
  "result": {
    "sheet": "区域汇总",
    "range": "A1:D18",
    "rows_written": 18,
    "columns_written": 4,
    "headers": ["区域", "产品类别", "净销售收入", "交易数量"]
  },
  "state_delta": {
    "workbook_modified": true
  }
}
```

原子操作不得只返回难以机器验证的自然语言字符串。

## 12. 执行、验收与发布

```text
1. 固定输入文件身份和 hash
2. 创建 Attempt 与 working copy
3. 加载已验证 Atomic Plan
4. 执行原子步骤
5. 保存 temporary artifact
6. 验证输入 hash 未变化
7. 执行结构、业务和系统验收
8. 独立 Oracle 从源文件复算关键结果
9. 生成 Runtime Evidence
10. no-replace 原子发布
11. 校验 published hash 与 validated hash 一致
```

交付条件保持：

```text
state = RUNTIME_PASS
artifact_integrity = MATCHED
delivery_valid = true
```

### 12.1 验收分层

| 层次 | 检查内容 |
|---|---|
| Plan validation | 计划完整、可执行、安全、覆盖 Acceptance |
| Operation postconditions | 每个原子步骤兑现自身输出和状态承诺 |
| Structural validation | 工作簿可打开、目标 Sheet/范围/对象存在 |
| Business acceptance | 过滤、维度、指标、排序和输出符合冻结契约 |
| Independent Oracle | 独立读取源文件并复算关键结果 |
| Publication validation | 已验证文件与发布文件 hash 一致 |

## 13. 版本管理

Task 创建时固定：

```text
task_contract_version
compiler_version
atomic_registry_version
validator_version
oracle_version
```

版本规则：

- 原子操作输入、输出、前置条件或副作用语义变化时提升操作版本。
- Composite 展开结果变化时提升 Expander/Compiler 版本。
- 相同版本必须保持确定性输出。
- Retry 使用原计划；Binding Revision 使用 Task 固定 Compiler 重新编译。
- Runtime 无法加载固定版本时返回 `CAPABILITY_UNSUPPORTED`，不得静默切换新版。

## 14. 错误模型

| 错误 | 阶段 | 对外归属 |
|---|---|---|
| 请求字段、枚举、引用无效 | contract validation | Agent 可修订 |
| 字段不存在或歧义 | field binding | Agent 选择候选或人工处理 |
| Task Type 不支持请求能力 | capability negotiation | `CAPABILITY_UNSUPPORTED` |
| Compiler 对合法输入无法生成 coverage | compilation | `INTERNAL_ERROR` |
| Composite Operation 无法完全展开 | expansion | `INTERNAL_ERROR` |
| Atomic Operation 未注册或类型不匹配 | plan validation | `INTERNAL_ERROR` |
| 动态前置条件失败 | execution | 稳定执行错误码 |
| Oracle 结果不匹配 | acceptance | Attempt 失败，不发布 |
| 输出冲突或无法原子发布 | publication | 人工处理或新任务 |

内部 Plan 错误不能包装成普通 Agent 参数错误。

## 15. 目录建议

```text
src/sheetpilot/
├── task_api/
│   ├── contract.py
│   ├── runtime.py
│   └── inventory.py
├── task_types/
│   ├── base.py
│   └── summarize_table.py
├── compiler/
│   ├── business_ir.py
│   ├── composite_plan.py
│   ├── atomic_plan.py
│   ├── expander.py
│   ├── validator.py
│   └── canonical.py
├── atomic/
│   ├── registry.py
│   ├── models.py
│   ├── runtime.py
│   ├── journal.py
│   └── operations/
│       ├── workbook.py
│       ├── sheet.py
│       ├── range.py
│       ├── formula.py
│       ├── style.py
│       ├── table.py
│       └── chart.py
├── backends/
│   ├── openpyxl_adapter.py
│   └── table_engine.py
└── acceptance/
    ├── validator.py
    └── oracle.py
```

目录迁移应渐进进行，不要求第一阶段立即移动现有模块。

## 16. 分阶段实施

### Phase 0：基线和能力盘点

交付物：

- 当前 Task API、Compiler、Runtime 和测试基线；
- Bread 能力到 SheetPilot 领域操作的映射表；
- 原子边界评审规则；
- 当前 `summarize_table` 的 golden plan 和结果夹具。

退出条件：现有测试全绿，当前 plan hash 和输出结果已固定为迁移基线。

### Phase 1：最小 Atomic Runtime

实现：

```text
table.read
table.filter
table.group
table.aggregate
table.sort
table.select
sheet.create
range.write_table
```

同时实现 Registry、类型模型、Result Store、Execution Journal 和 Plan Validator。

退出条件：每个操作具备单元测试、Schema 测试、负向测试和结构化结果。

### Phase 2：迁移 summarize_table

- 现有 Task Contract 保持不变；
- Business Compiler 生成 Composite Plan；
- Expander 生成 Atomic Plan；
- Runtime 不再直接执行 `summarize_by_dimension` 和 `_write_table`；
- 新旧实现针对同一夹具进行差分比较。

退出条件：Agent Contract、独立 Oracle、Artifact Integrity 和确定性 hash 测试全部通过。

### Phase 3：基础 Excel 编辑能力

加入：

```text
cell.read/write
range.read/write/copy/clear
rows/columns insert/delete
formula.write/fill
style.apply
number_format.apply
column.set_width
row.set_height
freeze_panes.set
auto_filter.set
```

退出条件：工作簿 fidelity 测试覆盖 `.xlsx` 和 `.xlsm`，未授权部件保持不变。

### Phase 4：新增业务 Task Type

建议顺序：

1. `clean_table`
2. `join_tables`
3. `pivot_table`
4. `create_report`
5. `create_dashboard`

每个 Task Type 只增加公开契约、Compiler、Acceptance 和 Oracle；底层操作必须优先复用。

### Phase 5：高级 Excel 对象

逐步加入图表、Excel Table、数据验证、条件格式、命名范围、批注和图片。每个能力必须同时提供 Registry 定义、后端实现、计划验证规则、读取回验能力和工作簿 fidelity 测试。

## 17. 测试策略

### 17.1 原子操作测试

- 正常输入；
- 边界值；
- 非法输入；
- 前置条件失败；
- 后置条件；
- 对工作簿的最小差异；
- `.xlsm` 宏部件保留。

### 17.2 Compiler 测试

- 相同冻结输入产生字节级相同计划；
- 每个业务组件有唯一 coverage；
- `count.rows` 不产生字段绑定；
- `count.non_empty` 必须产生字段绑定；
- 输出名称只在最终 projection/write 阶段出现；
- 未支持组合在编译前拒绝。

### 17.3 Plan Validator 负向测试

- 删除一个 required filter；
- 删除一个 metric；
- 引用不存在的步骤；
- 制造依赖环；
- 将文本字段传给 sum；
- 使用未注册操作；
- 写入输入文件；
- 写入未授权 Sheet；
- 声明与实际 effects 不一致。

### 17.4 属性和变异测试

- 随机生成合法 Task Request，所有计划都应通过类型与依赖检查；
- 对合法计划随机删除、交换或替换步骤，Validator 或 Acceptance 必须失败；
- 对字段顺序、Unicode 表头和空值分布做组合测试。

### 17.5 端到端测试

```text
Task Request
→ Binding
→ Composite Plan
→ Atomic Plan
→ Temporary Artifact
→ Independent Oracle
→ Runtime Evidence
→ Atomic Publication
```

最终通过条件仍由 Agent-facing black-box 测试决定。

## 18. 可观测性与证据

Attempt Evidence 增加：

```json
{
  "compiler_version": "summarize-table/2.0",
  "atomic_registry_version": "1.0",
  "composite_plan_hash": "...",
  "internal_plan_hash": "...",
  "operation_counts": {
    "table.read": 1,
    "table.filter": 1,
    "table.group": 1,
    "table.aggregate": 1,
    "range.write_table": 1
  },
  "coverage_hash": "...",
  "validated_artifact_sha256": "...",
  "published_sha256": "..."
}
```

证据中记录稳定摘要，不记录完整敏感表格数据、Python 对象地址或不必要的单元格内容。

## 19. 风险与控制

| 风险 | 控制措施 |
|---|---|
| 原子过细导致计划巨大 | 保留 Composite Plan；Expander 可生成批量范围操作而非逐单元格操作 |
| 原子过粗导致复用不足 | 原子边界评审：单一效果、稳定类型、可独立验证 |
| Registry 与实现漂移 | 装饰器注册和启动时一致性检查，单一事实来源 |
| Compiler 漏业务条件 | Acceptance coverage + 变异测试 + 独立 Oracle |
| 隐式状态导致不可重放 | 所有资源显式引用，禁止 active/last 状态 |
| pandas/openpyxl 语义差异 | 统一 TableData 类型和后端契约，差分测试 |
| 大量逐格操作性能差 | `range.write`、`range.write_table` 等批量原子操作 |
| 计划合法但结果错误 | 操作后置条件、业务 Validator、独立 Oracle 三重检查 |
| 能力数量成为形式指标 | 以 Task coverage、正确率、fidelity 和复用率衡量，不以恰好 109 个验收 |

## 20. 架构决策

1. **Agent 接口保持业务级。** 原子能力永远是 Runtime 内部实现。
2. **Compiler 不使用 LLM。** LLM 只参与 Task Request 和必要的 Binding 语义选择。
3. **计划分为 Composite 与 Atomic 两层。** 前者保证业务可读性，后者保证执行确定性。
4. **Capability Registry 是唯一事实来源。** 不复制 Bread 的多份工具声明机制。
5. **生命周期操作由 Attempt Executor 管理。** 普通业务计划不负责打开、保存、关闭和发布文件。
6. **Plan Validator 独立于 Compiler。** Compiler 不能自行证明自己正确。
7. **Oracle 独立于生产执行路径。** Coverage 不能替代最终结果复算。
8. **“109”是能力版本名称。** 实际操作数量由合理的原子边界决定。

## 21. 完成定义

109 原子能力运行时可以进入稳定版本，必须同时满足：

- Agent 可见命令仍只有 `task-types`、`task-run`、`task-status`；
- `summarize_table` 已完全通过 Atomic Runtime 执行；
- 业务 Compiler 和原子操作实现之间不存在直接 openpyxl/pandas 调用；
- Registry、Atomic Plan、Plan Validator 和结构化执行日志稳定；
- 相同冻结输入生成相同计划与 hash；
- Acceptance coverage 对每个冻结组件完整且唯一；
- 计划变异测试能够拦截遗漏、错序、错类型和越权写入；
- 独立 Oracle、Agent Contract 和 workbook fidelity 测试通过；
- 输出满足 `RUNTIME_PASS`、`artifact_integrity=MATCHED`、`delivery_valid=true`；
- 新增一个业务 Task Type 可以只通过契约、Compiler、Acceptance 和 Oracle 完成，不重复实现底层 Excel 写入逻辑。

## 22. 总结

SheetPilot 109 版本不是“向 LLM 暴露 109 个 Excel 工具”，而是建立一套 Runtime 内部原子指令集：

```text
业务 Task API
    ↓
确定性 Business Compiler
    ↓
Composite Plan
    ↓
Atomic Expander + Plan Validator
    ↓
Atomic Capability Runtime
    ↓
统一后端、验证、证据和原子发布
```

业务能力只描述业务契约并编译组合；原子能力只执行稳定的最小操作；Runtime 负责生命周期、安全、验收和发布。这样既保留 SheetPilot 当前的可审计和确定性优势，又获得 Bread 原子能力模型带来的覆盖范围和复用能力。
