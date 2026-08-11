# SheetPilot Agent Interface

SheetPilot Agent Interface 定义 Agent 表达 Excel 业务任务时使用的领域语言，以及 Runtime 对任务执行和验收承担的边界。

## Language

**Task Request**:
Agent 提交给 SheetPilot 的业务级任务声明，描述数据来源、业务操作、输出目标和验收要求，不包含 Atom DAG 或运行目录。
_Avoid_: Plan, Execution Plan, DAG

**Task Type**:
Task Request 所表达的通用业务操作类别，例如 `summarize_table`。Task Type 不暴露其内部使用的 Molecule 或 Atom。
_Avoid_: Recipe, Capability Name, Operation Graph

**Deterministic Task Compiler**:
Runtime 将已验证 Task Request、Acceptance Snapshot 和 Binding Snapshot 转换为稳定内部执行计划的组件。相同冻结输入和 Compiler 版本必须产生字节级相同的计划。
_Avoid_: Planner, Agent-generated Plan

**Internal Execution Plan**:
Deterministic Task Compiler 生成并由 Runtime 独占使用的低层执行表示。Agent 不提交、修改或依赖 Internal Execution Plan。
_Avoid_: Task Request, Public Plan

**Acceptance Contract**:
Task Request 中独立声明且在首次接收后冻结的验收范围。后续执行尝试可以修复执行参数，但不能静默缩减 Acceptance Contract。
_Avoid_: Validation Hints, Optional Checks

**Acceptance Snapshot**:
Runtime 将 Acceptance Contract 引用的业务组件展开为完整定义，并加入不可删除的系统验收后形成的 Task 级不可变快照。
_Avoid_: Requirement Copy, Validation Plan

**Business Acceptance**:
Acceptance Contract 中由 Agent 根据用户要求声明的业务结果条件。Runtime 验证其中明确的数学和结构事实，但不替 Agent 判断业务术语是否选择正确。
_Avoid_: Agent Validation, Semantic PASS

**System Acceptance**:
Runtime 自动加入 Acceptance Contract 且调用方不能删除的平台一致性条件，包括输入保护、证据完整和验证后发布一致性。
_Avoid_: Default Checks, Optional Safety Checks

**Task**:
Runtime 接收并固定 Task Request 后形成的稳定任务身份。同一个 Task 可以包含多个执行尝试。
_Avoid_: Run, Run Directory

**Attempt**:
Runtime 为同一个 Task 创建的一次不可变执行尝试。失败后的恢复产生新的 Attempt，已有 Attempt 保持只读。
_Avoid_: Reused Run, Cleared Run Directory

**Request Revision**:
同一个 Task 中对 Runtime 明确授权字段所做的一次不可变请求修订。Request Revision 不能改变 Acceptance Snapshot，并通过 base revision 防止过期修订覆盖新状态。
_Avoid_: Edited Request, Mutable Task

**Field Binding**:
Task Request 中业务字段与输入工作簿具体 Sheet、表头或列之间的显式对应关系。无法唯一确定的 Field Binding 必须由 Agent 补充，Runtime 不静默猜测。
_Avoid_: Column Guess, Semantic Mapping Script

**Binding Candidate**:
Runtime 根据固定输入文件画像生成的可选物理字段事实。Agent 通过 Task 内 Candidate ID 选择 Binding Candidate，不自行提交 Sheet、表头行或列坐标。
_Avoid_: Column Mapping, Agent-provided Coordinate

**Needs Binding**:
Task 已被接收但存在未解决或歧义 Field Binding 的状态。该状态提供候选事实，不执行工作簿修改。
_Avoid_: Planning Failure, Invalid Request

**Runtime Evidence**:
Runtime 针对某个 Attempt 生成的执行与验证事实。Agent 的最终说明只能引用 Runtime Evidence，不自行声明未被记录的执行能力或验证结论。
_Avoid_: Agent Summary, Self-reported Validation

**Runtime Pass**:
某个 Attempt 的全部 Business Acceptance、System Acceptance、证据完整性和验证后发布一致性均通过的 Runtime 结论。Runtime Pass 不包含 Agent 对业务口径是否正确的判断。
_Avoid_: PASS, Semantic Validation

**Artifact Integrity**:
当前交付文件与 Runtime Pass 时已验证发布文件之间的 hash 关系，取值为 matched、missing 或 modified。Runtime Pass 是历史结论，只有 Artifact Integrity 为 matched 时当前文件仍可交付。
_Avoid_: Output Exists, Previous PASS

**Diagnostic**:
Runtime 对请求字段或执行事实为何不符合公开契约的结构化描述，包含稳定原因、字段路径、期望和实际值。
_Avoid_: Error Details, Traceback

**Recovery Directive**:
Runtime 针对 Diagnostic 给出的机器可执行恢复边界，明确恢复动作、允许修改的路径和可选补丁。Recovery Directive 不能授权缩减 Acceptance Contract。
_Avoid_: Troubleshooting Hint, Agent Guess
