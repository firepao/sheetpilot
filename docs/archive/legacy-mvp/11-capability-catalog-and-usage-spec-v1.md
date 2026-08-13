# SheetPilot 原子与分子能力目录及使用规范 V1

## 1. 文档定位

`10-atomic-and-molecular-capability-architecture-v1.md` 定义分层和总体架构；本文将其中的能力落成开发契约，供以下模块共同使用：

```text
能力注册表、CLI/MCP 适配器、Coverage Planner、Composed Plan Builder、Executor、Validator、Skill 和契约测试
```

本文中的 `AVAILABLE` 表示已经具备实现、适配器、参数校验、审计和测试。仅写在本文中的能力不能被 Agent 当作当前可用能力。

## 2. 统一定义

### 2.1 Atom 定义

```python
AtomDefinition(
    id="read_table",
    version="1.0",
    parameter_schema=ReadTableParams,
    input_ports=(Port("workbook", "WorkbookRef"),),
    output_ports=(Port("table", "TableData"),),
    effects={"read_workbook"},
    executor=...,                 # in-process / CLI / MCP
    validators=("read_contract",),
    status="AVAILABLE",
)
```

Atom 必须满足：单一动作、严格参数、类型化输入输出、明确副作用、可独立记录和可独立测试。Atom 不包含业务流程，不接受 Python 表达式、Shell 命令或任意公式源码。

### 2.2 Molecule 定义

```python
MoleculeDefinition(
    id="summarize_by_dimension",
    version="1.0",
    parameter_schema=SummarizeParams,
    input_ports=(Port("source", "TableRef"),),
    output_ports=(Port("table", "TableData"), Port("range", "RangeRef")),
    effects={"read_workbook", "create_sheet", "write_values", "write_styles"},
    expander=expand_summarize_by_dimension,
    validators=("aggregation_reconciliation",),
    status="AVAILABLE",
)
```

Molecule 是多步 Excel 操作模式。它必须由 `expander` 生成 `PlanFragment`，而不是在 Dispatcher 中作为不可见黑盒函数执行。Fragment 中的节点只能引用已注册 Atom 或受限 Dynamic Transform。

### 2.3 通用调用结构

简单任务允许 Agent 直接调用 Atom/Molecule：

```json
{
  "capability": "summarize_by_dimension",
  "version": "1.0",
  "arguments": {
    "source": {"sheet": "订单", "header_row": 1},
    "group_by": ["区域"],
    "metrics": [{"field": "金额", "function": "sum", "as": "金额合计"}],
    "target": {"sheet": "区域汇总", "anchor": "A1"}
  }
}
```

复杂任务中 Agent 只提交同一份 `CompositionRequest`；Builder 负责把 Molecule 展开成执行计划。

### 2.4 引用类型

| 类型 | 含义 | 典型来源 |
|---|---|---|
| `WorkbookRef` | 工作副本 | `inspect_workbook` |
| `TableRef` | 带字段和来源的逻辑表 | `resolve_table` |
| `TableData` | 内存表数据 | `read_table`、`aggregate` |
| `RangeRef` | 最终 XLSX 中的矩形区域 | `write_table` |
| `CellRef` | 单个单元格 | `write_scalar` |
| `ScalarRef` | 有来源和可选单元格绑定的指标 | `compute_scalar` |
| `MetricSetRef` | 一组 ScalarRef | `compute_scalar_metrics` |
| `ChartRef` | 原生 Excel 图表 | `create_chart` |
| `CheckBlockRef` | 检查区块 | `build_check_block` |

裸字符串只能用于字段名、Sheet 名和模板 ID，不能用来隐式表示步骤依赖。

## 3. Atom 目录

### 3.1 `inspect_workbook`

用途：建立输入事实画像。

参数：

```json
{"input_file": "input.xlsx", "sample_rows": 20, "max_sheets": 100}
```

输出：`WorkbookProfile`，包括文件哈希、Sheet、有效范围、候选表头、字段类型、公式数、图表数和风险对象。

使用：所有复杂任务的第一步；不修改文件。

验证：文件存在、扩展名支持、哈希稳定、OOXML 可重开。

### 3.2 `resolve_table`

用途：把语义字段解析为确定的 Sheet、表头行和列地址。

参数：

```json
{
  "workbook": "profile",
  "sheet": "订单",
  "header_row": 1,
  "fields": ["日期", "区域", "金额"]
}
```

输出：`TableRef`。字段不存在、重复或置信度不足时阻断，不自动猜测。

### 3.3 `read_table`

用途：有界读取字段并保留源行号。

参数：

```json
{
  "source": "orders_ref",
  "fields": ["日期", "区域", "金额"],
  "max_rows": 200000,
  "empty_row_policy": "skip"
}
```

输出：`TableData`，每行包含 provenance 中的源行号。

约束：禁止整列无限读取；公式、数字、日期保持原类型；空表和超预算分别返回明确错误。

### 3.4 `read_range`

用途：读取已授权范围，适用于非标准表格、指标区块和已有结果复核。

参数：`{"range": {"sheet": "汇总", "address": "A1:F20"}}`。

输出：二维值或带表头的 `TableData`。范围必须来自 Inspector 或计划声明。

### 3.5 `select_columns`

用途：字段选择、重排和安全重命名。

参数：

```json
{"input": "source_table", "fields": [{"source": "金额", "as": "营收"}]}
```

输出：字段顺序变化的 `TableData`。不改变行数和类型。

### 3.6 `filter_rows`

用途：按受控条件筛选。

参数：

```json
{
  "input": "source_table",
  "where": {"all": [{"field": "状态", "op": "eq", "value": "有效"}]},
  "invalid_value_policy": "exclude"
}
```

支持 `eq/ne/gt/gte/lt/lte/in/not_in/is_null/not_null/contains/between`；最多两层逻辑嵌套。不得使用 `eval`。

输出 metrics：`input_rows`、`output_rows`、`excluded_rows`、`invalid_rows`。

### 3.7 `normalize_values`

用途：按显式规则统一文本、日期、枚举和数字。

参数：

```json
{
  "input": "source_table",
  "rules": [
    {"field": "区域", "template": "trim"},
    {"field": "日期", "template": "parse_date", "source_format": "%Y/%m/%d"}
  ],
  "error_policy": "mark"
}
```

输出：标准化 `TableData` 及字段级错误统计。歧义日期必须显式提供格式。

### 3.8 `derive_column`

用途：只在内存中生成派生字段。

参数：`{"input":"table","as":"利润","template":"subtract","arguments":{"left":"营收","right":"成本"}}`。

模板：`add`、`subtract`、`multiply`、`safe_divide`、`coalesce`、`date_year`、`date_month`。零除和空值策略必填或使用安全默认值。

### 3.9 `aggregate`

用途：通用分组聚合。

参数：

```json
{
  "input": "valid_rows",
  "group_by": ["区域", "类别"],
  "metrics": [
    {"field": "营收", "function": "sum", "as": "营收合计"},
    {"field": "订单号", "function": "count_distinct", "as": "订单数"}
  ],
  "null_group_policy": "label",
  "null_group_label": "(空)"
}
```

函数：`sum`、`count`、`count_distinct`、`average`、`min`、`max`。非法数值不能静默当零。

### 3.10 `sort_rows`

用途：稳定排序汇总或明细。

参数：`{"input":"summary","keys":[{"field":"营收合计","direction":"desc","nulls":"last"}]}`。

混合类型默认拒绝；多键排序必须保持稳定。

### 3.11 `compute_scalar`

用途：从表格、范围或已有指标计算单个可引用标量。

参数：

```json
{
  "input": "valid_rows",
  "id": "valid_revenue",
  "function": "sum",
  "field": "营收"
}
```

支持：`count_rows`、`count_nonblank`、`count_if`、`count_distinct`、`sum`、`sum_if`、`average`、`min`、`max`。输出包括运行时值、来源和参与行数。

### 3.12 `compare_scalars`

用途：比较两个 ScalarRef 并生成差异和布尔结果。

参数：`{"left":"detail_total","right":"summary_total","operator":"approx_eq","tolerance":0.01}`。

它不直接写 Sheet；写入由 `write_scalar` 或 `build_check_block` 完成。

### 3.13 `create_sheet`

用途：创建计划授权的新 Sheet。

参数：`{"sheet":"经营总览","on_conflict":"fail"}`。

默认禁止删除、替换和修改用户已有 Sheet。返回 `SheetRef` 和变更记录。

### 3.14 `write_table`

用途：将表格写入精确矩形范围。

参数：`{"input":"summary","sheet":"经营总览","anchor":"A10","include_header":true}`。

返回精确 `RangeRef`；执行前检查授权上限，执行后记录实际范围。

### 3.15 `write_values`

用途：写标题、标签和小型二维区块。

参数：`{"sheet":"检查","anchor":"A1","values":[["检查项","状态"],["行数守恒","PASS"]]}`。

只允许有界数据；大表必须使用 `write_table`。

### 3.16 `write_formula_column`

用途：向现有结果区域增加真实公式列。

参数：

```json
{
  "input": "detail_range",
  "header": "利润率",
  "template": "safe_ratio",
  "arguments": {"numerator": "利润", "denominator": "营收"},
  "number_format": "0.00%"
}
```

公式模板必须来自注册表；执行后扫描公式数量和填充范围。

### 3.17 `write_formula_cells`

用途：在明确 CellRef 上写入检查和 KPI 公式。

参数：`{"cells":[{"cell":"B3","template":"count_if","arguments":{...}}]}`。

不接受任意公式字符串；每个模板必须声明允许的引用类型。

### 3.18 `write_scalar`

用途：把 ScalarRef 写入单元格。

参数：`{"scalar":"valid_count","cell":{"sheet":"检查","address":"B3"},"mode":"both","number_format":"0"}`。

`formula`/`both` 模式必须写真实公式并保存运行时复算值用于验收。

### 3.19 `apply_style_preset`

用途：对已写入区域应用版本化样式。

参数：`{"range":"summary_range","preset":"business_table","version":"1.0"}`。

不得传递 openpyxl 对象或任意样式代码。

### 3.20 `set_number_format`

用途：设置受控数字格式。

参数：`{"range":"profit_range","format":"#,##0.00"}`。

支持货币、整数、小数、百分比和日期格式；不改变底层值类型。

### 3.21 `set_column_widths`

用途：按字段类型或有限样本设置列宽。

参数：`{"range":"summary_range","policy":"bounded_auto","min":8,"max":40}`。

禁止无界 autofit。

### 3.22 `freeze_panes`

用途：冻结表头或指定首个滚动单元格。

参数：`{"sheet":"经营总览","cell":"A4"}`。

只允许新建 Sheet 或明确授权布局修改。

### 3.23 `add_conditional_format`

用途：添加受控条件格式。

首期规则：`equals`、`not_equals`、`negative`、`data_bar`。不允许任意公式条件。

### 3.24 `create_chart`

用途：创建单个原生 Excel 图表。

参数：

```json
{
  "input":"summary_range",
  "chart_type":"column",
  "category_fields":["区域"],
  "series_fields":["营收合计"],
  "anchor":"H3",
  "title":"区域营收"
}
```

必须显式指定分类和系列，不能依赖“第一列分类、其他列系列”的猜测。

### 3.25 `create_excel_table`

用途：把结果 RangeRef 转为原生 Excel Table。

参数：`{"range":"detail_range","name":"CleanDetail"}`。

表名唯一且符合 Excel 规则。结构化引用可供公式和图表使用。

## 4. 分子目录

### 4.1 `add_source_trace`

**语义**：为任意明细表增加源行号、源 Sheet 等追溯字段。

**参数**：

```json
{
  "source":"source_table",
  "columns":[
    {"kind":"source_row","as":"原始行号"},
    {"kind":"source_sheet","as":"来源Sheet"}
  ],
  "target":{"sheet":"明细","anchor":"A1"},
  "write_mode":"value"
}
```

**展开**：`read_table -> derive trace columns -> create_sheet -> write_table -> style/freeze`。

**输出**：`TableRef`、`RangeRef`。**验证**：行数相等、源行号非空且唯一、源范围有效。

### 4.2 `normalize_columns`

**语义**：按字段规则标准化文本、日期、枚举或数字。

**参数**：规则数组、错误策略、标准化字段命名策略、目标位置和写入模式。

**展开**：`read_table -> normalize_values -> optional write_table -> set_number_format`。

**验证**：规则应用计数、失败值计数、日期解析统计和原始值可追溯。

### 4.3 `classify_rows`

**语义**：按可配置规则生成状态、原因和严重级别。

**参数**：字段规则、状态/原因列名、`value/formula/both` 模式。

**展开**：`normalize/derive -> evaluate rules -> add status/reason -> write`。

**验证**：有效数 + 异常数 = 输入数；每个异常行至少有一个原因；规则 ID 可追溯。

### 4.4 `add_formula_metrics`

**语义**：用通用公式模板增加派生指标列。

**参数**：目标表、指标列表、模板参数、零值策略、数字格式、输出模式。

**展开**：`resolve columns -> write_formula_column x N -> format -> formula_scan`。

**模板**：`add`、`subtract`、`multiply`、`safe_ratio`、`percentage_change`、`date_period`。利润和利润率只是模板参数的一个使用实例，不是独立业务能力。

**验证**：公式真实存在、覆盖所有明细行、引用列正确、独立复算与运行时结果一致。

### 4.5 `summarize_by_dimension`

**语义**：按任意维度聚合任意指标，并可排序、写入和格式化。

**参数**：`source`、`where`、`group_by`、`metrics`、`sort`、`target`、`style`、`write_mode`。

**展开**：`read/use -> filter_rows? -> aggregate -> sort_rows? -> create_sheet -> write_table -> style/format`。

**验证**：输入与输出指标守恒、分组键唯一、结果区域精确、空结果明确失败。

### 4.6 `summarize_by_period`

**语义**：按日/周/月/季度/年进行周期标准化和聚合。

**参数**：日期字段、周期粒度、源日期格式、无效日期策略、指标和目标。

**展开**：`normalize date -> derive period -> summarize_by_dimension`。

**验证**：期间覆盖、无效日期计数、总额守恒和结果排序。

### 4.7 `compute_scalar_metrics`

**语义**：一次计算一组可被 KPI、检查和图表复用的标量。

**参数**：输入引用、指标定义数组、过滤条件、输出模式。

**展开**：`compute_scalar x N -> MetricSetRef`。

**验证**：每个指标 ID 唯一、类型正确、来源完整、运行时结果可复算。

### 4.8 `write_metric_block`

**语义**：将指标组写成可读、可追溯的 KPI 区块。

**参数**：MetricSet、目标 Sheet/锚点、横向/纵向布局、模式、样式、格式。

**展开**：`create_sheet? -> write_values labels -> write_scalar x N -> style/format`。

**验证**：实际 KPI 数达到 Requirement 的 `minimum_count`；公式模式下公式数和引用正确。

### 4.9 `build_check_block`

**语义**：从 ScalarRef 和受控标量表达式生成对账/质量检查区块。

**参数**：检查项、左右引用、运算符、容差、目标位置、输出模式。

**展开**：`resolve scalars -> write labels/values/formulas -> difference -> PASS/FAIL -> conditional format`。

**验证**：独立重算所有检查；任何 critical FAIL 都阻止发布。

### 4.10 `create_chart_block`

**语义**：为一个或多个汇总 RangeRef 创建原生 Excel 图表。

**参数**：源区域、图表定义数组、分类/系列字段、锚点布局、数量约束。

**展开**：`validate ranges -> resolve anchors -> create_chart x N -> layout check`。

**验证**：原生图表数量、图表类型、系列引用、锚点不遮挡数据区；PNG 不属于此能力。

### 4.11 `build_analysis_section`

**语义**：把汇总表、指标区块和图表组成通用分析区块。

**参数**：标题、汇总定义、可选 KPI、图表、布局策略和目标 Sheet。

**展开**：`summarize_by_dimension + write_metric_block? + create_chart_block? + layout`。

**边界**：不定义“经营总览”“订单报表”等业务名称；这些由 TaskSpec 的输出布局提供。

## 5. 能力使用规范

### 5.1 简单任务

简单任务可直接调用一个 Molecule：

```text
用户：按区域汇总金额，写到新 Sheet。
Agent：inspect -> resolve_table -> summarize_by_dimension -> validate。
```

不需要 Agent 手写 Atom DAG。

### 5.2 复杂任务

复杂任务必须提交 RequirementSet：

```json
[
  {"id":"traceability","critical":true},
  {"id":"formula_columns","constraints":{"minimum_count":2},"critical":true},
  {"id":"kpi","constraints":{"minimum_count":4},"critical":true},
  {"id":"native_charts","constraints":{"minimum_count":2},"critical":true},
  {"id":"reconciliation","critical":true}
]
```

Planner 先返回覆盖矩阵；存在 critical `UNCOVERED` 时禁止执行和交付。

### 5.3 动态缺口

只有当缺口是纯 `TableData` 变换且没有稳定 Molecule 时，才使用 Dynamic Transform。动态结果仍通过 `write_table`、`write_formula_column` 或 `write_scalar` 落盘，不能让动态脚本绕过能力授权。

## 6. 注册、版本和测试要求

每个 Atom/Molecule 注册必须包含：

```text
id、version、status、参数 Schema、输入端口、输出端口、引擎、预计副作用、Validator、示例和测试 ID
```

注册前检查：

1. 重复 ID 和版本冲突；
2. Schema 是否拒绝未知参数；
3. 所有引用类型是否可解析；
4. Molecule 展开后是否只引用 AVAILABLE Atom；
5. 预计副作用是否覆盖展开副作用；
6. Requirement 覆盖声明是否包含数量、公式和 Sheet 约束；
7. 最终 XLSX 是否有独立验证测试。

## 7. MVP 实施顺序

1. **目录与引用类型**：Atom/Molecule Definition、Ref、StepResult、Manifest。
2. **标量与公式基础**：`compute_scalar`、`write_scalar`、`write_formula_column`、公式模板。
3. **写入型 Molecule**：`summarize_by_dimension`、`add_formula_metrics`、`write_metric_block`、`build_check_block`。
4. **组合器**：Coverage Planner、参数绑定、Fragment 展开、DAG 合并和硬门禁。
5. **图表与分析区块**：`create_chart_block`、`build_analysis_section`，只验证 XLSX 原生对象。
6. **真实任务回归**：脏订单作为组合评测，不注册专用 Recipe。
7. **动态 Transform 反馈**：重复逻辑沉淀为模板或 Molecule；PNG Renderer 单独开发。

## 8. 完成定义

当以下条件全部满足，原子/分子能力重构的 MVP 才算完成：

- 简单任务可以直接调用 Atom/Molecule；
- 复杂任务不要求 Agent 手写 DAG；
- 每个分子能力能展开为可审计 Atom；
- 分子能力可以实际创建 Sheet、写值、写公式、写检查和图表；
- 标量有统一来源和单元格引用；
- critical Requirement 未覆盖时不会执行或发布；
- Validator 独立检查最终 XLSX；
- CLI、MCP、Skill、Planner 和 Executor 没有重复能力清单；
- 脏订单测试验证的是组合能力，而不是专用 Recipe。
