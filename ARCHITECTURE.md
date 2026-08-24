# SheetPilot 架构与设计思路

## 核心定位

**SheetPilot 是面向 LLM Agent 的确定性 Excel 执行 Runtime**，采用"黑盒原则"——Agent 通过高级业务契约提交需求，不接触底层计划、不管理文件系统、不编写工作簿操作脚本。

---

## 一、架构分层

```
┌─────────────────────────────────────────────┐
│  Agent (通过 Skill 调用)                      │
└──────────────────┬──────────────────────────┘
                   │ 自然语言 → Task Request JSON
                   ▼
┌─────────────────────────────────────────────┐
│  Task API (业务契约层)                        │
│  · contract.py   - 契约定义与验证             │
│  · compiler.py   - Task Request → 执行计划    │
│  · runtime.py    - 状态机与生命周期管理        │
│  · inventory.py  - 字段清单与绑定候选探测      │
└──────────────────┬──────────────────────────┘
                   │ ExecutionPlan (内部表示)
                   ▼
┌─────────────────────────────────────────────┐
│  Execution Engine (Registry-driven)         │
│  · registry.py   - 操作注册表 (Filter/GroupBy/│
│                    Aggregate/Sort/Publish)   │
│  · atomic/       - 执行上下文与共享状态        │
└──────────────────┬──────────────────────────┘
                   │ 调用底层原语
                   ▼
┌─────────────────────────────────────────────┐
│  Workbook Foundation                        │
│  · engines/      - OpenPyxlEngine            │
│  · workbook/     - TableData 表格抽象         │
└─────────────────────────────────────────────┘
```

---

## 二、核心设计原则

### 1. 黑盒执行协议

Agent 只看到 3 个命令：

```bash
sheetpilot task-types [--input file.xlsx --sheet "明细" --header-row 1]
sheetpilot task-run --request request.json
sheetpilot task-status --task-id task-xxx
```

**Agent 不提交：**

- ❌ 执行计划（DAG/步骤序列）
- ❌ 运行目录路径
- ❌ 列字母（`A`、`D`、`G`）
- ❌ openpyxl 代码
- ❌ 临时文件名

### 2. 确定性与幂等性

- 相同 `(submission_hash, input_sha256, output_file)` → 复用已有 Task
- 字段绑定失败 → 返回 `NEEDS_BINDING`，Agent 用 `task_id` + 补充绑定再提交
- 执行失败 → 明确 `retryable: true/false`，禁止 Agent 自由猜测

### 3. 安全边界

- 输入文件只读，不覆盖原文件
- 输出文件已存在 → 拒绝执行，要求人工介入
- Runtime 验证（数学正确性）与 Agent 验收（业务语义）分离报告

---

## 三、Task Request 契约示例

Agent 提交的 JSON（`MINIMAL_EXAMPLE`）：

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input_file": "D:/data/orders.xlsx",
  "output_file": "D:/result/city-summary.xlsx",
  "user_request": "仅统计有效且未退货订单，按城市汇总销售收入...",
  
  "source": {"sheet": "清洗明细", "header_row": 1},
  
  "filters": [
    {"id": "valid_rows", "field": "清洗状态", "operator": "eq", "value": "有效"},
    {"id": "not_returned", "field": "是否退货", "operator": "eq", "value": "否"}
  ],
  
  "dimensions": [
    {"id": "city", "field": "城市", "output_name": "城市"}
  ],
  
  "metrics": [
    {"id": "sales_revenue", "function": "sum", "field": "销售额", "output_name": "销售收入"},
    {"id": "order_count", "function": "count", "mode": "rows", "output_name": "订单数量"},
    {"id": "customer_count", "function": "count", "mode": "non_empty", "field": "客户编号", "output_name": "客户数"},
    {"id": "avg_amount", "function": "average", "field": "销售额", "output_name": "平均订单金额"}
  ],
  
  "output": {
    "sheet": "城市经营汇总",
    "anchor": "A1",
    "sort": [{"by": "sales_revenue", "direction": "desc"}]
  },
  
  "acceptance": {
    "required_filters": ["valid_rows", "not_returned"],
    "required_dimensions": ["city"],
    "required_metrics": ["sales_revenue", "order_count", "customer_count", "avg_amount"],
    "required_sort": [{"by": "sales_revenue", "direction": "desc"}]
  }
}
```

**关键特性：**

- 使用**稳定 ID**（`valid_rows`、`city`、`sales_revenue`）引用组件
- 使用**业务字段名**（`"清洗状态"`、`"销售额"`）而非列字母
- `acceptance` 独立声明业务验收要求
- `user_request` 仅用于审计，不参与 Runtime 推断

---

## 四、字段绑定机制（Inventory）

### 问题

Agent 提交 `"field": "销售额"`，但实际工作簿表头可能是：

- `"销售金额"` ❌
- `"销售额(元)"` ❌
- `"销售额"` ✅

### 解决方案（`inventory.py`）

1. **掩码探测**：对 `--input` 中所有可见 Sheet（或 `--sheet` 指定的），尝试 `--header-row`（默认 1）或前 10 行作为候选表头
2. **上限保护**：最多返回 200 个字段 × 5 个候选位置
3. **闭合返回**：

```json
{
  "available_fields": ["城市", "订单号", "销售额", "是否退货", "清洗状态", "客户编号"],
  "field_candidates": {
    "清洗明细": [{"sheet": "清洗明细", "header_row": 1, "fields": [...]}]
  },
  "error_code": null,
  "truncated": false
}
```

4. **绑定失败时**：返回 `NEEDS_BINDING` + `binding_slots`，Agent 看到候选后补充 `task_id` + `resolved_bindings` 再提交（`_amend`）

---

## 五、Registry-Driven 执行引擎

**核心改进**（2026年8月优化完成）：

```python
# 旧代码（if/elif 硬编码）
if step["type"] == "filter":
    result = _filter_impl(...)
elif step["type"] == "group_by":
    result = _group_by_impl(...)
elif step["type"] == "sort":
    result = _sort_impl(...)

# 新代码（注册表驱动）
handler = DEFAULT_REGISTRY.get_handler(step["type"])
result = handler(ctx, step["params"])
```

**注册表结构**（`capabilities/registry.py`）：

```python
DEFAULT_REGISTRY.register("filter", filter_handler)
DEFAULT_REGISTRY.register("group_by", group_by_handler)
DEFAULT_REGISTRY.register("aggregate", aggregate_handler)
DEFAULT_REGISTRY.register("sort", sort_handler)
DEFAULT_REGISTRY.register("publish", publish_handler)
```

**执行上下文**（`atomic/context.py`）：

```python
@dataclass
class ExecutionContext:
    task_id: str
    input_file: Path
    output_file: Path
    state: dict[str, Any]          # 运行时状态（中间表格、校验和）
    bindings: dict[str, str]       # 字段 → 物理列映射
    attempt_dir: Path              # 沙盒目录
```

---

## 六、状态机与生命周期

```
[CREATE] → [NEEDS_BINDING] ─resolve→ [EXECUTING]
             ↓ (all resolved)            ↓
             └────────────────────→ [RUNTIME_PASS]
                                         ↓
                                    sha256匹配 → [DELIVERED]
                                         ↓
                                    文件被篡改 → [MODIFIED]
```

**持久化结构**（`~/.local/state/SheetPilot/tasks/task-xxx/`）：

```
task.json                    # 任务元数据、acceptance_hash
acceptance-snapshot.json     # 独立验收快照
revisions/
  revision-001.json          # 第1版 request + bindings
  revision-002.json          # 修订后的请求
attempts/
  attempt-001/               # 第1次执行沙盒
    execution-plan.json
    published.xlsx
    validation.json
current-state.json           # 当前状态（RUNTIME_PASS/FAILED/NEEDS_BINDING）
```

---

## 七、Skill 与 Agent 集成

### Skill 位置

`skills/sheetpilot-excel-agent/SKILL.md`（主要 Skill，18KB）

### Skill 作用

1. **环境准备**：提示 `pip install openpyxl`
2. **查询字段**：`sheetpilot task-types --input orders.xlsx` → 返回 `available_fields`
3. **构造 Request**：提供 `count.rows` vs `count.non_empty` 的完整示例
4. **提交任务**：`sheetpilot task-run --request req.json`
5. **复核状态**：`sheetpilot task-status --task-id xxx`

### Agent 工作流（预期 6-8 步）

```
1. 理解需求 → 2. task-types 查字段 → 3. 构造 JSON → 4. task-run 提交
   ↓ (如果 NEEDS_BINDING)
5. 补充绑定 → 6. 再次提交 → 7. task-status 确认 RUNTIME_PASS
   ↓
8. 检查输出文件 SHA256 → 交付
```

---

## 八、项目目录结构

```text
src/sheetpilot/
  agent_cli.py          Agent 唯一 CLI 入口
  task_api/             Task Contract、Compiler、Runtime、Inventory
  capabilities/         Registry-driven 执行引擎
  atomic/               ExecutionContext 与共享状态
  engines/              OpenPyxlEngine 底层引擎
  workbook/             TableData 表格抽象
  planning/, recipes/,
  mvp.py, cli.py        旧 Runtime 兼容实现（已废弃）

skills/                 Agent Skill 目录
  sheetpilot-excel-agent/      主要执行 Skill
  sheetpilot-run-review/       执行记录评审
  sheetpilot-run-scorer/       执行记录打分

tests/
  unit/                 单元测试
  integration/          集成测试
  agent_contract/       黑盒用例与 Oracle
  fixtures/             测试固定输入

docs/
  current/              当前架构文档
  archive/              历史设计文档

archive/                旧 Schema、实验、重复文件
```

---

## 九、历史与未来

### 已废弃（archive/）

- 旧 Planner/MVP CLI（`cli.py`、`planning/`）
- 动态脚本生成（`recipes/`）
- Univer 引擎集成实验

### 当前 MVP（V3）

- 单引擎 openpyxl
- 业务级契约（`summarize_table`）
- 确定性编译与 Registry 执行
- 字段绑定与幂等性保证

### 目标态（docs/current/README.md）

- 混合引擎（openpyxl + Windows COM + Univer）
- Atom/Molecule/Composite 三级能力
- 受控动态脚本（仅补能力缺口）
- MCP Server 接入（当前是本地 CLI）

---

## 核心思想

**"Agent 描述业务需求，Runtime 保证数学正确，两者通过稳定契约连接，互不侵入彼此领域。"**

- Agent 不懂 openpyxl → 不需要懂
- Runtime 不猜业务语义 → 只验证计算一致性
- 中间状态全持久化 → 失败可追溯、可复现
- 契约稳定优先 → 内部实现可替换引擎

这是一个**混合执行系统**：固定能力为主体，动态生成为兜底，验收与审计为闭环。

---

## 关键技术决策

### 为什么是黑盒协议？

传统做法是让 LLM 生成 Python 脚本操作 openpyxl，问题：
- LLM 容易写出不安全的文件操作
- 列字母引用（`ws['D5']`）脆弱，表头变化就失效
- 每次都要重新生成和验证脚本
- 无法保证幂等性和可复现性

SheetPilot 的做法：
- Agent 只需理解业务概念（过滤、分组、求和）
- Runtime 负责安全的文件操作和列映射
- 相同输入 + 相同请求 = 相同结果（确定性）
- 失败时提供结构化错误和修复建议

### 为什么需要字段绑定？

Excel 表头千变万化：
- `"销售额"` vs `"销售额(元)"` vs `"销售金额"`
- 表头可能在第2行、第3行
- 多个 Sheet 可能有同名字段

Inventory 机制：
- 探测所有可能的表头位置
- 提供候选列表让 Agent 选择
- 绑定后固定映射，不会漂移

### 为什么用 Registry 而不是 if/elif？

旧代码问题：
```python
if step_type == "filter":
    ...  # 50行
elif step_type == "group_by":
    ...  # 80行
elif step_type == "aggregate":
    ...  # 100行
# runtime.py 变成 500+ 行的巨型函数
```

Registry 优势：
- 每个操作独立为一个 handler 函数
- 新增操作只需 `registry.register("new_op", handler)`
- 易于测试每个操作
- 为未来动态能力扩展做准备

---

## 相关文档

- [README.md](./README.md) - 项目概览与快速开始
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - 详细目录结构
- [docs/current/README.md](./docs/current/README.md) - 完整设计文档导航
- [docs/current/13-summarize-table-task-request-contract-prototype-v1.md](./docs/current/13-summarize-table-task-request-contract-prototype-v1.md) - Task Request 契约详细规范
- [skills/sheetpilot-excel-agent/SKILL.md](./skills/sheetpilot-excel-agent/SKILL.md) - Agent 使用指南
