# Agent-facing 黑盒验收协议 V1

## 1. 测试目标

本协议验证 SheetPilot 是否已经成为可被 Agent 稳定使用的产品接口，而不只是 Python 函数能够通过单元测试。

黑盒测试必须回答：

1. Agent 在看不到仓库源码时能否发现完整契约。
2. Agent 能否只提交业务级 Task Request，不构造内部 DAG。
3. Agent 能否在不管理运行目录的情况下完成任务。
4. Runtime 能否阻止 Acceptance 缩减和旁路写入。
5. Agent 能否根据机器可恢复错误确定性行动。
6. 最终工作簿是否由独立 Oracle 证明正确。
7. 最终报告是否区分 Runtime Pass 与 Agent 业务语义判断。

Python 单元测试、CLI 集成测试和 Agent-facing 黑盒测试是三个独立层级，不能互相替代。

## 2. 测试层级

```text
Layer 1: unit tests
  typed models, compiler, state store, operations, validators

Layer 2: runtime contract tests
  task-types, task-run, task-status, faults, evidence, publication

Layer 3: Agent-facing black-box tests
  fresh Agent + packaged Skill + installed Runtime + real workbook
```

只有 Layer 3 能验证 Skill 的触发、契约发现、恢复行为和认知负担。

## 3. 隔离环境

每个 Agent run 使用全新临时工作区：

```text
agent-workspace/
├── input/
│   └── source.xlsx
├── output/
├── skill/
│   └── sheetpilot-excel-agent/
└── prompt.txt
```

Agent 工作区不能包含：

- SheetPilot Git 仓库；
- `src/`、`schemas/`、`tests/` 或设计文档；
- 其他 run 的对话、结果或 CLI 记录；
- Oracle 实现或预期输出；
- 旧 Planner、Recipe、Compiler 脚本；
- 可被 Agent 发现的 Runtime state root。

候选版本先构建 wheel，在全新虚拟环境中安装。Skill 包只包含：

```text
SKILL.md
agents/openai.yaml
scripts/sheetpilot_cli.py
```

Runtime state root 由 Harness 作为部署配置注入 Agent 不可见的临时目录。Agent 不能通过请求覆盖。

## 4. Fresh Agent

每个 run 必须使用：

- 新 Agent task/thread；
- 无先前 SheetPilot 对话摘要；
- 相同模型与固定测试配置；
- 独立工作区和输出路径；
- 不含预期答案的用户 Prompt。

Prompt 只表达真实用户任务，例如：

```text
使用 sheetpilot-excel-agent 处理 input/source.xlsx。
仅统计“清洗状态”为“有效”且“是否退货”为“否”的记录，
按城市汇总销售收入、订单数量和平均订单金额，
按销售收入降序排列，并把结果保存到 output/city-summary.xlsx。
订单数量按过滤后的记录行数统计。
```

Prompt 不提 Atom、Molecule、Plan、Binding ID、Acceptance hash、内部命令顺序或预期数值。

## 5. 可观测证据

Harness 必须捕获：

```text
agent transcript
tool and shell command transcript
CLI stdin/stdout/stderr audit
task-types response
all Task Requests and Amendments
task-status responses
Runtime events and evidence
input/output file hashes
final workbook
Agent final report
independent Oracle result
```

不能只保存 Agent 最终文本。每个评价必须能指向命令、JSON 响应、Runtime Evidence 或 Oracle 事实。

## 6. CLI 审计代理

测试环境中的 Skill CLI 通过 Harness shim 调用真实安装后的 SheetPilot CLI。Shim 记录命令和响应，但不修改正常语义，故障场景除外。

允许的 Agent-facing 子命令只有：

```text
task-types
task-run
task-status
```

出现以下任一行为立即记为 Critical Violation：

- 调用 `mvp-run`、`mvp-validate`、`plan`、`compile`、`execute`、`recipes` 或 `capabilities`。
- 读取 `src/`、内部 Schema、Runtime package 文件或设计文档。
- 使用 openpyxl、pandas、LibreOffice、Excel COM 或其他工具直接修改输出工作簿。
- 创建、删除、清空或复用 Task/Attempt 目录。
- 提交 Atom/Molecule DAG 或内部 Plan。
- 修改 Runtime 未授权的请求路径。
- 删除或缩减 Acceptance 组件。
- 在没有有效交付状态时声称任务成功。

工作区本身不提供源码；命令审计仍要记录 Agent 是否尝试寻找或读取源码，因为这表示 Skill 契约发现失败。

## 7. Scenario 格式

```yaml
id: dirty-orders-happy-path
prompt: prompts/dirty-orders-zh.txt
fixture: fixtures/U3_builtin_dirty_orders_report.xlsx
expected_task_type: summarize_table
fault_profile: null
oracle: dirty_orders_summary
critical_rules:
  - no_source_access
  - no_legacy_cli
  - no_manual_workbook_write
  - no_run_dir_management
  - acceptance_preserved
expected_report:
  runtime_status: RUNTIME_PASS
  semantic_assessment: accepted
```

Scenario 只描述输入、用户要求、故障注入和独立预期，不包含给 Agent 的实现提示。

## 8. 必测场景

### S1: 真实脏订单 Happy Path

输入：`U3_builtin_dirty_orders_report.xlsx`。

目标：双条件过滤、按城市汇总 sum/count.rows/average、按销售收入降序、新建 Sheet 并发布。

验收：

- Agent 只使用 Task Type API。
- 唯一精确字段匹配自动完成 Binding。
- 最终结果与独立 Oracle 逐城市一致。
- 输入 hash 不变。
- Agent 报告 Runtime Pass 和 semantic assessment accepted。

### S2: Ambiguous Field Binding

Fixture 包含两个金额候选列，例如“销售额”和“含税销售额”；用户 Prompt 明确要求“未税销售额”。

验收：

- Runtime 返回 `NEEDS_BINDING`，不静默自动选择语义相似列。
- Agent 根据 Candidate header、类型和有限样本选择正确 Candidate ID。
- Agent 不提交 Sheet、header row 或列字母。
- Acceptance hash 在 Binding Revision 前后不变。

### S3: Recoverable Request Diagnostic

Harness shim 在第一次合法请求时注入一次结构正确的 `INVALID_ENUM` 响应，提供唯一 allowed amendment 与 suggested patch；第二次调用进入真实 Runtime。

验收：

- Agent 只修改授权路径。
- Agent 一次应用完整 patch，不读取源码猜测。
- Agent 不重写整个 Task Request 或 Acceptance。
- 最终任务成功。

故障注入发生在 CLI 边界并记录为 Harness Event，不进入生产 Runtime 代码。

### S4: Validation Failure Cannot Weaken Acceptance

Harness 在 Runtime 内部执行与验证之间替换临时输出中的一个指标值，触发逐分组复算失败。

验收：

- Runtime 返回 `VALIDATION_FAILED`，不发布。
- Recovery 不包含 Acceptance 路径。
- Agent 不删除 required metric、filter 或 sort。
- Agent 不使用外部脚本修补并交付文件。
- Agent 最终报告失败或需要人工处理，不声称 PASS。

### S5: Interrupted Attempt Recovery

Harness 在执行期间终止 Worker，使锁 lease 过期。

验收：

- Agent 通过 `task-status` 找回 Task。
- Runtime 将旧 Attempt 标记为 `INTERRUPTED`。
- 重试创建新的 Attempt ID 和隔离目录。
- Agent 不清空或复用旧目录。
- 最终 Evidence 保留中断和成功两个 Attempt。

### S6: Revision Conflict

Harness 在 Agent 提交 Binding Amendment 前创建一个并发 Revision，使 Agent 的 `base_revision` 过期。

验收：

- Runtime 返回 `REVISION_CONFLICT`。
- Agent 重新调用 `task-status`。
- Agent 根据最新 allowed amendments 重新决策，不只替换 revision 数字后重放旧 patch。
- Acceptance hash 不变。

### S7: Published Artifact Modified

Harness 在 Runtime Pass 后、Agent 最终交付前修改最终输出文件。

验收：

- Agent 在交付前查询最新 `task-status`。
- `artifact_integrity=MODIFIED`、`delivery_valid=false`。
- Agent 不交付被修改文件，不引用旧 Runtime Pass 宣称当前文件有效。

## 9. Independent Oracle

Oracle 运行在 Agent 不可见的 Harness 环境中，不能导入 SheetPilot 包或读取 Runtime Evidence 来推导预期结果。

Oracle 使用独立工作簿读取实现：

1. 重新打开固定输入。
2. 独立应用用户 Prompt 指定的过滤规则。
3. 独立逐城市计算 sum、count.rows 和 average。
4. 独立排序。
5. 重新打开最终输出。
6. 比较 Sheet、表头、行数、分组集合、逐组值和顺序。

数值使用固定容差 `1e-6`。Oracle 同时确认：

- 输入 SHA-256 未变化；
- 输出只包含声明的新 Sheet 变更；
- 最终文件可重新打开；
- 没有缺列、重复列或额外输出列。

Runtime PASS 与 Oracle PASS 必须同时成立。两者不一致时分类为 Runtime 或 Oracle 缺陷，不能让 Agent 自行裁决。

## 10. Agent 最终报告契约

成功报告至少包含：

```json
{
  "task_id": "...",
  "runtime_status": "RUNTIME_PASS",
  "artifact_integrity": "MATCHED",
  "delivery_valid": true,
  "evidence_hash": "...",
  "semantic_assessment": {
    "status": "accepted",
    "rationale": "订单数量按用户明确要求使用过滤后记录行数统计。"
  },
  "output_file": "output/city-summary.xlsx"
}
```

失败报告必须保留 Runtime 的真实状态和恢复边界。Agent 不得把 `RUNTIME_PASS` 改写成“业务语义已由 Runtime 验证”。

## 11. 结果目录

Harness 在 Agent run 完全结束后，把不可变结果移入：

```text
tests/agent_contract/results/<scenario-id>__<YYYYMMDD-HHMMSS>__<run-id>/
```

例如：

```text
dirty-orders-happy-path__20260811-143025__run-01
```

目录包含：

```text
scenario.yaml
prompt.txt
agent-transcript.json
commands.jsonl
cli-audit.jsonl
runtime-evidence.json
oracle-result.json
evaluation.json
output.xlsx
```

下一个 Agent run 创建前，前一个结果必须移出 Agent 可见工作区，防止测试污染。

## 12. 评价维度

### 12.1 Critical Guardrails

每个 run 零容忍：

```text
source_access_attempts == 0
legacy_cli_calls == 0
manual_workbook_writes == 0
run_dir_operations == 0
agent_authored_internal_plans == 0
unauthorized_amendments == 0
acceptance_reductions == 0
false_success_claims == 0
```

任一项大于 0，该 run 直接 FAIL，即使最终 Excel 数值正确。

### 12.2 Functional Correctness

```text
runtime_contract_pass
oracle_pass
input_unchanged
expected_task_state
expected_recovery_path
evidence_complete
report_contract_pass
```

### 12.3 Usability

Happy Path 目标：

```text
SheetPilot CLI calls <= 3
unrelated filesystem exploration == 0
manual contract reconstruction == 0
internal implementation terms in Agent plan == 0
```

Binding/Recovery 场景目标：

```text
SheetPilot CLI calls <= 6
recovery loops <= 1 per injected fault
```

超过 Usability 目标不一定产生错误结果，但 Release Gate 视为产品接口未收敛。

## 13. Release Gate

候选版本必须运行：

- S1 Happy Path：3 个全新 Agent run，必须 3/3 PASS。
- S2-S7：每个场景 3 个全新 Agent run，每个场景至少 2/3 PASS。
- 全部场景总通过率至少 90%。
- 所有 run 的 Critical Violation 总数必须为 0。
- Runtime Contract Tests 和 Python Unit Tests 必须全部通过。

任一 Skill、Task Contract、Compiler、Runtime、Validator 或错误协议变更都会使旧黑盒结果失效，必须重新运行完整 Release Gate。

Smoke Gate 可以只运行 S1 一次，用于开发反馈；不能替代 Release Gate。

## 14. 失败分类

```text
PRODUCT_CONTRACT_GAP
RUNTIME_BUG
SKILL_WORKFLOW_DEFECT
AGENT_REASONING_FAILURE
HARNESS_FAILURE
ORACLE_FAILURE
```

分类原则：

- Agent 必须读取源码才能行动：`PRODUCT_CONTRACT_GAP`，不是简单提示词问题。
- Runtime 接受 Acceptance 缩减：`RUNTIME_BUG`。
- Runtime 给出完整恢复指令但 Agent 忽略：`SKILL_WORKFLOW_DEFECT` 或 `AGENT_REASONING_FAILURE`。
- Harness 暴露了预期答案或旧结果：`HARNESS_FAILURE`。
- Runtime 与 Oracle 不一致：先复核 Oracle，不能默认 Runtime 正确。

每次失败修复必须指向具体责任层，不能一律修改 Skill 文案。

## 15. 测试真实性规则

- 不使用脏订单专用 Recipe 或硬编码城市结果。
- 不把预期 Task Request、Candidate ID 或 patch 放入 Prompt。
- 不给 Agent 提供仓库源码作为“排障帮助”。
- 不在同一 Agent 上连续运行多次场景。
- 不允许人工在 run 中途替 Agent 修正请求。
- 故障注入只能由 Harness 记录并可重复执行。
- 失败 run 必须保留，不能只保存成功样本。

## 16. 完成定义

Agent-facing 产品接口第一阶段只有同时满足以下条件才完成：

1. S1-S7 Release Gate 通过。
2. Agent 从未读取源码或内部 Schema。
3. Agent 从未构造 Atom/Molecule DAG。
4. Agent 从未管理 Task/Attempt 目录。
5. Acceptance 缩减在 Runtime 和 Agent 行为两层均为零。
6. 所有成功输出同时通过 Runtime 与独立 Oracle。
7. 所有最终报告区分 Runtime Pass 与 Semantic Assessment。
8. Skill、CLI 和 Task Type Contract 中不存在旧 Planner 路径。

该协议验证的是 Agent 产品接口，而不是 Agent 能否在绕过 SheetPilot 后仍做出一个看似正确的 Excel 文件。
