# 详细架构设计

## 1. 模块分层

```text
交互层
  Agent / Skill / 用户确认 / 进度事件

决策层
  Requirement Normalizer / Planner / Plan Compiler / Policy Gate

能力层
  Capability Registry / Templates / Task Scripts / Atomic Tools

执行层
  Executor / Dynamic Script Runner / Engine Pipeline Adapters / Export Finalizer

质量层
  Structural / Formula / Business / Recalculation / Visual Validators

基础设施层
  Artifact Manager / Event Log / Task Workspace / Security Policy
```

## 2. 任务状态机

```text
CREATED
  -> INSPECTING
  -> PLANNING
  -> PLAN_REVIEW
  -> WAITING_CONFIRMATION (optional)
  -> PREPARING_WORKSPACE
  -> EXECUTING
  -> VERIFYING_WORK_STATE
  -> EXPORTING
  -> FINALIZING
  -> VALIDATING_DELIVERY
  -> REPAIRING (optional, may repeat)
  -> SUCCEEDED | FAILED | NEEDS_USER_ACTION
```

状态变化必须写入事件日志。`SUCCEEDED` 只能由 Validator 产生，Executor 无权直接标记成功。

## 3. 任务目录和产物

```text
runs/<task_id>/
├── input/
│   └── original.xlsx
├── working/
│   ├── working.xlsx
│   ├── working.unv/
│   └── generated_scripts/
├── output/
│   ├── result.xlsx
│   ├── previews/
│   └── audit-report.json
├── metadata/
│   ├── workbook-profile.json
│   ├── import-baseline.json
│   ├── work-state-evidence.json
│   ├── export-evidence.json
│   ├── normalized-requirements.json
│   ├── selected-plan.json
│   ├── confirmation.json
│   └── manifest.json
└── logs/
    ├── events.jsonl
    ├── tool-calls.jsonl
    └── execution.log
```

`original.xlsx` 必须保持只读并记录 SHA-256。输出文件名不得与输入文件相同。

`working.xlsx` 与 `working.unv` 是不同引擎可能采用的工作态，单个任务只使用实际选定的一种。最终 `result.xlsx` 是交付态，不得被当作工作态反复导入和修改。

## 4. 结构化需求模型

```json
{
  "task_type": "operating_report",
  "requirements": [
    {
      "id": "monthly_summary",
      "category": "analysis",
      "required": true,
      "parameters": {
        "date_field": "订单日期",
        "value_field": "销售额"
      },
      "acceptance": {
        "aggregation": "sum",
        "period": "month"
      }
    },
    {
      "id": "waterfall_chart",
      "category": "visualization",
      "required": true,
      "parameters": {
        "target_sheet": "经营总览"
      }
    }
  ],
  "constraints": {
    "preserve_existing_content": true,
    "overwrite_input": false,
    "validation_level": "strict"
  }
}
```

每个必需需求必须映射到至少一个计划步骤和至少一条验收规则。

## 5. 工作簿画像

Inspector 生成统一画像：

```json
{
  "file": {
    "format": "xlsx",
    "sha256": "...",
    "size_bytes": 123456
  },
  "sheets": [
    {
      "name": "销售明细",
      "used_range": "A1:H5000",
      "headers": ["订单日期", "区域", "产品", "数量", "单价", "销售额"],
      "formula_count": 4999,
      "chart_count": 0
    }
  ],
  "advanced_features": {
    "vba": false,
    "power_query": false,
    "data_model": false,
    "pivot_tables": false,
    "slicers": false,
    "external_links": false
  },
  "risk_level": "LOW"
}
```

Inspector 不执行写操作。对于无法解析的对象，必须记录 `unknown_features`，不能默认视为不存在。

## 6. 能力注册表

### 6.1 能力类型

| 类型 | 粒度 | 示例 |
|---|---|---|
| Template | 固定工作簿结构 | 经营分析报表模板 |
| Task Script | 完整业务流程 | 预算实际对比、三表模型 |
| Atomic Tool | 通用操作 | 写公式、创建图表、格式化范围 |
| Dynamic SDK | 动态脚本允许调用的受控 API | WorkbookContext |
| Engine Capability | 引擎原生能力 | 重算、VBA、Power Query |
| Pipeline Capability | 引擎流程能力 | XLSX 导入、工作态读回、XLSX 导出 |
| Finalizer | 导出物修复能力 | 图表缓存、drawing 关系、颜色规范化 |
| Validator | 验收能力 | 公式检查、资产负债勾稽 |

### 6.2 能力清单示例

```yaml
id: sales_operating_report
version: 1.0.0
type: task_script
engine_requirements:
  any_of: [openpyxl, com, univer]
input_policy:
  accepts_real_input: true
  synthetic_only: false
accepts:
  formats: [xlsx]
  required_semantic_fields:
    - date
    - product
    - quantity
    - unit_price
provides:
  capabilities:
    - revenue_formula
    - monthly_summary
    - product_summary
    - operating_dashboard
parameters:
  theme:
    type: string
    enum: [default, executive, audit]
limitations:
  - no_multi_currency
  - no_power_query
  - fixed_dashboard_regions
side_effects:
  creates_sheets: true
  modifies_existing_sheets: false
risk: LOW
validators:
  - revenue_formula_validator
  - summary_reconciliation_validator
  - dashboard_visual_validator
delivery_contract:
  format: xlsx
  requires_export_finalizer: when_charts_present
  validate_work_state: true
  validate_delivery_state: true
```

### 6.3 原子工具示例

```yaml
id: create_chart
version: 1.0.0
type: atomic_tool
input:
  workbook: workbook_ref
  source_range: range_ref
  target_sheet: sheet_ref
supports:
  chart_types: [bar, line, pie, scatter]
limitations:
  - no_waterfall
  - no_pivot_chart
preconditions:
  - source_range_exists
  - numeric_series_exists
output:
  chart: chart_ref
risk: LOW
```

## 7. 需求覆盖与路由算法

### 7.1 匹配层级

匹配必须同时检查：

1. 能力名称是否覆盖。
2. 参数是否支持。
3. 输入前置条件是否满足。
4. 引擎是否具备所需能力。
5. 保真约束是否满足。
6. 是否存在对应验收器。
7. 能否从输入格式安全进入该引擎的工作态。
8. 能否从工作态可靠导出用户要求的交付格式。
9. 该能力是否允许消费真实输入，还是只能生成合成工作簿。

### 7.2 候选计划评分（第二阶段）

MVP 先使用必需需求覆盖、输入输出兼容、引擎支持、可验收和风险规则进行硬过滤，不实现复杂权重调参。固定能力数量和组合数量增长后，再使用以下概念评分：

```text
score =
  coverage_weight * requirement_coverage
  + determinism_weight * fixed_capability_ratio
  + validation_weight * automatic_validation_ratio
  + fidelity_weight * preservation_confidence
  - risk_weight * risk_score
  - dynamic_weight * dynamic_code_ratio
  - cost_weight * execution_cost
```

硬性条件优先于分数：必需需求未覆盖、用户约束冲突或缺少验收方式时，候选计划不得入选。

### 7.3 路由伪代码

```python
def select_plan(requirements, workbook_profile, registry):
    candidates = []

    candidates += match_single_templates(requirements, registry)
    candidates += extend_templates_with_tools(requirements, registry)
    candidates += compose_task_scripts(requirements, registry)
    candidates += compose_atomic_tools(requirements, registry)

    valid = [
        plan for plan in candidates
        if deterministic_plan_review(plan, requirements, workbook_profile).passed
    ]

    if valid:
        return max(valid, key=score_plan)

    partial = best_partial_plan(candidates)
    gaps = compute_uncovered_requirements(partial, requirements)
    return add_minimal_dynamic_steps(partial, gaps)
```

## 8. 多工具和多脚本编排

执行计划使用有向无环图表示：

```json
{
  "steps": [
    {
      "id": "inspect",
      "capability": "inspect_workbook",
      "depends_on": []
    },
    {
      "id": "normalize",
      "capability": "normalize_sales_data",
      "depends_on": ["inspect"]
    },
    {
      "id": "base_report",
      "capability": "sales_operating_report",
      "depends_on": ["normalize"]
    },
    {
      "id": "custom_waterfall",
      "mode": "dynamic_patch",
      "covers": ["waterfall_chart"],
      "depends_on": ["base_report"]
    },
    {
      "id": "strict_audit",
      "capability": "strict_audit",
      "depends_on": ["custom_waterfall"]
    }
  ]
}
```

Plan Compiler 必须验证：

- 图中不存在循环依赖。
- 每一步输入由前置步骤或任务输入提供。
- 两个步骤不会以不兼容方式修改同一区域。
- 非幂等步骤不会被无条件重试。
- 所有动态步骤都明确声明补齐的能力缺口。
- 最后必须存在与需求相匹配的验收步骤。

## 9. 确定性计划审核

计划审核器至少检查：

```json
{
  "coverage": {
    "required_total": 5,
    "covered": 4,
    "uncovered": ["waterfall_chart"]
  },
  "compatibility": {
    "inputs_valid": true,
    "engine_supported": true,
    "conflicts": []
  },
  "policy": {
    "overwrites_input": false,
    "requires_confirmation": true,
    "reasons": ["modifies_existing_formulas"]
  },
  "decision": "REJECTED"
}
```

结构、类型、路径、依赖和权限使用确定性代码检查；字段语义和业务意图可以由评审 LLM 辅助，但不能由评审 LLM 绕过硬规则。

## 10. Dry Run

Dry Run 在真正写文件前检查：

- 工作表和范围是否存在。
- 字段名称或语义映射是否成立。
- 数据类型是否满足公式和图表要求。
- 目标工作表、表格名、图表名是否冲突。
- 预计修改的单元格、公式、工作表和图表数量。
- 高级对象是否可能受损。
- 输出路径是否与输入路径不同。
- 引擎能否执行所需操作。
- 动态脚本是否通过静态安全检查。
- 导入是否可能丢失公式、样式、图表或高级对象。
- 工作态格式和最终交付格式是否明确。
- 导出后是否需要 Finalizer，以及 Finalizer 会修改哪些 OOXML 对象。

Dry Run 生成用户确认摘要：

```text
将创建：2 张工作表、3 张图表
将修改：860 个单元格、0 个现有公式
将保留：全部 6 张现有工作表
输出方式：另存为 result.xlsx
风险：将执行 1 个受限动态脚本，用于创建瀑布图
```

## 11. 动态脚本设计

### 11.1 启用条件

同时满足以下条件才可启用：

1. 结构化需求中存在必需能力缺口。
2. 能力注册表不存在合法的固定能力组合。
3. 当前引擎能够实现该需求。
4. 可以定义明确的验收规则。
5. 动态执行风险在允许范围内，或已得到用户确认。

### 11.2 局部补丁优先

动态脚本输入应是已完成大部分工作的工作副本，只允许修改声明的工作表和范围。例如：

```json
{
  "mode": "dynamic_patch",
  "allowed_sheets": ["经营总览"],
  "allowed_ranges": ["J2:R24"],
  "allowed_operations": ["write_values", "set_format", "create_chart"],
  "forbidden_operations": ["delete_sheet", "external_link", "run_macro"]
}
```

### 11.3 引擎专属受控运行时

动态脚本必须绑定执行引擎，不能假设一段 Python 可以跨所有引擎运行。优先让脚本调用引擎专属受控上下文，而不是直接访问文件系统：

```python
def execute(ctx):
    sheet = ctx.sheet("经营总览")
    sheet.write_values("J2:K8", data)
    sheet.create_chart(
        chart_type="waterfall",
        source_range="J2:K8",
        anchor="M2"
    )
```

`ctx` 负责路径限制、范围校验、日志记录和变更追踪。

对于 Univer，动态路径应收敛为一个顶层函数的 JavaScript 文件，通过公开 `run --file` 表面执行；修改前后使用 `inspect`、`search` 或 `pipe out` 读取工作簿可见状态。禁止直接编辑 `.unv` 包内部文件。

### 11.4 安全限制

- 只能访问任务工作目录。
- 禁止覆盖输入文件。
- 默认禁止网络。
- 禁止任意子进程。
- 仅允许白名单依赖。
- 限制运行时间、内存、文件数和输出大小。
- 禁止反射、动态导入和环境变量遍历。
- 禁止修改系统、注册表和 Agent 配置。
- 代码、参数、标准输出和异常全部归档。

## 12. 工作簿执行流水线接口

```python
class WorkbookPipeline(Protocol):
    engine_id: str

    def inspect_input(self, source: str) -> WorkbookProfile: ...
    def prepare_work_state(self, source: str, workspace: str) -> WorkState: ...
    def verify_import(self, state: WorkState, baseline: WorkbookProfile) -> Evidence: ...
    def execute(self, state: WorkState, plan: ExecutionPlan) -> ChangeSet: ...
    def read_work_state(self, state: WorkState, probes: list[Probe]) -> Evidence: ...
    def export(self, state: WorkState, output: str) -> ExportResult: ...
    def finalize(self, output: str, policy: FinalizePolicy) -> FinalizeResult: ...
    def validate_delivery(self, output: str, contract: DeliveryContract) -> ValidationReport: ...
```

原子读写 API 可以作为某个 Pipeline 的内部实现，但不作为跨引擎强制接口。这样可以避免把 Univer 的导入/包状态/导出语义，或 COM 的会话与重算语义，错误压缩成 `open_copy + save_as`。

每个引擎还需要暴露能力矩阵：

```json
{
  "engine": "openpyxl",
  "capabilities": {
    "formula_write": true,
    "formula_calculation": false,
    "basic_charts": true,
    "pivot_tables": false,
    "power_query": false,
    "vba_execute": false
  }
}
```

## 13. 高保真与引擎路由

引擎路由不只考虑能否执行，还要考虑是否会破坏现有对象：

```text
普通工作簿 + 基础公式/格式/图表
  -> 文件型引擎候选

含 VBA/Power Query/数据模型/复杂透视表
  -> COM 候选，或停止并提示风险

需要 Web 持续编辑和 Univer 状态
  -> Univer 候选
```

若检测到未知高级对象，默认采用保守策略，不允许文件型引擎静默保存。

### 13.1 Univer 真实输入流水线

```text
original.xlsx
  -> univer import -> working.unv
  -> inspect workbook/range 建立导入证据
  -> 一个任务脚本或一个有界动态 run 脚本
  -> inspect/pipe out 验证工作态
  -> univer export -> result.xlsx
  -> finalize-xlsx -> result.xlsx + preview.png + JSON 证据
  -> 独立交付态验收
```

规则：

- `bitagent-report` 仅用于没有真实输入且明确命中其固定结构的新建任务。
- 首次成功导入后，`working.unv` 成为本次执行的工作事实源；普通失败在该工作包上定向修复，不重复导入原文件。
- `.unv` 是否作为交付物由交付模式决定。XLSX-first 模式下，它只是中间态。
- Viewer 只用于交互审阅，不作为 XLSX 图表、公式或布局正确性的证据。
- Finalizer 是会修改导出文件的步骤，不是只读 Validator；执行后必须重新计算文件哈希并再次验收。

### 13.2 交付模式

| 模式 | 主要目标 | 必需验证 |
|---|---|---|
| XLSX-first（MVP 默认） | 最终 Excel 文件正确、快速交付 | 最终 XLSX、公式/业务、OOXML、必要预览 |
| Workspace-first | 保留可继续编辑的引擎工作态 | 工作态可打开、版本状态、最终 XLSX |
| Dual-delivery | 同时交付工作态与 XLSX | 两套状态分别验证，并记录可能的显示差异 |

## 14. 严格验收架构

### 14.1 结构验收

- 文件可打开且 OOXML 结构完整。
- 必需工作表、表格、命名范围和图表存在。
- 工作表名称、顺序和可见性符合计划。
- 原有工作表和关键区域未被意外删除。
- 与输入基线比较，确认导入和导出没有造成未声明的对象丢失。

### 14.2 公式验收

- 必需计算字段包含公式而不是静态值。
- 无 `#REF!`、明显循环引用和越界引用。
- 公式填充范围、绝对/相对引用符合规则。
- 汇总公式覆盖完整明细范围。

### 14.3 业务验收

根据任务注册专用断言，例如：

- 收入等于数量乘单价。
- 汇总收入等于明细收入。
- 资产等于负债加所有者权益。
- 现金流期末余额与资产负债表现金一致。
- DCF 估值由明确的自由现金流和折现率推导。

### 14.4 重算验收

`openpyxl` 只能写公式，不能计算公式。严格模式需要使用可用的真实 Excel、LibreOffice 或其他计算引擎重新计算。如果无法重算，报告必须标记为未完全验证，而不能给出无条件 PASS。

### 14.5 视觉验收

- 渲染关键工作表或指定范围。
- 检查文本截断、重叠、异常空白和列宽。
- 检查图表是否为空、图例和标题是否可读。
- 检查数字格式、颜色对比和冻结窗格。
- 可使用确定性图像规则加视觉评审模型，但最终应保留预览证据。
- 工作态 Viewer 预览和最终 XLSX 渲染证据不得互相替代。

### 14.6 需求覆盖验收

验收器从结构化需求逐项确认：

```json
{
  "requirement": "monthly_summary",
  "status": "PASS",
  "evidence": {
    "sheet": "经营总览",
    "range": "A10:C22",
    "formula_pattern": "SUMIFS"
  }
}
```

### 14.7 Finalizer 后验收

Finalizer 修复 chart cache、drawing 关系或其他 OOXML 后，至少重新检查：

- 文件仍可打开且关系完整。
- 图表公式引用、缓存和源范围一致。
- Finalizer 未改变业务单元格、公式文本或工作表结构。
- 输出哈希、修复清单和修复前后证据已归档。

## 15. 自动返修

失败分为：

| 类型 | 处理方式 |
|---|---|
| 参数错误 | 修正工具参数后重试 |
| 格式或布局问题 | 生成受限视觉修复计划 |
| 固定能力缺陷 | 切换工具或局部动态补丁 |
| 引擎不支持 | 切换引擎或请求用户接受降级 |
| 业务规则不明确 | 请求用户补充规则 |
| 文件可能损坏 | 停止执行，不交付不可信结果 |

自动返修必须限制次数。每次返修都基于新的验收证据，不允许无依据重复执行。

返修必须保留阶段边界：工作态错误在当前工作态定向修复并重新读回；导出错误优先重新导出；Finalizer 错误只允许针对交付物修复。除非工作态已经损坏或不可打开，否则不得重新导入原始文件并从头执行。

## 16. 用户确认模型

以下操作默认需要确认：

- 删除或重命名已有工作表。
- 修改大量已有公式。
- 覆盖超过阈值的单元格。
- 移除或降级高级 Excel 对象。
- 运行宏或刷新外部连接。
- 执行动态脚本中的中高风险操作。
- 切换到可能改变文件兼容性的引擎。

确认记录包含计划版本、文件指纹、变更摘要和用户选择。计划发生实质变化后，原确认失效。

## 17. 日志与事件

### 17.1 用户事件

```json
{
  "timestamp": "2026-07-31T10:20:30+08:00",
  "task_id": "task-123",
  "phase": "VALIDATING",
  "level": "info",
  "message": "正在检查财务勾稽关系",
  "progress": 82
}
```

### 17.2 工具调用日志

记录能力 ID、版本、参数摘要、输入输出引用、变更集合、耗时和错误。敏感数据和完整单元格内容不得默认写入普通日志。

### 17.3 变更集合

```json
{
  "step_id": "base_report",
  "changes": [
    {"type": "sheet_created", "sheet": "经营总览"},
    {"type": "range_written", "sheet": "经营总览", "range": "A1:H30"},
    {"type": "chart_created", "sheet": "经营总览", "anchor": "J2"}
  ]
}
```

## 18. 错误模型

统一错误类型：

- `INPUT_INVALID`
- `WORKBOOK_UNSUPPORTED`
- `CAPABILITY_GAP`
- `PLAN_INVALID`
- `USER_CONFIRMATION_REQUIRED`
- `POLICY_VIOLATION`
- `ENGINE_ERROR`
- `SCRIPT_REJECTED`
- `EXECUTION_TIMEOUT`
- `VALIDATION_FAILED`
- `REPAIR_EXHAUSTED`

不得把认证、路径、引擎、脚本和超时错误统一归类为“执行失败”。

## 19. Skill 结构建议

```text
skills/excel-agent/
├── SKILL.md
├── references/
│   ├── routing-policy.md
│   ├── risk-policy.md
│   ├── validation-policy.md
│   └── engine-compatibility.md
├── schemas/
│   ├── requirement.schema.json
│   ├── capability.schema.json
│   └── plan.schema.json
└── scripts/
    ├── inspect_workbook.py
    ├── validate_plan.py
    └── audit_workbook.py
```

Skill 应重点规定决策和质量流程，不应复制所有模板实现代码。

### 19.1 BitAgent 接入契约

迁移版 Univer 的实际接入不是代码内嵌，而是以下安装和调用契约：

1. 安装器将 `using-univer-cli`、`univer-cli`、规划、执行和测试 Skill 复制到 `%USERPROFILE%\.agents\skills`。
2. 安装器部署离线 `univer-cli` 到 npm 全局包目录，并生成 `univer.cmd` 等命令入口。
3. 安装器部署 `univer-cli-guard`，把其 `bin` 放在用户 PATH 前部。
4. 安装器将 Skill 内原机器的绝对路径替换为当前机器路径。
5. BitAgent 重启后扫描 Skill 目录，根据 Skill 描述决定何时调用命令。
6. BitAgent 通过 Shell 执行 Guard，而不是直接调用 Node 模块。
7. Guard 每次执行前检查并恢复补丁，再转发给 patched CLI。
8. CLI 通过退出码、JSON 标准输出和文件路径向 BitAgent返回结果。

### 19.2 CLI 命令注入方式

迁移版保留官方 CLI 核心入口，并用新的 `bin/univer.js` 作为包装入口：

```text
univer.cmd
  -> patched bin/univer.js
       ├── bitagent-report -> internal/bitagent-report.js
       ├── finalize-xlsx  -> internal/finalize-xlsx.js
       ├── export 成功后  -> export-chart-cache-fix.js
       └── 其他命令       -> bin/univer-core.js
```

这意味着“新增 BitAgent 能力”的本质是同时增加：

- Skill 中的触发条件、路由规则和验收要求。
- CLI 中可稳定调用的命令或维护脚本。
- 安装器中的部署、路径改写和验证逻辑。
- 机器可读结果及独立质量门。

只写 `SKILL.md` 不会产生执行能力；只安装 CLI 又不会让 BitAgent 稳定地选择正确命令。

### 19.3 新方案的接入建议

第一阶段沿用这种低侵入模式，但不复制其“直接补丁全局 npm 包”的脆弱做法：

```text
%USERPROFILE%\.agents\skills\excel-agent\
  -> SKILL.md / references / schemas

项目自有安装目录\excel-agent-runtime\
  -> excel-agent.cmd
  -> capability registry
  -> maintained task scripts
  -> engine pipelines
  -> validators
```

建议由自有 CLI 作为稳定入口，再把 openpyxl、Univer 或 COM 当作内部依赖。不要直接修改第三方全局包；如必须补丁，应固定版本、记录哈希，并在启动时做兼容检查。

CLI 对 BitAgent 至少提供：

- `inspect`：输出工作簿画像 JSON。
- `plan`：输出结构化计划和风险摘要。
- `execute`：执行已批准计划并输出事件流。
- `validate`：独立验证最终交付物。
- `capabilities`：返回当前安装的能力和引擎矩阵。

MVP 不必先实现 MCP。未来若需要远程调用、强类型工具参数、细粒度授权或并发 Worker，可在同一 Orchestrator 外增加 MCP Adapter，Skill 和任务契约无需重写。

## 20. 首批固定能力

### 20.1 任务级脚本

1. 通用经营分析报表。
2. 销售收入、成本和利润分析。
3. 预算与实际对比。
4. 基础三表财务模型。
5. 简化 DCF 与敏感性分析。

MVP 可先实现其中三个，其他保留注册定义。

### 20.2 原子工具

1. `inspect_workbook`
2. `read_range`
3. `write_range`
4. `set_formulas`
5. `format_range`
6. `create_sheet`
7. `copy_sheet`
8. `create_table`
9. `create_chart`
10. `set_conditional_format`
11. `freeze_panes`
12. `set_column_widths`
13. `recalculate`
14. `render_ranges`
15. `strict_audit`

MVP 不要求把这 15 项都暴露成 Agent 可单独编排的远程工具。可先作为任务脚本内部的稳定库函数，只有具备清晰参数、独立权限边界和契约测试的操作才进入公开能力注册表。

## 21. 测试策略

### 21.1 单元测试

- 能力清单解析和版本兼容。
- 需求覆盖计算。
- 计划 DAG、类型和冲突检查。
- 路径、权限和动态代码策略。
- 各原子工具和验收器。

### 21.2 集成测试

- 自然语言到结构化需求。
- 模板、工具组合和动态补丁三条路径。
- 工作副本与另存为策略。
- 失败、返修和用户确认流程。
- 引擎切换和高级对象保护。

### 21.3 评测测试

评测必须区分：

- 命中固定模板。
- 模板加工具扩展。
- 纯原子工具组合。
- 局部动态脚本。
- 完整开放式动态任务。

不能把模板命中结果用于证明开放式生成能力。评分应检查具体公式、业务指标、布局和文件保真，而不只是统计公式或图表是否存在。

## 22. MVP 验收标准

MVP 完成至少需要满足：

- 三类演示任务均能通过自然语言触发。
- 系统能解释为什么选择模板、工具组合或动态脚本。
- 能识别至少一种能力缺口并生成局部动态补丁。
- 所有任务均不覆盖输入文件。
- 高风险计划能够暂停并等待用户确认。
- 用户可以看到阶段性进度和返修过程。
- 输出包含结果 XLSX、预览、执行日志和审计报告。
- 严格验收能够主动拦截一个公式错误和一个视觉错误。
- 含已知高级对象的测试文件不会被静默损坏。

## 23. 关键风险

| 风险 | 应对措施 |
|---|---|
| 能力清单与真实实现不一致 | 契约测试、版本绑定和执行后验收 |
| Planner 错误理解业务需求 | 结构化需求展示、歧义确认和逐项验收 |
| 多工具修改冲突 | 范围级读写集合和计划冲突检测 |
| 动态脚本越权 | 受控 SDK、沙箱、白名单和任务目录隔离 |
| openpyxl 损坏高级对象 | 预检、兼容矩阵、阻止保存或切换 COM |
| 公式写入但未计算 | 引擎重算或明确标记未完全验证 |
| 模板结果掩盖泛化不足 | 按执行路径分类评测和公开模板命中信息 |
| 自动返修陷入循环 | 返修次数、错误指纹和策略升级限制 |

## 24. 后续待定设计

在实现前还需完成以下决策：

1. MVP 主引擎是否选择 openpyxl。
2. 公式重算和渲染使用 Excel、LibreOffice 还是其他服务。
3. 动态脚本采用进程隔离、容器还是受控 SDK 解释执行。
4. 首批三个模板的准确业务范围和输入字段规范。
5. 高风险单元格数量、公式修改比例等确认阈值。
6. COM 引擎是否进入 MVP，还是第二阶段接入。
7. Univer 是进入 MVP 主路径，还是仅作为第二引擎验证 Pipeline 抽象。
8. 首期采用 XLSX-first 还是同时承诺 `.unv` 工作态交付。
