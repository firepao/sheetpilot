# SheetPilot 原子能力与分子能力架构及详细设计 V1

## 1. 文档目的

本文根据脏订单两次测试及后续架构讨论，重新定义 SheetPilot 的能力分层、组合模型、规划职责和执行接口，并作为后续重构的目标设计。

本文重点解决以下问题：

1. 已有 XLSX CLI/MCP 与 SheetPilot 原子能力是否重复建设；
2. 原子能力和分子能力的准确边界；
3. 分子能力如何保持通用、长期复用，而不是绑定脏订单等具体业务；
4. 分子能力如何真正修改 Excel，而不只返回内存中的 `TableData`；
5. Planner 是否必要，以及覆盖判断和组合计划应如何实现；
6. 如何保证路由、参数绑定、执行和任务级验收使用同一事实来源。

本文替代 `07`、`08` 中将 Composite 偏向“业务模块或内存处理函数”的表述。已有文档中的安全、工作副本、禁止覆盖原文件、独立验收和动态脚本限制继续有效。

## 2. 核心结论

SheetPilot 采用以下五层模型：

```text
Agent / Skill
  -> Requirement 与字段语义映射
  -> Coverage Planner
  -> Composed Plan Builder
  -> Recipe / Molecule / Atom / Dynamic Transform
  -> Executor（CLI 或 MCP 适配）
  -> XLSX Validator
```

能力层级定义如下：

```text
Atom（原子能力）
  单一、确定、可独立执行的 Excel 操作，优先直接复用成熟 XLSX CLI/MCP。

Molecule（分子能力）
  由多个 Atom 构成的参数化、可展开、跨业务复用的 Excel 操作模式。
  Molecule 可以读取、变换和写入工作簿，也可以创建公式、指标、检查区块和图表。

Recipe（配方）
  长期稳定的完整交付流程。只有输入、口径、布局和验收都稳定时才注册。

Dynamic Transform
  固定能力无法覆盖时，由 Agent 生成的受限表格数据变换。

Dynamic Task
  固定能力无法覆盖的特殊工作簿编辑。风险高，不进入当前公开 MVP。
```

关键原则：

- 不重复实现成熟 XLSX CLI/MCP 已具备的原子操作；SheetPilot 用适配器将其注册进统一目录。
- 分子能力不是行业专用脚本，也不是单个黑盒 Python handler。
- 分子能力必须能展开为可检查的子 DAG，明确读写范围、副作用和验证器。
- 分子能力既可以返回内存数据，也必须能够声明并执行工作簿写入。
- Agent 负责理解意图和提供语义参数，不负责手写完整 DAG。
- Planner 不猜测 Excel 实现细节；Coverage Planner 选能力，Composed Plan Builder 确定性装配。
- PNG 预览属于独立 Renderer Pipeline，不进入 Excel 核心能力覆盖和 MVP 成败判定。

## 3. 能力分层边界

### 3.1 原子能力判定标准

满足以下条件的操作定义为 Atom：

1. 只有一个主要动作；
2. 参数可以用严格 Schema 完整描述；
3. 输入和输出类型明确；
4. 副作用范围可以在执行前估计、执行后精确记录；
5. 不包含可选业务流程或多阶段控制逻辑；
6. CLI/MCP 单次调用即可完成。

例如 `write_table` 是 Atom；“按区域汇总并写到经营总览、排序和套用样式”不是 Atom。

### 3.2 分子能力判定标准

满足以下条件的操作定义为 Molecule：

1. 由两个或更多 Atom 形成稳定组合；
2. 组合表达跨任务复用的 Excel 语义，而不是某个测试场景；
3. Agent 只需提供字段、规则、目标位置和少量策略参数；
4. 能确定性展开为子计划；
5. 展开后的每个 Atom 仍可单独审计；
6. 至少在多个任务中有合理复用价值。

推荐命名强调通用动作：

```text
summarize_by_dimension
add_formula_metrics
compute_scalar_metrics
write_metric_block
build_check_block
create_chart_block
classify_rows
add_source_trace
```

不推荐命名绑定评测场景：

```text
build_dirty_orders_report
clean_ecommerce_orders
make_u3_test_workbook
```

### 3.3 Recipe 判定标准

完整流程只有同时满足以下条件才提升为 Recipe：

- 长期重复出现；
- 输入字段契约稳定；
- 业务公式与统计口径稳定；
- Sheet 布局稳定；
- 验收条件稳定；
- 参数化不会使 Recipe 退化成通用编程语言。

脏订单目前只是评测场景，不应注册为 Recipe。

## 4. 总体架构

```text
用户任务
  |
  v
Inspector ---------> WorkbookProfile
  |
  v
Semantic Mapper ---> TaskSpec + RequirementSet + FieldBindings
  |
  v
Coverage Planner
  |  判断 Recipe/Molecule/Atom 能否覆盖数量、公式、Sheet 等约束
  v
Composition Request
  |
  v
Composed Plan Builder
  |  选择分子、补充原子、绑定参数、展开子 DAG、合并依赖
  v
ExecutionPlan
  |
  +--> Policy Gate
  |
  v
Executor
  |  Atom Adapter -> 内置实现 / XLSX CLI / MCP
  v
temporary_output.xlsx
  |
  v
Task-level Validator ---> 发布 output.xlsx 或拒绝交付

独立可选流程：output.xlsx -> Renderer -> preview.png -> Visual Validator
```

### 4.1 Skill 的职责

Skill 只负责：

- 指导 Agent 检查工作簿；
- 生成合法 TaskSpec、RequirementSet 和 FieldBindings；
- 调用规划、执行和验证命令；
- 根据结构化错误补充参数或报告不支持。

Skill 不应：

- 手工维护能力列表；
- 让 Agent 猜 JSON 字段；
- 让 Agent手写完整执行 DAG；
- 将局部执行 PASS 描述为完整任务 PASS；
- 在 Excel 核心阶段承诺 PNG。

### 4.2 CLI、MCP 与注册表

CLI 和 MCP 是调用协议，不是新的能力层。统一能力目录是唯一事实来源：

```text
Capability Catalog
  -> CLI manifest / invoke
  -> MCP tools / call
  -> Planner 候选能力
  -> Compiler 参数与类型检查
  -> Executor Adapter
  -> 契约测试
```

已有成熟 XLSX CLI/MCP 时，AtomDefinition 的 executor 指向适配器：

```python
AtomDefinition(
    id="write_table",
    executor=CliAtomAdapter(command="xlsx write-table"),
    # 或 executor=McpAtomAdapter(tool="xlsx.write_table")
)
```

SheetPilot 不应为暴露接口而复制一套相同工作簿逻辑。只有现有接口无法满足工作副本、授权范围、结构化结果和审计要求时，才补自研实现。

## 5. 公共类型系统

仅有 `TableData` 无法支持可组合的工作簿编辑。目标模型至少包含：

```text
WorkbookRef   工作副本引用
SheetRef      工作表引用
TableRef      带表头和数据来源的逻辑表
RangeRef      已写入的矩形区域
ColumnRef     表或区域中的列
CellRef       单元格引用
ScalarRef     有名称、有来源的标量
MetricSetRef  一组标量指标
ChartRef      图表对象引用
CheckBlockRef 检查区块引用
```

### 5.1 引用而不是裸值

计划步骤之间传递引用：

```json
{
  "kind": "ScalarRef",
  "id": "valid_row_count",
  "value_type": "number",
  "runtime_value": 92,
  "cell": "'异常检查'!B3",
  "provenance": {
    "source": "clean_detail",
    "function": "count_if",
    "field": "清洗状态"
  }
}
```

`runtime_value` 供执行分支和独立验证使用，`cell` 供 Excel 公式引用。两者可以同时存在，但必须记录来源和一致性检查。

### 5.2 输出模式

涉及计算的能力统一支持显式输出模式：

```text
runtime  只产生运行时结果，不写 Excel
value    将静态值写入 Excel
formula  写入真实 Excel 公式
both     同时保留运行时结果和公式输出，并验证一致性
```

默认规则：

- 用户明确要求真实公式时必须使用 `formula` 或 `both`；
- KPI、派生列、对账检查优先使用 `both`；
- 图表源数据可以使用静态聚合值，但必须可独立复算；
- 不得用 Python 静态值冒充 Excel 公式。

### 5.3 副作用声明

每个能力声明副作用并由分子能力汇总：

```text
read_workbook
create_sheet
write_values
write_formulas
write_styles
create_chart
modify_layout
```

分子展开前计算预计副作用和预算，展开后取所有 Atom 副作用的并集。执行器只允许写入计划授权范围。

## 6. 原子能力目录与详细设计

原子能力按职责分类，而不是按业务场景分类。以下是目标 MVP 目录；只有完成 Schema、适配器、审计和契约测试的能力才能标记为 `AVAILABLE`。

### 6.1 检查与定位类

#### `inspect_workbook`

- 输入：文件路径和检查预算。
- 输出：`WorkbookProfile`。
- 实现：读取 Sheet、有效区域、候选表头、字段类型、公式和图表数量、风险对象。
- 副作用：无。
- 验证：输入哈希、Sheet 数和 OOXML 完整性。

#### `resolve_table`

- 输入：Sheet、表头行、字段名或候选区域。
- 输出：`TableRef`。
- 实现：将语义字段绑定到确定列，拒绝重复表头和低置信度歧义。
- 副作用：无。
- 价值：避免每个分子重复猜表头和列地址。

#### `resolve_target`

- 输入：目标 Sheet、锚点、预计形状、冲突策略。
- 输出：授权的 `RangeRef` 草案。
- 实现：检查名称、边界、已有对象和写入冲突。
- 副作用：无。

### 6.2 数据读取类

#### `read_table`

- 输入：`TableRef`、字段列表、最大行数。
- 输出：`TableData`，必须保留源 Sheet、源行号和字段 provenance。
- 实现：有界读取，不允许无约束整表加载；保持数字、日期、布尔和公式文本类型。
- 副作用：`read_workbook`。

#### `read_range`

- 输入：确定的 `RangeRef`。
- 输出：二维值或 `TableData`。
- 用途：检查块、局部模板和非标准表头场景。
- 约束：范围必须来自 Inspector 或 Planner 授权。

### 6.3 表格变换类

这些 Atom 默认只改变运行时数据，不直接写工作簿。

#### `select_columns`

- 支持选择、重排和重命名字段。
- 拒绝缺失字段和重复输出字段。

#### `filter_rows`

- 使用受控条件 AST；支持 `all/any` 和白名单操作符。
- 明确无效值策略，不使用任意 Python 表达式。

#### `sort_rows`

- 支持多字段稳定排序、空值位置和类型检查。

#### `derive_column`

- 使用注册模板计算运行时派生列。
- 首期模板：`add`、`subtract`、`multiply`、`safe_divide`、`coalesce`、日期年/月。
- 与 `write_formula_column` 区分：前者产生内存值，后者修改 Excel。

#### `aggregate`

- 支持多维度和多个指标。
- 首期函数：`sum`、`count`、`count_distinct`、`average`、`min`、`max`。
- 必须输出参与行数、忽略值数和分组数。

#### `normalize_values`

- 按显式规则标准化文本、日期、枚举和数字。
- 不能模糊猜测歧义日期或币种。

### 6.4 标量统计类

标量是当前实现缺失的重要中间类型。

#### `compute_scalar`

- 输入：`TableData/TableRef/RangeRef`、函数、字段、可选条件。
- 输出：`ScalarRef`。
- 函数：`count_rows`、`count_nonblank`、`count_if`、`count_distinct`、`sum`、`sum_if`、`average`、`min`、`max`。
- 实现：运行时独立计算，记录来源、参与行数、空值和数据类型。
- 副作用：无。

#### `write_scalar`

- 输入：`ScalarRef`、目标 `CellRef`、标签位置、输出模式和数字格式。
- 输出：包含单元格位置的 `ScalarRef`。
- 实现：`value` 写静态值；`formula` 根据来源生成白名单公式；`both` 写公式并保留运行时值供验证。
- 副作用：`write_values` 或 `write_formulas`。

#### `compare_scalars`

- 输入：左右 `ScalarRef`、运算符和容差。
- 输出：差异标量和布尔结果。
- 运算符：`eq`、`approx_eq`、`lte`、`gte`。
- 副作用：无；Excel 中的展示由分子能力负责。

### 6.5 工作表和区域写入类

#### `create_sheet`

- 创建新 Sheet，支持 `fail` 或受控 `reuse_empty` 冲突策略。
- MVP 默认禁止删除和覆盖已有 Sheet。

#### `write_table`

- 将 `TableData` 写到授权区域，返回精确 `RangeRef`。
- 保持数值和日期类型，不预先格式化为文本。

#### `write_values`

- 写入有界二维值，适合标题、标签和小型检查区块。
- 不接受任意无限范围。

#### `write_formula_column`

- 在表格或区域中按模板写入真实公式列。
- 参数使用字段语义，不接受任意公式源码。
- 返回扩展后的 `RangeRef` 和公式覆盖统计。

#### `write_formula_cells`

- 在一组明确单元格写入白名单公式模板。
- 用于 KPI 和检查区块，不用于大规模逐单元格自由编辑。

### 6.6 格式与布局类

#### `apply_style_preset`

- 对授权区域应用版本化样式预设。
- 预设与能力注册分离，但也必须版本化和可查询。

#### `set_number_format`

- 对列或区域设置货币、整数、小数、百分比、日期等受控格式。

#### `set_column_widths`

- 根据字段类型或有限样本设置宽度，禁止无界自动适应。

#### `freeze_panes`

- 设置冻结位置，写入布局变更记录。

#### `merge_cells`

- 仅允许在新建 Sheet 和明确授权区域内使用。
- 数据表区域默认禁止合并。

#### `add_conditional_format`

- 使用白名单规则，例如 FAIL 红色、负值警示、数据条。
- 不接受任意公式规则进入 MVP。

### 6.7 对象类

#### `create_chart`

- 输入：精确 `RangeRef`、分类字段、系列字段、图表类型、锚点和尺寸。
- 输出：`ChartRef`。
- 首期类型：column、bar、line、pie。
- 验证：真实图表对象数、系列和范围引用，而不是只看 XML 中存在图表文件。

#### `create_excel_table`

- 将写入区域转换成原生 Excel Table。
- 为结构化公式和可扩展图表提供稳定引用。
- 表名必须唯一且符合 Excel 规则。

### 6.8 保存与交付类

#### `save_workbook`

- 只保存到运行目录临时文件，不直接发布最终路径。
- 保存后重新打开，检查完整性。

#### `publish_workbook`

- 仅在任务级 Validator 通过后复制到最终输出路径。
- 发布不是普通计划 Atom，只能由 Orchestrator 调用。

## 7. 分子能力契约

### 7.1 MoleculeDefinition

```python
@dataclass(frozen=True)
class MoleculeDefinition:
    id: str
    version: str
    parameter_schema: dict
    input_ports: tuple[PortDefinition, ...]
    output_ports: tuple[PortDefinition, ...]
    requirement_patterns: tuple[RequirementPattern, ...]
    supported_engines: frozenset[str]
    estimated_effects: frozenset[str]
    required_validators: tuple[str, ...]
    expander: MoleculeExpander
```

与当前 `CapabilityDefinition(handler=...)` 的区别是：

- Atom 使用 `executor` 执行一个动作；
- Molecule 使用 `expander` 生成一组 Atom 节点和内部依赖；
- Executor 最终只执行展开后的 Atom 或受限动态步骤；
- Molecule ID、版本和展开记录保留在计划 provenance 中。

### 7.2 PlanFragment

```python
@dataclass(frozen=True)
class PlanFragment:
    nodes: tuple[PlanNode, ...]
    input_bindings: dict[str, Ref]
    output_bindings: dict[str, Ref]
    requirements_covered: tuple[CoverageClaim, ...]
    assertions: tuple[Assertion, ...]
    effects: frozenset[str]
```

分子展开器必须是确定性的：相同版本、参数和输入画像产生结构相同的 Fragment。不得调用 LLM、网络或执行任意代码。

### 7.3 分子能力的工作簿修改

Molecule 不直接绕过授权修改 WorkbookContext。它通过展开写入 Atom 获得修改能力：

```text
Molecule: add_formula_metrics
  -> resolve_target
  -> write_formula_column
  -> set_number_format
  -> formula_scan assertion
```

因此既能实现完整 Excel 修改，又保留：

- 原子级审计；
- 精确范围授权；
- 公式和样式验证；
- CLI/MCP 后端替换能力；
- 局部失败定位。

## 8. 分子能力分类与详细设计

### 8.1 `add_source_trace`

目的：为明细数据建立可追溯字段，不绑定脏订单业务。

关键参数：

```json
{
  "source": "source_table",
  "columns": [
    {"kind": "source_row", "as": "原始行号"},
    {"kind": "source_sheet", "as": "来源Sheet"}
  ],
  "target": {"sheet": "清洗明细", "anchor": "A1"}
}
```

展开：

```text
read_table -> derive trace columns -> create/reuse target sheet -> write_table
```

输出：`TableRef`、`RangeRef`。验证：源行号唯一性、范围覆盖和行数一致性。

### 8.2 `normalize_columns`

目的：用声明式规则标准化一组字段。

支持规则：trim、空白归一、大小写、枚举映射、显式日期格式、数值解析。规则按列配置，错误策略为 `mark/fail/keep_original`。

展开：

```text
read_table -> normalize_values -> 可选写入标准化字段 -> set_number_format
```

它不负责判断整行有效性，输出标准化结果和逐字段错误标记，供 `classify_rows` 使用。

### 8.3 `classify_rows`

目的：根据参数化规则生成状态和原因字段。

支持规则：required、比较、集合、日期合法性、唯一性和受控复合条件。每条规则必须包含 `id`、字段、条件、原因和严重级别。

展开：

```text
read/use TableData -> evaluate rule set -> add status/reason columns
-> 可选 write_table 或 write_formula_column
```

首期建议使用运行时计算后写值；当规则可以稳定映射为 Excel 公式时允许 `formula/both`。输出包含有效、异常、警告数量的 `MetricSetRef`。

### 8.4 `add_formula_metrics`

目的：根据字段关系向 Excel 表格增加一组真实公式派生列。

示例不是固定“利润业务”，而是模板参数化：

```json
{
  "target_table": "clean_detail_range",
  "metrics": [
    {
      "as": "利润",
      "template": "subtract",
      "arguments": {"left": "营收", "right": "成本"},
      "number_format": "#,##0.00"
    },
    {
      "as": "利润率",
      "template": "safe_ratio",
      "arguments": {"numerator": "利润", "denominator": "营收"},
      "zero_policy": "blank",
      "number_format": "0.00%"
    }
  ],
  "output_mode": "both"
}
```

展开：

```text
resolve columns -> write_formula_column x N -> set_number_format
-> formula_scan -> optional runtime recomputation assertion
```

可复用模板包括加减乘除、安全比例、同比、环比、税额、折扣后金额和日期期间。模板库应独立版本化。

### 8.5 `summarize_by_dimension`

目的：按任意一至多个维度和多个指标生成汇总表。

参数包括：source、where、group_by、metrics、sort、target、style。业务词“区域”“类别”只是字段参数，不进入实现。

展开：

```text
read/use table
-> optional filter_rows
-> aggregate
-> optional sort_rows
-> create/reuse target sheet
-> write_table
-> apply_style_preset
-> set_number_format
```

输出：汇总 `TableData` 与工作簿 `RangeRef`。验证：分组唯一性、输入输出汇总一致性、目标区域和格式。

### 8.6 `summarize_by_period`

目的：按日、周、月、季度、年等周期生成汇总。

它是 `normalize period + summarize_by_dimension` 的稳定特化，但不绑定具体业务。参数包含日期字段、源格式、周期粒度、无效日期策略和指标。

展开：

```text
normalize date -> derive period -> summarize_by_dimension
```

若周期维度直接来自 Excel 公式，可选择写入辅助列；默认运行时派生后写汇总值。

### 8.7 `compute_scalar_metrics`

目的：一次定义和计算多个 KPI 或检查标量。

参数：

```json
{
  "source": "clean_detail",
  "metrics": [
    {"id": "raw_count", "label": "原始行数", "function": "count_rows"},
    {"id": "valid_count", "label": "有效行数", "function": "count_if", "field": "清洗状态", "value": "有效"},
    {"id": "valid_revenue", "label": "有效营收", "function": "sum_if", "field": "营收", "where": {"field": "清洗状态", "op": "eq", "value": "有效"}}
  ]
}
```

展开：多个 `compute_scalar`，并将结果合并为 `MetricSetRef`。它默认不写工作簿，可被下面的写入分子复用。

### 8.8 `write_metric_block`

目的：将 `MetricSetRef` 写成 KPI 区块，并支持真实公式、格式和布局。

参数包括目标 Sheet/锚点、方向、列数、输出模式、样式和数字格式。

展开：

```text
create/reuse sheet -> write labels -> write_scalar x N
-> apply_style_preset -> set_number_format
```

输出：`RangeRef` 和带单元格绑定的 `MetricSetRef`。验证：指标数量约束、标签唯一、公式数量、公式与运行时复算一致。

### 8.9 `build_check_block`

目的：建立通用、可审计的检查区块，不绑定订单场景。

参数包括已命名标量、表达式、比较符、容差和目标位置。表达式只允许标量引用和 `add/subtract` 等受控操作。

展开：

```text
resolve ScalarRef
-> write check labels
-> write source/result/difference formulas
-> write PASS/FAIL formulas
-> add conditional format
-> register task assertions
```

典型检查：

- 原始行数 = 有效行数 + 异常行数；
- 明细有效金额 = 汇总金额；
- 分维度汇总金额 = 分期间汇总金额；
- 公式覆盖行数 = 明细行数。

输出：`CheckBlockRef`。Validator 必须重新读取最终 XLSX 并独立计算，不能只相信单元格中的 PASS。

### 8.10 `create_chart_block`

目的：基于一个或多个汇总 `RangeRef` 创建图表，并处理标题、锚点、尺寸和布局。

展开：

```text
validate source range -> choose explicit category/series
-> resolve non-overlapping anchor -> create_chart x N
-> layout check
```

它只负责 Excel 原生图表，不负责 PNG。数量约束由 Requirement，例如 `minimum_count: 2`，在展开和验证阶段同时检查。

### 8.11 `build_analysis_section`

目的：将一个汇总表、可选指标和图表组织成通用分析区块。

这是更高一级但仍跨业务复用的 Molecule，可组合：

```text
summarize_by_dimension
+ write_metric_block（可选）
+ create_chart_block（可选）
+ section layout
```

它不规定“经营总览”字段，只接收 section title、维度、指标和目标布局。该能力进入 MVP 后可显著降低复杂报表的装配节点数。

## 9. 能力目录设计

### 9.1 统一目录、不同定义

能力事实来源应统一，但 Atom、Molecule、Recipe 不应塞进同一个只有 `handler` 的数据类：

```python
class CapabilityCatalog:
    atoms: AtomRegistry
    molecules: MoleculeRegistry
    recipes: RecipeRegistry
    formula_templates: FormulaTemplateRegistry
    style_presets: StylePresetRegistry
```

统一目录负责：

- 唯一 ID 和版本；
- 查询与公开 Manifest；
- 引擎支持范围；
- Requirement 覆盖声明；
- 参数 Schema；
- 生命周期状态；
- 契约测试入口。

### 9.2 生命周期状态

```text
EXPERIMENTAL  可测试，不进入默认自动路由
AVAILABLE     实现、验证和文档完整，可自动路由
DEPRECATED    兼容旧计划，不再生成新计划
DISABLED      不可执行
```

设计文档中的能力不能自动出现在运行时 Manifest。只有实现适配器、Schema、测试和 Validator 后才能成为 `AVAILABLE`。

### 9.3 覆盖声明

不能再用简单字符串 `covers=("kpi",)` 表达全部能力。覆盖模式至少包含：

```json
{
  "requirement_type": "chart",
  "constraints": {
    "minimum_count": {"max_supported": 8},
    "native_excel": true
  },
  "conditions": ["source_range_resolved"]
}
```

Requirement 应支持：

```text
type
critical
minimum_count / exact_count
required_sheets
output_mode
formula_required
native_object_required
constraints
validator
```

Planner 只有在所有约束均满足时才能标记 `COVERED`。

## 10. Planner 与组合设计

### 10.1 Planner 为什么仍然需要

简单任务可以由 Agent 直接调用一个 Atom 或 Molecule，不必构造复杂计划。例如“筛选华东区并写入新 Sheet”可以直接调用相应接口。

复杂任务仍需要 Planner，因为工具暴露不能自动保证：

- 所有 Requirement 被覆盖；
- 多个分子的输入输出能够连接；
- 分支均使用同一份有效数据；
- Sheet、公式和图表创建顺序正确；
- 数量和输出模式满足约束；
- Validator 验证的是完整用户任务。

Planner 应保持确定性和有限职责，而不是让 LLM 在 Planner 内自由编程。

### 10.2 Coverage Planner

输入：TaskSpec、RequirementSet、WorkbookProfile、Capability Manifest。

职责：

1. 标准化 Requirement；
2. 判断 Recipe 是否完整覆盖；
3. 查找可覆盖每项要求的 Molecule/Atom 候选；
4. 检查数量、公式、引擎、Sheet 和风险约束；
5. 输出覆盖矩阵和缺口；
6. critical Requirement 未覆盖时阻止执行。

它不生成 `HighLevelPlan`，也不声称已经形成可执行计划。

### 10.3 Composed Plan Builder

输入：覆盖决策、FieldBindings、WorkbookProfile、输出布局约束。

职责：

1. 选择满足覆盖的最小 Molecule 集合；
2. 为 Molecule 绑定字段、来源和目标；
3. 调用 Molecule expander 得到 PlanFragment；
4. 根据端口类型连接 Fragment；
5. 插入缺失的 Atom，例如读取、创建 Sheet 和写入；
6. 合并相同读取和中间变换；
7. 处理分支、汇合、写入冲突和布局；
8. 绑定任务级 Assertion；
9. 输出唯一 ExecutionPlan。

Agent 不直接提供节点依赖，只提供语义参数和必要的用户决策。

### 10.4 组合算法

候选选择按以下顺序：

```text
完整覆盖的稳定 Recipe
-> 覆盖更多 Requirement 的 Molecule
-> 少量补充 Atom
-> Dynamic Transform 补纯数据缺口
-> Dynamic Task（当前禁用）
-> UNSUPPORTED
```

候选评分建议：

```text
score =
  未覆盖关键要求的极大惩罚
  + 动态代码惩罚
  + 高风险写入惩罚
  + 节点数量
  + 重复读取与重复计算成本
  + 不可独立验证惩罚
```

“最少组件”不是唯一目标；一个节点较少但无法验证的黑盒方案应输给可展开、可审计的组合。

### 10.5 DAG 合并规则

- 每个节点有唯一 ID、类型化输入端口和输出端口；
- 依赖由 Ref 绑定推导，不从任意字符串猜测；
- 同一源表和字段集合的读取可以合并；
- 清洗、分类后的有效数据建立明确分支引用；
- 两个写入节点的预计范围冲突时编译失败；
- 图表必须依赖已写入的 `RangeRef`；
- 检查区块必须依赖命名 `ScalarRef`；
- 所有节点拓扑排序后才能交给 Executor。

### 10.6 复杂分析报表示例

下面是评测场景可能生成的组合，不是专用 Recipe：

```text
resolve/read source
  -> add_source_trace
  -> normalize_columns
  -> classify_rows
  -> add_formula_metrics
       |-> write detail
       |-> filter valid rows
             |-> summarize_by_period
             |-> summarize_by_dimension
             |-> compute_scalar_metrics -> write_metric_block
       |-> compute audit scalars -> build_check_block
  -> create_chart_block
```

每个 Molecule 都可单独用于其他任务，整张图由 Builder 根据 Requirement 生成。

## 11. 执行设计

### 11.1 执行前展开

ExecutionPlan 不应包含运行时无法解释的黑盒 Molecule handler。推荐流程：

```text
CompositionPlan（含 Molecule）
-> expand and compile
-> ExecutionPlan（Atom + Dynamic Transform）
-> Policy
-> execute
```

ExecutionPlan 保留 `origin_molecule` 和 `fragment_version`，方便审计和复盘。

### 11.2 Atom Adapter

统一执行接口：

```python
class AtomExecutor(Protocol):
    def execute(
        self,
        context: ExecutionContext,
        parameters: Mapping[str, Any],
        inputs: Mapping[str, Ref],
    ) -> StepResult: ...
```

适配器可以是：

```text
InProcessAdapter   当前 WorkbookContext/openpyxl 实现
CliAdapter         调用成熟 XLSX CLI 并解析 JSON 结果
McpAdapter         调用 MCP Tool 并解析结构化结果
```

所有适配器必须返回统一 `StepResult`、ChangeRecord 和错误码，不允许上层依赖某个后端的自由文本。

### 11.3 事务和工作副本

- 所有修改发生在运行目录工作副本；
- 原始文件只读并记录 SHA-256；
- 每个 Atom 执行前检查授权范围；
- 每个写 Atom 执行后记录实际范围和对象变化；
- 任一步失败，不发布临时文件；
- 只有任务级 Validator 通过后发布。

## 12. 验证设计

### 12.1 三层验证

```text
Atom Validator
  参数、类型、范围和单步结果。

Molecule Assertion
  分子语义是否成立，例如汇总守恒、公式覆盖和指标数量。

Task-level Validator
  用户完整 Requirement 是否全部满足。
```

局部 ExecutionPlan PASS 不能替代 Task-level PASS。

### 12.2 Requirement 验证映射

每个 critical Requirement 必须绑定至少一个能读取最终 XLSX 的 Validator。示例：

| Requirement | 最终文件验证 |
|---|---|
| 原始行可追溯 | 检查追溯列、非空率、唯一性和源行范围 |
| 真实公式 | `data_only=False` 扫描公式及覆盖行数 |
| 至少 4 个 KPI | 检查 KPI 区块标签、数量、值/公式 |
| 至少 2 个图表 | 检查原生图表对象、系列和引用 |
| 对账通过 | 独立读取源数据和结果重算，不信任自报 PASS |
| 指定 Sheet | 检查名称、数量和关键区域 |

### 12.3 Formula 模式限制

openpyxl 能写公式但不计算公式。Validator 必须区分：

```text
公式文本合法且引用正确
公式缓存值是否可用
独立 Python 复算是否一致
```

不能因为 `data_only=True` 读取到空值就误判公式不存在，也不能因为公式文本存在就认为计算结果正确。

### 12.4 PNG 独立流程

Excel MVP 的成功条件止于已验证 XLSX：

```text
Excel Pipeline -> validated.xlsx -> PASS/FAIL
```

需要预览时再执行：

```text
validated.xlsx -> Renderer -> preview.png -> Visual Validator
```

Renderer 不应伪装成 Excel Atom，也不应因环境缺少 Renderer 阻止本来合格的 XLSX 生成，除非用户把 PNG 明确列为独立必需交付物。

## 13. 动态能力边界

### 13.1 Dynamic Transform

仅用于固定 Atom/Molecule 无法表达的 `TableData -> TableData/ScalarRef` 逻辑。不得直接访问文件、工作簿或网络。

执行后可以通过固定写入 Atom 将结果落到 Excel。这样动态代码不需要获得工作簿写权限。

### 13.2 Dynamic Task

允许直接操作工作簿的动态脚本风险明显更高。当前 MVP 保持禁用。未来启用时必须具备：

- 独立进程或容器；
- 精确工作副本路径；
- 禁止网络和任意文件访问；
- 写入范围和对象预算；
- 变更 diff；
- 完整任务级 Validator。

## 14. 模块详细设计

建议目标结构：

```text
src/sheetpilot/
├── catalog/
│   ├── catalog.py
│   ├── manifests.py
│   └── lifecycle.py
├── atoms/
│   ├── definitions.py
│   ├── parameters.py
│   ├── adapters/
│   │   ├── in_process.py
│   │   ├── cli.py
│   │   └── mcp.py
│   └── results.py
├── molecules/
│   ├── definitions.py
│   ├── fragments.py
│   ├── data_quality.py
│   ├── analysis.py
│   ├── formulas.py
│   ├── metrics.py
│   ├── checks.py
│   └── charts.py
├── planning/
│   ├── requirements.py
│   ├── coverage.py
│   ├── bindings.py
│   ├── composition.py
│   ├── expansion.py
│   └── compiler.py
├── references/
│   ├── models.py
│   └── resolver.py
├── executor/
├── validators/
└── runtime/
```

职责约束：

- `catalog` 不导入具体 Excel 引擎对象；
- `atoms` 不包含多步流程；
- `molecules` 只生成 Fragment，不直接调用 openpyxl；
- `planning` 不修改工作簿；
- `executor` 不进行语义规划；
- `validators` 独立读取最终文件，不复用执行结果作为唯一证据。

## 15. 对当前实现的差距分析

当前实现可以保留的部分：

- 冻结注册表与 Compiler/Dispatcher 共用事实来源；
- 12 个基础操作及 WorkbookContext；
- ExecutionPlan、Policy、工作副本和 ChangeRecorder；
- Dynamic Transform 的 AST、子进程和预算限制；
- Inspector 和基础 Validator。

需要调整的部分：

1. `CapabilityDefinition` 拆成 AtomDefinition 与 MoleculeDefinition；
2. 当前 7 个 Composite 从 handler 改造成 expander；
3. `HybridPlanner` 改名并收敛为 Coverage Planner；
4. 新增 Composed Plan Builder 和 Fragment 合并；
5. `plan` CLI 输出真正可编译的 CompositionPlan，而不只是组件列表；
6. 增加 ScalarRef、CellRef、RangeRef 等类型化引用；
7. 增加 `compute_scalar`、`write_scalar` 等 Atom；
8. 利润、KPI、检查等分子支持真实 Excel 公式和目标位置；
9. Requirement Schema 支持数量、Sheet、公式和原生对象约束；
10. Validator 从计划级断言升级到完整任务 Requirement 验收；
11. `UNCOVERED` critical Requirement 成为 compile/execute 硬门禁；
12. PNG 从 Excel 核心流程移除。

当前 `calculate_profitability`、`build_kpi_block` 等函数可暂时作为 Molecule 内部运行时计算辅助，但不能继续作为目标态 Composite 接口。

## 16. MVP 实施方案

### 阶段 A：类型与目录重构

- 增加类型化 Ref 和 StepResult；
- 拆分 Atom/Molecule Definition；
- 保持旧注册表兼容读取；
- 增加生命周期状态和公开 Manifest；
- 建立能力契约测试。

完成标准：现有 12 个能力作为 Atom 可查询、可执行，Compiler 和 Dispatcher 无重复白名单。

### 阶段 B：工作簿写入基础补齐

- 实现 `compute_scalar`、`write_scalar`、`write_values`；
- 完善 `write_formula_column/cells`；
- 增加 `set_number_format`、条件格式和 Excel Table；
- 所有写能力返回精确 Ref 和 ChangeRecord。

完成标准：可以从表格提取标量并以值或真实公式写入新 Sheet，最终文件可独立验证。

### 阶段 C：首批通用 Molecule

优先实现：

```text
add_source_trace
normalize_columns
classify_rows
add_formula_metrics
summarize_by_dimension
summarize_by_period
compute_scalar_metrics
write_metric_block
build_check_block
create_chart_block
```

每个 Molecule 必须有参数 Schema、展开快照测试、至少一个真实 XLSX 集成测试和独立 Validator。

### 阶段 D：确定性组合器

- 实现 Coverage Planner；
- 实现字段和目标位置绑定；
- 实现 Fragment 展开与 DAG 合并；
- 实现冲突检测和依赖推导；
- `sheetpilot plan` 生成 CompositionPlan；
- `sheetpilot compile` 展开为唯一 ExecutionPlan；
- 增加 critical uncovered 硬门禁。

### 阶段 E：任务级验收

- Requirement Validator Registry；
- 数量、公式、图表、Sheet 和对账约束；
- Validator 独立读取最终 XLSX；
- 局部 PASS 不再允许发布完整任务结果。

### 阶段 F：动态缺口与反馈循环

- 仅在固定能力存在纯数据缺口时使用 Dynamic Transform；
- 记录重复动态逻辑；
- 达到复用和稳定门槛后提升为 Atom 模板或 Molecule；
- 不自动提升为完整 Recipe。

## 17. 测试策略

### 17.1 Atom 契约测试

每个 Atom 测试：参数拒绝、输入输出类型、边界、错误码、副作用、ChangeRecord、保存重开。

### 17.2 Molecule 展开测试

每个 Molecule 测试：

- 同输入产生稳定 Fragment；
- 展开节点全部来自已注册 Atom；
- 端口类型连接合法；
- 副作用和 Validator 声明完整；
- 目标位置和公式模式正确；
- 参数变化只影响预期节点。

### 17.3 组合器测试

- 单链、分支、汇合；
- 重复读取合并；
- 写入冲突；
- 数量约束；
- 关键 Requirement 未覆盖时阻断；
- Dynamic Transform 只补指定缺口；
- 不允许局部 Recipe 冒充完整覆盖。

### 17.4 真实文件测试

至少维护：

- 简单筛选和写表；
- 多维度、多指标汇总；
- 真实公式派生列；
- KPI 与标量提取；
- 对账检查块；
- 两图表和布局；
- 脏订单综合评测，但不建立专用 Recipe。

验收必须检查真实 `.xlsx`，不能只依据执行器自报。

## 18. 最终设计判断

SheetPilot 的价值不在于重新包装已有 XLSX CLI/MCP，也不在于积累大量场景脚本。合理定位是：

```text
复用成熟原子执行面
+ 注册可展开的通用分子能力
+ 用确定性组合器解决复杂任务依赖
+ 用任务级 Validator 保证完整交付
+ 用受限动态 Transform 处理长尾数据逻辑
```

这样简单任务仍可由 Agent 快速直调 Atom/Molecule，复杂任务则由系统稳定组合。分子能力既保持跨业务复用，也能通过展开后的写入、公式、样式和对象 Atom 真正修改 Excel。
