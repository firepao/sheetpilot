# SheetPilot 能力注册表与工具实现设计 V1

## 1. 文档目的

本文定义 SheetPilot 编排级工具的实现契约，以及 Compiler、Dispatcher、Skill 和测试共同使用的唯一能力注册表。本文是 `05-mvp-detailed-design-v3.md` 的实施补充，不改变原有的安全、工作副本和验收原则。

本阶段解决以下问题：

1. Compiler 声明的能力与 Dispatcher 实际可执行能力不一致。
2. 工具参数以无约束 `dict` 传递，未知参数和错误类型发现过晚。
3. Skill 只能通过阅读源码判断能力，容易生成无法执行的计划。
4. 工具缺少统一的输入、输出、风险、变更和测试契约。
5. 文本日期、过滤和空结果等常见情况缺少稳定语义。

## 2. 范围与原则

### 2.1 本期能力范围

编排级能力分两批实现。

第一批是经营汇总闭环必须具备的能力：

```text
read_table
select_columns
filter_rows
aggregate
sort_rows
create_sheet
write_table
apply_style_preset
create_chart
freeze_header
```

第二批在第一批稳定后实现：

```text
derive_column
add_formula_column
```

未完成实现、参数校验、注册和契约测试的能力不得出现在运行时注册表中。

### 2.2 设计原则

- 注册表是运行时能力的唯一事实来源。
- “设计存在”不等于“运行时可用”。
- Compiler 只接受注册且支持当前引擎的能力。
- Dispatcher 不维护独立 `if/elif` 白名单。
- 每个工具必须使用明确参数模型和结构化结果。
- 读取、纯数据变换、工作簿写入三类工具分别声明风险和副作用。
- 任何工具不得接收 Python 表达式、模块路径、Shell 命令或 openpyxl 对象。
- 任何写工具都必须通过 `WorkbookContext` 授权和 `ChangeRecorder` 记录。
- 核心用户要求未被计划覆盖时，Compiler 必须拒绝计划，而不是带缺失功能执行。

## 3. 能力注册表

### 3.1 模块位置

新增模块：

```text
src/sheetpilot/capabilities/
├── __init__.py
├── base.py
├── registry.py
├── parameters.py
├── handlers.py
└── manifest.py
```

职责如下：

| 模块 | 职责 |
|---|---|
| `base.py` | 定义能力、风险和结果协议 |
| `registry.py` | 注册、查找和冻结能力集合 |
| `parameters.py` | 每个能力的严格参数模型 |
| `handlers.py` | 参数模型到 WorkbookContext 的确定性适配器 |
| `manifest.py` | 向 Skill/CLI 输出不含 Python 对象的公开能力清单 |

### 3.2 能力定义

```python
@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    version: str
    parameter_type: type[CapabilityParameters]
    handler: CapabilityHandler
    input_kind: str
    output_kind: str
    risk_level: Literal["read", "transform", "write", "object_write"]
    supported_engines: frozenset[str]
    required_validations: tuple[str, ...]
    side_effects: frozenset[str]
```

约束：

- `name` 使用稳定的 `snake_case`，作为计划中的 `op` 和执行步骤中的 `handler`。
- `version` 表示能力契约版本，不等同于软件包版本。
- `parameter_type` 必须拒绝未知字段。
- `handler` 是代码注册时绑定的函数，不能来自计划内容。
- `supported_engines` 首期只能包含 `openpyxl`。
- `side_effects` 只能取 `read_workbook`、`create_sheet`、`write_values`、`write_formulas`、`write_styles`、`create_chart`。

### 3.3 注册和冻结

```python
registry = CapabilityRegistry()
registry.register(READ_TABLE)
registry.register(FILTER_ROWS)
registry.register(AGGREGATE)
registry.freeze()
```

注册规则：

- 重复名称立即失败。
- 名称、版本、参数模型、handler 或引擎集合缺失时失败。
- `freeze()` 后禁止动态添加和替换。
- 生产代码只暴露冻结后的 `DEFAULT_REGISTRY`。
- 测试可创建局部注册表，但不得修改 `DEFAULT_REGISTRY`。

### 3.4 唯一事实来源

各模块只能这样使用注册表：

```text
Compiler   -> registry.require(step.op, engine)
Dispatcher -> registry.execute(step.handler, context, parameters, results)
CLI        -> registry.public_manifest()
Skill      -> sheetpilot capabilities 的 JSON 输出
Tests      -> 遍历 registry.definitions() 执行契约测试
```

删除以下重复声明：

- `planning.compiler.HANDLERS`
- `executor.dispatcher` 中按名称维护的 `if/elif` 白名单
- Skill `contracts.md` 中手工维护的可用能力清单

Skill 文档只说明如何查询能力，不复制运行时状态。

### 3.5 规划能力与运行能力分离

尚未实现的能力可以记录在设计文档或 `roadmap` 中，但不能注册：

```python
PLANNED_CAPABILITIES = {
    "derive_column": "planned",
    "add_formula_column": "planned",
}
```

`PLANNED_CAPABILITIES` 仅用于开发跟踪，不得被 Compiler 或 Dispatcher 导入。

## 4. 公共数据契约

### 4.1 参数模型

所有参数模型采用不可变 `dataclass`，并提供统一入口：

```python
class CapabilityParameters(Protocol):
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self: ...
    def to_dict(self) -> dict[str, Any]: ...
```

`from_dict` 必须完成：

- 必填字段检查；
- 未知字段拒绝；
- 基础类型和枚举检查；
- 字符串非空和长度限制；
- 参数间约束；
- 错误转换为 `PLAN_INVALID`，并包含能力名和参数路径。

### 4.2 数据引用

```python
@dataclass(frozen=True)
class DataRef:
    step_id: str

@dataclass(frozen=True)
class TableData:
    fields: tuple[TableField, ...]
    rows: tuple[tuple[CellValue, ...], ...]
    row_count: int
    provenance: TableProvenance
```

`TableData` 不再使用任意字段名到值的松散字典作为公共契约。字段顺序、类型和来源必须明确。实现内部可使用索引缓存提高查找效率。

### 4.3 步骤结果

```python
@dataclass(frozen=True)
class StepResult:
    step_id: str
    output_kind: str
    value: TableData | SheetRef | RangeRef | ChartRef | None
    metrics: dict[str, int | float | str]
    warnings: tuple[WarningRecord, ...] = ()
```

Dispatcher 的结果表只保存 `StepResult`。后续步骤通过注册表校验输入类型，例如 `aggregate` 只能接收 `TableData`。

### 4.4 条件表达式

过滤和派生使用受控 AST，不接受字符串表达式：

```json
{
  "all": [
    {"field": "清洗状态", "op": "eq", "value": "有效"},
    {"field": "是否退货", "op": "eq", "value": "否"}
  ]
}
```

白名单操作符：

```text
eq ne gt gte lt lte in not_in is_null not_null contains starts_with ends_with between
```

条件最多嵌套两层；单个步骤最多 20 个原子条件；`in/not_in` 最多 100 个值。禁止正则表达式进入 MVP，避免复杂度和资源风险。

### 4.5 日期标准化

日期解析是表格数据层的公共能力，不由配方临时处理。支持：

- Python `date` 和 `datetime`；
- Excel 原生日期序列经 openpyxl 转换后的日期值；
- 严格 ISO 文本 `YYYY-MM-DD`；
- 明确声明格式的文本日期，例如 `%Y/%m/%d`。

不进行模糊地区格式猜测。`01/02/2026` 等歧义文本必须由语义任务声明格式或返回 `DATA_TYPE_UNSUPPORTED`。

解析结果同时保留：

```text
parsed_count
invalid_count
invalid_sample_rows（最多 10 个原始行号，不记录敏感值）
```

## 5. 工具实现设计

## 5.1 `read_table`

### 目的

从确定的工作表和表头读取有限字段，构造带类型和来源信息的 `TableData`。

### 参数

```json
{
  "sheet": "清洗明细",
  "header_rows": [1],
  "fields": ["日期", "城市", "销售额"],
  "columns": {"日期": "C", "城市": "D", "销售额": "G"},
  "max_rows": 200000
}
```

`columns` 只允许 Compiler 写入，HighLevelPlan 不允许直接提供。Compiler 根据 WorkbookProfile 解析后生成。

### 实现

1. 校验工作表、表头行和列地址。
2. 计算有界读取范围，拒绝整列和超过策略上限的读取。
3. 逐行读取指定字段，不加载未声明列。
4. 保留数值、布尔、文本、日期和公式文本；错误单元格记录为受控错误值。
5. 跳过所有已选字段均为空的行，保留原始行号到 provenance。
6. 记录读取行数、空行数、字段和耗时，不记录完整数据。

### 输出和错误

- 输出：`TableData`。
- 错误：`SHEET_NOT_FOUND`、`FIELD_NOT_FOUND`、`READ_LIMIT_EXCEEDED`、`DATA_TYPE_UNSUPPORTED`。
- 变更：只记录 `read`，不产生工作簿写入。

### 测试

类型保持、空行、公式文本、错误单元格、中文表头、重复表头、最大行数和原始行号。

## 5.2 `select_columns`

### 目的

从前序 `TableData` 选择、重排和安全重命名字段。

### 参数

```json
{
  "input": "read_source",
  "fields": [
    {"source": "城市", "as": "城市"},
    {"source": "销售额", "as": "销售收入"}
  ]
}
```

### 实现

1. 验证输入为 `TableData`。
2. 验证源字段存在且不重复。
3. 验证输出字段名非空且唯一。
4. 通过字段索引重建字段和行，不改变值类型与行数。
5. 更新字段 provenance，记录重命名关系。

### 输出和错误

- 输出：新的 `TableData`。
- 错误：`DATA_REF_INVALID`、`FIELD_NOT_FOUND`、`DUPLICATE_OUTPUT_FIELD`。
- 变更：纯内存变换。

### 测试

选择、重排、重命名、缺失字段、重复别名、零字段拒绝和类型保持。

## 5.3 `filter_rows`

### 目的

按受控条件筛选行，支持脏数据清洗状态、退货标记和日期范围等业务过滤。

### 参数

```json
{
  "input": "read_source",
  "where": {
    "all": [
      {"field": "清洗状态", "op": "eq", "value": "有效"},
      {"field": "是否退货", "op": "eq", "value": "否"},
      {"field": "日期", "op": "between", "value": ["2026-01-01", "2026-12-31"], "value_type": "date", "source_format": "%Y-%m-%d"}
    ]
  },
  "invalid_value_policy": "exclude"
}
```

### 实现

1. 编译受控条件 AST 为内部谓词，不使用 `eval`。
2. 校验字段存在、操作符与字段类型兼容。
3. 日期比较前执行严格日期标准化。
4. 按行求值；短路处理 `all/any`。
5. 对无法解析的值执行 `exclude`、`fail` 或 `keep` 策略；核心日期默认 `fail`，非核心脏值默认 `exclude`。
6. 输出保留原始行号和过滤统计。
7. 零行结果立即返回 `NO_ROWS_AFTER_FILTER`，不延迟到图表步骤。

### 输出和错误

- 输出：过滤后的 `TableData`，metrics 包含输入、输出、排除和无效行数。
- 错误：`FILTER_INVALID`、`FILTER_TYPE_MISMATCH`、`DATE_PARSE_FAILED`、`NO_ROWS_AFTER_FILTER`。
- 变更：纯内存变换。

### 测试

单条件、复合条件、空值、数值边界、ISO 文本日期、歧义日期、无效值策略、零结果和大表性能。

## 5.4 `derive_column`

### 目的

在内存表中按白名单模板生成派生字段，用于执行前计算，不直接写 Excel 公式。

### 参数

```json
{
  "input": "filtered",
  "as": "利润",
  "template": "subtract",
  "arguments": {"left": "销售额", "right": "成本"},
  "null_policy": "null"
}
```

首期模板：`add`、`subtract`、`multiply`、`safe_divide`、`date_year`、`date_month`、`coalesce`。

### 实现

1. 从模板注册表获取确定性实现。
2. 校验参数字段及输入类型。
3. 逐行计算，不执行任意表达式。
4. 明确零除和空值策略。
5. 将模板、参数字段和失败计数写入 provenance。

### 输出和错误

- 输出：增加一个字段的 `TableData`。
- 错误：`DERIVATION_TEMPLATE_UNSUPPORTED`、`FIELD_NOT_FOUND`、`DERIVATION_TYPE_MISMATCH`。
- 变更：纯内存变换。

### 测试

每个模板、负值、零除、空值、日期文本、重复输出字段和类型错误。

## 5.5 `aggregate`

### 目的

对已经完成必要过滤的 `TableData` 执行确定性分组聚合。

### 参数

```json
{
  "input": "filtered",
  "group_by": ["城市", "渠道"],
  "metrics": [
    {"field": "销售额", "function": "sum", "as": "销售收入"},
    {"field": "订单ID", "function": "count_distinct", "as": "订单数"}
  ],
  "null_group_policy": "label",
  "null_group_label": "(空)"
}
```

首期聚合函数：`sum`、`count`、`count_distinct`、`min`、`max`、`average`。经营汇总第一阶段仍限制一个核心数值指标，扩展指标需同步扩展业务 Validator。

### 实现

1. 验证分组和指标字段存在。
2. 验证聚合函数和输入类型兼容。
3. 应用明确的空值策略；不得静默把非法数值当零。
4. 使用稳定键分组；保持负数。
5. 输出按明确的稳定排序规则排列。
6. 零组结果返回 `NO_ROWS_TO_AGGREGATE`。
7. 记录输入行数、参与计算行数、忽略空值数和输出组数。

日期范围不再由 `aggregate` 特殊处理，统一交给 `filter_rows`，避免重复过滤语义。

### 输出和错误

- 输出：汇总 `TableData`。
- 错误：`AGGREGATION_INVALID`、`AGGREGATION_TYPE_MISMATCH`、`NO_ROWS_TO_AGGREGATE`。
- 变更：纯内存变换。

### 测试

单/双维度、全部聚合函数、负值、空值、重复值、浮点容差、稳定结果和零行。

## 5.6 `sort_rows`

### 目的

按一个或多个字段稳定排序，为结果表和图表提供确定顺序。

### 参数

```json
{
  "input": "aggregate_summary",
  "keys": [
    {"field": "销售收入", "direction": "desc", "nulls": "last"},
    {"field": "城市", "direction": "asc", "nulls": "last"}
  ]
}
```

### 实现

1. 验证字段存在且方向合法。
2. 标准化空值排序，不直接比较不可比类型。
3. 从末级键到首级键执行稳定排序。
4. 类型混合字段默认拒绝；只有显式 `coerce_to_text` 时按文本排序。

### 输出和错误

- 输出：行顺序变化、字段不变的 `TableData`。
- 错误：`SORT_INVALID`、`SORT_TYPE_MISMATCH`。
- 变更：纯内存变换。

### 测试

升降序、多键、空值、稳定性、日期和混合类型。

## 5.7 `create_sheet`

### 目的

创建计划声明的新工作表。

### 参数

```json
{"sheet": "城市渠道销售汇总"}
```

### 实现

1. Compiler 校验 Excel 工作表名称、长度、非法字符和冲突。
2. Policy 确认该操作只新增工作表，不替换、删除或重命名现有表。
3. WorkbookContext 再次检查名称和计划授权。
4. Engine 创建工作表。
5. ChangeRecorder 记录对象变化并增加 `new_sheets`。

### 输出和错误

- 输出：`SheetRef`。
- 错误：`SHEET_NAME_INVALID`、`SHEET_ALREADY_EXISTS`、`CHANGE_NOT_AUTHORIZED`、`CHANGE_BUDGET_EXCEEDED`。
- 变更：`create_sheet`。

### 测试

中文名、空格、31 字符边界、非法字符、重名、预算和引擎失败。

## 5.8 `write_table`

### 目的

把 `TableData` 写入新建工作表的精确矩形区域。

### 参数

```json
{
  "input": "sorted_summary",
  "sheet": "城市渠道销售汇总",
  "anchor": "A3",
  "include_header": true
}
```

### 实现

1. Compiler 根据输入步骤的静态形状估计或运行时上限生成授权范围。
2. 执行前根据实际 `TableData` 计算精确输出范围和单元格数。
3. WorkbookContext 校验实际范围包含于授权范围且不与其他写步骤冲突。
4. 逐区域写入类型化值；不得把数字和日期预格式化为字符串。
5. ChangeRecorder 记录精确范围和实际写入单元格数。
6. 返回 `RangeRef`，供样式和图表步骤引用。

不得再用 `A3:XFD1048576` 作为正常预计写入范围。输入规模无法静态确定时，计划声明合理上限，执行记录声明实际范围。

### 输出和错误

- 输出：`RangeRef`。
- 错误：`OUTPUT_RANGE_OVERFLOW`、`WRITE_CONFLICT`、`CHANGE_NOT_AUTHORIZED`、`CHANGE_BUDGET_EXCEEDED`。
- 变更：`write_values`。

### 测试

空表拒绝、单行、最大范围、日期和数值类型、授权边界、冲突和保存往返。

## 5.9 `add_formula_column`

### 目的

在已经写入的结果区域右侧使用注册公式模板添加公式列。

### 参数

```json
{
  "input": "write_summary",
  "header": "毛利率",
  "template": "safe_ratio",
  "arguments": {"numerator_header": "利润", "denominator_header": "销售收入"},
  "number_format": "0.0%"
}
```

### 实现

1. 从公式模板注册表取得模板；不接受任意公式文本。
2. 根据 `RangeRef` 和表头解析输入列。
3. 计算目标列和精确填充范围。
4. 使用相对/绝对引用生成代表公式并逐行填充。
5. 对工作表名统一转义；对零除使用受控保护。
6. 记录模板名、目标范围和代表公式，不记录全部公式。
7. 标记“公式文本已验证，未由 openpyxl 计算”。

### 输出和错误

- 输出：扩展后的 `RangeRef`。
- 错误：`FORMULA_TEMPLATE_UNSUPPORTED`、`FORMULA_ARGUMENT_INVALID`、`FORMULA_RANGE_CONFLICT`。
- 变更：`write_formulas`。

### 测试

引用偏移、特殊表名、零除、空数据、填充边界、公式扫描和重开保留。

## 5.10 `apply_style_preset`

### 目的

对已授权区域应用版本化样式预设。

### 参数

```json
{
  "input": "write_summary",
  "preset": "business_table",
  "preset_version": "1.0"
}
```

### 实现

1. 从样式预设注册表获取样式，不接受 openpyxl Style 对象。
2. 校验目标 `RangeRef` 属于本计划写入区域。
3. 根据表头、明细和数值列分区应用样式。
4. 列宽基于有限样本计算，限制在 8 至 40；禁止无界 autofit。
5. 记录样式范围和预设版本。

首期预设：`business_table`、`title`、`total_row`、`input_area`、`formula_area`。

### 输出和错误

- 输出：无数据输出，返回结构化变更摘要。
- 错误：`STYLE_PRESET_UNSUPPORTED`、`STYLE_RANGE_UNAUTHORIZED`。
- 变更：`write_styles`。

### 测试

每个预设的关键属性、区域边界、数字格式、列宽限制和原区域不变。

## 5.11 `create_chart`

### 目的

基于结果 `RangeRef` 创建白名单图表。

### 参数

```json
{
  "input": "write_summary",
  "sheet": "城市渠道销售汇总",
  "chart_type": "bar",
  "category_fields": ["城市", "渠道"],
  "series_fields": ["销售收入"],
  "anchor": "F3",
  "title": "城市渠道销售额"
}
```

### 实现

1. 显式解析分类字段和数值系列，禁止按“第一列分类、其余列系列”猜测。
2. 双维度分类生成确定性的组合标签，例如 `城市 / 渠道`，或要求前序 `derive_column` 生成标签。
3. 校验至少一行数据和一个数值系列；空数据返回 `CHART_SOURCE_EMPTY`。
4. 校验图表类型、系列数量和数据引用。
5. 检查锚点不覆盖核心结果区域。
6. Engine 创建图表，ChangeRecorder 记录类型、锚点和引用范围。

首期支持 `bar`、`column`、`line`、`pie`；饼图只允许一个系列和合理分类数量。

### 输出和错误

- 输出：`ChartRef`。
- 错误：`CHART_TYPE_UNSUPPORTED`、`CHART_SOURCE_EMPTY`、`CHART_FIELD_INVALID`、`CHART_ANCHOR_CONFLICT`。
- 变更：`create_chart`。

### 测试

各图表重开、单/双维分类、系列引用、空数据、文本系列拒绝、锚点和对象预算。

## 5.12 `freeze_header`

### 目的

冻结结果表表头以下的窗格，提高浏览可用性。

### 参数

```json
{"sheet": "城市渠道销售汇总", "cell": "A4"}
```

### 实现

1. 校验工作表由计划创建或明确允许布局修改。
2. 校验单个 A1 单元格地址，拒绝范围、整行和整列。
3. Engine 设置 `freeze_panes`。
4. ChangeRecorder 记录布局对象变化。

### 输出和错误

- 输出：结构化布局结果。
- 错误：`FREEZE_PANE_INVALID`、`LAYOUT_CHANGE_UNAUTHORIZED`。
- 变更：`write_styles` 或独立 `freeze_panes` 类型；推荐独立类型便于 Diff。

### 测试

正常地址、中文工作表、非法地址、非授权工作表和保存往返。

## 6. Compiler 设计

### 6.1 编译流程

```text
HighLevelStep
  -> registry.require(op, engine)
  -> parameter_type.from_dict(parameters)
  -> resolve DataRef
  -> capability-specific compile hook
  -> calculate reads/writes/budget/validations
  -> immutable ExecutionStep
```

能力可以提供可选的纯函数编译钩子：

```python
compile_hook(
    parameters,
    task,
    workbook_profile,
    prior_step_contracts,
) -> CompiledCapabilityStep
```

编译钩子不得读取工作簿、修改业务语义或执行 handler。

### 6.2 核心需求覆盖检查

`SemanticTask.requested_output` 增加结构化要求，至少表达：

```json
{
  "dimensions": ["region", "channel"],
  "metrics": ["revenue"],
  "filters": ["valid_rows", "not_returned", "current_period"],
  "chart": "bar"
}
```

配方编译结果声明：

```json
{
  "covered_requirements": ["dimensions", "revenue", "valid_rows", "not_returned", "current_period", "chart"],
  "uncovered_requirements": []
}
```

任一核心要求未覆盖时返回 `CAPABILITY_UNSUPPORTED`。不得生成忽略过滤条件的 `PROCEED` 计划。

### 6.3 编译期错误

- 未注册能力：`CAPABILITY_UNSUPPORTED`。
- 当前引擎不支持：`ENGINE_CAPABILITY_UNSUPPORTED`。
- 参数错误：`PLAN_INVALID`，包含能力名和参数路径。
- 输入输出类型不匹配：`DATA_REF_TYPE_MISMATCH`。
- 核心要求未覆盖：`REQUIREMENT_UNCOVERED`。
- 范围冲突或超预算：沿用 Policy/Plan 稳定错误。

## 7. Dispatcher 设计

Dispatcher 缩减为通用流程：

```python
def dispatch(context, step, results, registry):
    definition = registry.require(step.handler, context.engine_name)
    parameters = definition.parameter_type.from_dict(step.parameters)
    inputs = resolve_inputs(parameters, results, definition.input_kind)
    value = definition.handler(context, parameters, inputs)
    result = ensure_step_result(step.id, definition.output_kind, value)
    results[step.id] = result
    return result
```

Dispatcher 只负责：

- 通过注册表查找能力；
- 二次参数校验；
- 解析受控 DataRef；
- 检查输入输出类型；
- 调用已绑定 handler；
- 返回 `StepResult`。

Dispatcher 不负责业务过滤、聚合、范围授权和错误吞并。

## 8. CLI 与 Skill 能力发现

新增命令：

```powershell
sheetpilot capabilities
sheetpilot capabilities --name filter_rows
```

输出由 `registry.public_manifest()` 生成：

```json
{
  "schema_version": "1.0",
  "engine": "openpyxl",
  "capabilities": [
    {
      "name": "filter_rows",
      "version": "1.0",
      "input_kind": "table",
      "output_kind": "table",
      "risk_level": "transform",
      "parameters_schema": {},
      "required_validations": []
    }
  ]
}
```

公开清单不得包含 handler 函数、模块路径或内部 Python 类型。

Skill 的预检流程改为：

1. 执行 `inspect`。
2. 执行 `capabilities`，不读取源码判断功能。
3. 对用户核心要求和能力清单做覆盖检查。
4. 能力不足时立即返回 `CAPABILITY_UNSUPPORTED`。
5. 只有覆盖完整时才生成、编译和执行计划。

## 9. 经营汇总配方调整

标准计划顺序调整为：

```text
read_table
  -> filter_rows（日期、清洗状态、退货等）
  -> select_columns（可选）
  -> derive_column（需要组合标签或静态派生时）
  -> aggregate
  -> sort_rows
  -> create_sheet
  -> write_table
  -> add_formula_column（需要可更新公式时）
  -> apply_style_preset
  -> freeze_header
  -> create_chart
```

配方必须把过滤所需字段加入 `read_table.fields`。例如用户要求有效且未退货订单时，读取字段必须包含 `清洗状态` 和 `是否退货`，即使它们不出现在最终结果表。

业务 Validator 必须从原输入独立应用相同的结构化过滤条件，但不得调用执行过程产生的 `TableData`。过滤条件契约可以复用，执行结果不可复用。

## 10. 变更记录与验收

### 10.1 变更类型

ChangeRecorder 统一记录：

```text
read
transform
create_sheet
write_values
write_formulas
write_styles
freeze_panes
create_chart
```

纯数据变换记录行数统计，不计入工作簿写入预算。写操作记录精确范围和对象数。

### 10.2 验收绑定

注册表中的 `required_validations` 只增加检查，不允许降低 ExecutionPlan 已声明严重度。例如：

| 能力 | 必需验收 |
|---|---|
| `filter_rows` | `business_reconciliation`、过滤行数证据 |
| `aggregate` | `business_reconciliation` |
| `write_table` | `declared_change_match`、结果区域存在 |
| `add_formula_column` | `formula_scan`、填充模式 |
| `apply_style_preset` | `layout` |
| `create_chart` | `layout`、图表引用检查 |

## 11. 测试策略

### 11.1 注册表契约测试

遍历每个已注册能力，验证：

- 名称唯一；
- 参数模型可拒绝未知参数；
- handler 可调用且返回声明的输出类型；
- 声明引擎与真实契约一致；
- 风险级别和副作用一致；
- 公开 manifest 可 JSON 序列化；
- Compiler 接受所有已注册能力；
- Dispatcher 不存在注册表外的执行分支。

### 11.2 工具单元测试

每个工具至少覆盖：

- 正常路径；
- 边界值；
- 参数缺失和未知参数；
- 输入类型错误；
- 空数据；
- 预算或授权失败；
- ChangeRecorder 记录；
- 序列化结果。

### 11.3 集成测试

至少提供三份异构输入：

1. 原生日期、单维度、干净数值。
2. ISO 文本日期、双维度、有效/退货过滤和缺失金额。
3. 负值、空分类、重复订单和无匹配日期边界。

第二份使用 `U3_builtin_dirty_orders_report.xlsx`，验收：

- 文本日期正确解析；
- 只保留 `清洗状态=有效` 且 `是否退货=否`；
- 缺失销售额按声明策略处理并留下证据；
- 城市和渠道双维度汇总正确；
- 图表引用数值系列而不是文本维度；
- 原工作表值和公式不变；
- 独立业务复算通过。

## 12. 实施顺序

### 阶段 A：消除能力漂移

1. 建立 `CapabilityDefinition` 和 `CapabilityRegistry`。
2. 把当前 7 个可执行能力注册进去。
3. Compiler 和 Dispatcher 改用同一注册表。
4. 从运行时声明中移除未实现能力。
5. 增加 `sheetpilot capabilities` 和注册表契约测试。

完成条件：任何 Compiler 可接受的 handler 都能被 Dispatcher 执行；任何 Dispatcher 可执行的 handler 都来自注册表。

### 阶段 B：打通脏订单用例

1. 实现日期标准化。
2. 实现 `filter_rows`。
3. 调整经营汇总配方，将日期和业务过滤前置。
4. 调整业务 Validator 独立应用过滤条件。
5. 增加空结果早期错误。

完成条件：脏订单测试不需要手工修改 JSON 或绕过 SheetPilot。

### 阶段 C：完善表格变换

1. 实现 `select_columns`。
2. 实现 `sort_rows`。
3. 实现 `derive_column` 的白名单模板。
4. 修正双维度图表引用。

完成条件：经营汇总的读取、清洗、汇总、排序和图表均由注册能力覆盖。

### 阶段 D：公式和样式

1. 实现公式模板注册表和 `add_formula_column`。
2. 扩展样式预设。
3. 增加公式和布局验收。

完成条件：公式只由白名单模板生成，并能通过文本、范围和可选真实重算验证。

## 13. 迁移兼容性

- 现有高层计划中已支持的 7 个能力保持名称不变。
- 现有 `aggregate.current_period` 在一个过渡版本中继续接受，但 Compiler 将其规范化为前置 `filter_rows`，并产生弃用 warning。
- 新计划禁止使用 `aggregate.current_period`；日期范围统一放在 `filter_rows`。
- 旧执行计划仍按其绑定版本重放，不在运行时自动改写。
- 注册表或参数的不兼容变化升级能力主版本，并要求重新编译计划。

## 14. 完成定义

能力层重构完成必须同时满足：

1. 运行时不存在第二份 handler 白名单。
2. 未实现能力不能通过编译。
3. 每个注册能力都有严格参数模型和独立测试。
4. Compiler 和 Dispatcher 对能力、引擎和参数的判断一致。
5. Skill 通过 `sheetpilot capabilities` 判断支持范围，不读取源码。
6. 核心需求未覆盖时在执行前失败。
7. 文本日期和结构化过滤在脏订单用例中通过。
8. 空结果在过滤或聚合步骤失败，不伪装成图表错误。
9. 实际写入范围、变更预算和 Validator Diff 可以三方核对。
10. 完整 `unittest` 和三份异构端到端测试通过。
