# SheetPilot 混合规划 MVP 实施状态 V1

## 1. 实施判断

现有 `src/sheetpilot` 已具备可复用的 Inspector、WorkbookContext、Workspace、Executor、ChangeRecorder 和 Validator。它们是真实可执行代码，不是只有接口的占位骨架，因此采用原目录增量演进，不在 `MVP/` 下复制一套新实现。

新建平行代码树会造成两套模型、两份注册表和两条 CLI 链路，反而违背唯一事实来源原则。

## 2. 已完成范围

### 阶段 A：统一计划模型

- `ExecutionStep.kind` 支持 `CAPABILITY`、`COMPOSITE`、`RECIPE`、`TRANSFORM`、`TASK`；
- `ExecutionPlan` 增加策略、Requirement、覆盖结果和规划依据；
- 保留 `HighLevelPlan` 作为旧 Skill 输入兼容层；
- ExecutionPlan Schema 同时接受 `1.0` 和 `1.1`。

### 阶段 B：中粒度 Composite

Composite 与 Capability 共用唯一可执行注册表，已实现：

```text
build_traceable_detail
classify_invalid_rows
calculate_profitability
summarize_by_period
summarize_by_dimension
build_kpi_block
build_reconciliation_sheet
```

脏订单仍是组合能力的评测场景，不存在 `dirty_orders_report` Recipe。

### 阶段 C：Hybrid Planner

- Recipe 通过 `RecipeRegistry` 枚举和匹配，不在 Router 中写死；
- Planner 根据注册表中的 `covers` 声明匹配 Requirement；
- 输出选择策略、组件、逐项覆盖状态和理由；
- 核心要求未覆盖时不会谎报可执行，而是进入 Dynamic Transform 候选。

### 阶段 D：Dynamic Transform

- 输入输出限制为可 JSON 化的 `TableData`；
- AST 检查函数签名、导入白名单、危险调用、dunder、顶层副作用、装饰器和规模；
- 使用独立 Python 子进程执行；
- `TRANSFORM` 类型的 ExecutionStep 已接入统一 Dispatcher；
- 设置超时、输入输出行列预算；
- 保存 Manifest、脚本、静态分析、标准输出、错误输出和结果证据。

## 3. 暂未纳入本轮

- Dynamic Task 和 WorkbookContext 写入授权，属于设计阶段 E；
- 真正 Excel/LibreOffice Renderer 和 PNG 视觉验证；
- Planner 自动把自然语言 TaskSpec 完整编译成包含所有参数的 ExecutionPlan；
- Composite 的公式落盘模板和脏订单完整场景回归；
- 操作系统级低权限账户、容器或 Job Object 沙箱。

当前 Transform 的安全边界是应用级 AST、受限 builtins、独立进程和资源预算，不应描述为适合不可信多租户代码的强隔离沙箱。

## 4. 验证方式

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
sheetpilot capabilities --kind COMPOSITE
sheetpilot recipes
```

验收重点是旧端到端链路不回归、Compiler 与 Dispatcher 查询同一注册表、Composite handler 可真实执行、Planner 覆盖声明可验证，以及 Transform 对文件访问和顶层副作用进行阻断。
