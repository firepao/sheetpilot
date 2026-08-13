# Field Binding 与请求修订协议原型 V1

## 1. 决策目标

Field Binding 负责把 Task Request 中的业务字段引用绑定到输入工作簿的具体来源表、表头行和列。它必须满足：

- Agent 不读取源码或内部 Schema。
- Agent 不自行提交列字母、header row 或任意文件路径。
- Runtime 不依据模糊相似度静默选择列。
- 修正绑定不改变 Acceptance Contract。
- 并发或过期修订不能覆盖新状态。
- Agent 不创建、清空或复用运行目录。

## 2. 对象模型

```text
Task
├── Initial Task Request
├── Acceptance Snapshot (immutable)
├── Workbook Profile (input hash bound)
├── Binding Slots
├── Binding Candidates
└── Request Revisions
    ├── revision 1: initial request + automatic bindings
    ├── revision 2: Agent binding amendments
    └── revision N: later authorized binding correction
```

Task Request 中只保存业务字段名称。Runtime 在创建 Task 后生成 Binding Slot；Agent 只选择 Runtime 给出的 Candidate ID。

## 3. Binding Slot

Runtime 按字段第一次出现的顺序生成 Task 内稳定的 opaque ID：

```json
{
  "id": "binding-001",
  "logical_field": "清洗状态",
  "references": [
    "/filters/0/field"
  ],
  "requirements": {
    "accepted_types": ["text", "boolean", "unknown"],
    "uses": ["filter:eq"]
  },
  "status": "UNRESOLVED",
  "selected_candidate_id": null,
  "resolution": null
}
```

同一个 Task Request 中完全相同的业务字段名称共享一个 Binding Slot。例如 `sum(销售额)` 和 `average(销售额)` 使用同一个 Binding。

不同业务字段名称即使可能指向同一物理列，也保留独立 Slot。Agent 可以分别选择同一 Candidate，但 Runtime 必须在 Evidence 中记录该复用事实。

Slot ID 只在 Task 内稳定，不是跨任务领域 ID。Agent 不根据 ID 猜测字段含义。

## 4. Source Binding

来源表和表头范围先于字段绑定确定：

```json
{
  "id": "source-001",
  "sheet": "清洗明细",
  "header_row_start": 1,
  "header_row_end": 1,
  "confidence": 1.0,
  "evidence": ["request_sheet_exact_match", "header_candidate_detected"]
}
```

自动选择 Source 只允许以下情况：

1. Task Request 明确提供 `source.sheet`，且工作簿中只有一个同名可见 Sheet。
2. `header_row` 已明确，或者该 Sheet 只有一个可用 Header Candidate。

若 Task Request 没有 Sheet，或者存在多个 Header Candidate，Runtime 返回 `NEEDS_BINDING` 并要求 Agent 先选择 Source Candidate。字段 Candidate 必须属于最终选定的 Source。

第一阶段一个 `summarize_table` Task 只能读取一个 Source。

## 5. Binding Candidate

```json
{
  "id": "candidate-8f1472c1",
  "source_id": "source-001",
  "sheet": "清洗明细",
  "header_row_start": 1,
  "header_row_end": 1,
  "column": "G",
  "header": "销售额",
  "inferred_type": "number",
  "null_ratio": 0.02,
  "sample_values": [128.5, 300, 99.9],
  "confidence": 1.0,
  "evidence": ["exact_header_match", "type_compatible"]
}
```

Candidate ID 由以下事实确定性生成并截断显示：

```text
SHA-256(input_sha256, sheet, header_row_start, header_row_end, column, header)
```

Candidate ID 与固定输入文件身份绑定。输入 hash 改变后，全部 Candidate 失效，原 Task 不能继续执行。

候选事实约束：

- `confidence` 只用于排序和解释，不授权自动绑定。
- `sample_values` 最多 3 个非空值，字符串最多 64 个字符。
- 不返回公式源码、环境变量、外部链接内容或隐藏 Sheet 的样本。
- Candidate 列表按 exact match、type compatibility、confidence、Sheet/列顺序稳定排序。
- Candidate 必须来自 Workbook Profile，Agent 不能提交自定义 Sheet/列组合。

## 6. 自动绑定边界

Runtime 只有在以下条件全部满足时自动绑定字段：

1. Source 已唯一确定。
2. Source Header 中存在唯一的精确表头匹配。
3. Candidate 类型符合该 Slot 的全部用途。
4. 同一 Header Candidate 中没有重复同名表头。

以下情况必须返回 `NEEDS_BINDING`：

- 只有语义相似匹配，即使 confidence 很高。
- 存在多个精确匹配或多个 Source。
- 唯一精确匹配的类型与指标用途冲突。
- Header Candidate 不唯一。
- 找不到候选列。

“没有候选”使用 `HUMAN_ACTION_REQUIRED`，不允许 Agent 通过手写列字母绕过 Inspector。

## 7. NEEDS_BINDING 响应

```json
{
  "schema_version": "1.0",
  "status": "NEEDS_BINDING",
  "task_id": "task-01K0...",
  "request_revision": 1,
  "attempt_id": null,
  "acceptance_hash": "...",
  "binding_slots": [
    {
      "id": "binding-003",
      "logical_field": "销售额",
      "references": [
        "/metrics/0/field",
        "/metrics/2/field"
      ],
      "requirements": {
        "accepted_types": ["number"],
        "uses": ["metric:sum", "metric:average"]
      },
      "status": "AMBIGUOUS",
      "selected_candidate_id": null,
      "candidate_ids": [
        "candidate-8f1472c1",
        "candidate-a07f0614"
      ]
    }
  ],
  "binding_candidates": [],
  "diagnostics": [],
  "recovery": {
    "action": "PROVIDE_BINDING",
    "retryable": true,
    "base_revision": 1,
    "allowed_amendments": [
      {
        "op": "add",
        "path": "/bindings/binding-003",
        "constraints": {
          "candidate_ids": [
            "candidate-8f1472c1",
            "candidate-a07f0614"
          ]
        }
      }
    ],
    "suggested_patch": []
  }
}
```

Runtime 不确定正确列时，`suggested_patch` 必须为空。Agent 根据用户语义、header、类型和有限样本选择 Candidate。

## 8. Task Amendment

后续 `task-run` 调用提交修订 envelope，而不是重新提交完整 Task Request：

```json
{
  "schema_version": "1.0",
  "task_id": "task-01K0...",
  "base_revision": 1,
  "amendments": [
    {
      "op": "add",
      "path": "/bindings/binding-003",
      "value": {
        "candidate_id": "candidate-8f1472c1"
      }
    }
  ]
}
```

第一阶段 Task Amendment 规则：

- 只支持 Runtime 最近一次响应中列出的 `allowed_amendments`。
- Field Binding 只支持 `add` 和 `replace`，不支持 `remove`。
- 一次修订必须解决所有互不冲突的待绑定 Slot。
- 所有 amendment 原子应用；任一项失败时不创建新 revision。
- Agent 不提交 Acceptance、业务组件、输出或运行目录的修改。
- 原始 Task Request 永不覆盖；每次成功修订创建完整不可变 revision snapshot。

## 9. 修订处理流程

```text
接收 Task Amendment
→ 检查 task_id
→ 检查 base_revision == current_revision
→ 检查 acceptance_hash 未变化
→ 检查 amendment 完全属于 allowed_amendments
→ 检查 Candidate 属于当前 Task 和固定 input hash
→ 检查 Candidate 属于已选 Source
→ 检查 Candidate 类型满足 Slot 全部用途
→ 原子应用全部 amendment
→ 创建 revision N+1
→ 计算 request_revision_hash 与 binding_hash
→ 重新评估所有 Slot
→ NEEDS_BINDING 或 READY
```

进入 `READY` 前不创建 Attempt，也不修改工作簿。

## 10. Revision Conflict

当两个 Agent 或两个会话基于同一 revision 修订时，只接受第一个成功请求。后续请求返回：

```json
{
  "status": "REQUEST_INVALID",
  "task_id": "task-01K0...",
  "request_revision": 2,
  "attempt_id": null,
  "error": {
    "code": "REVISION_CONFLICT",
    "phase": "field_binding",
    "retryable": true,
    "diagnostics": [
      {
        "code": "REVISION_CONFLICT",
        "path": "/base_revision",
        "message": "修订基于过期版本。",
        "expected": {
          "kind": "integer",
          "value": 2
        },
        "actual": {
          "kind": "integer",
          "value": 1
        }
      }
    ],
    "recovery": {
      "action": "PROVIDE_BINDING",
      "retryable": true,
      "base_revision": 2,
      "allowed_amendments": [],
      "suggested_patch": []
    }
  }
}
```

Agent 必须重新读取 `task-status`，不能把旧 patch 直接改成新 revision 后重放。

`REVISION_CONFLICT` 应加入公开错误码集合。

## 11. Binding 修正时点

### 11.1 第一个 Attempt 之前

在 Task 仍为 `NEEDS_BINDING` 时，Runtime 可以允许 Agent `add` 或 `replace` 尚未执行的 Binding。

### 11.2 Attempt 创建之后

Agent 不能主动改 Binding。只有 Runtime Diagnostic 明确指出某个 Binding 无效，并在 Recovery Directive 中授权对应 `replace` 路径时，才能创建新 revision。

修正后：

- 保留旧 revision 和旧 Attempt Evidence。
- 创建新 request revision。
- `acceptance_hash` 保持不变。
- `binding_hash` 和 `request_revision_hash` 改变。
- 新执行使用新的 Attempt ID 和独立目录。

## 12. Binding Hash

```json
{
  "source": {
    "sheet": "清洗明细",
    "header_row_start": 1,
    "header_row_end": 1
  },
  "bindings": {
    "binding-001": "candidate-...",
    "binding-002": "candidate-...",
    "binding-003": "candidate-8f1472c1"
  }
}
```

```text
binding_hash = SHA-256(JCS(binding_snapshot))
```

Binding Snapshot 不包含 confidence、候选排序或样本值，只包含最终执行事实。每个 Attempt Evidence 必须记录 `binding_hash` 和可审计 Binding Snapshot。

## 13. 类型兼容

Runtime 根据 Slot 的全部用途计算最小类型要求：

| 用途 | 类型要求 |
|---|---|
| dimension | 任意稳定可序列化值 |
| filter:eq/ne/in | 任意与比较值兼容的类型 |
| filter:gt/gte/lt/lte | number 或 date |
| metric:sum/average | number |
| metric:count.rows | 不产生字段 Slot |
| metric:count.non_empty | 任意稳定可序列化值 |

若同一业务字段被用于多个组件，Candidate 必须满足所有用途。类型不兼容不能依赖执行阶段“试试看”。

## 14. 输入变化

Task 固定 `input_sha256`。任意阶段发现输入 hash 变化：

- Task 进入失败状态。
- 全部 Source、Candidate 和 Binding 失效。
- 返回 `INPUT_CHANGED` 与 `CREATE_NEW_TASK`。
- 不允许重新 inspect 后继续复用原 Acceptance Snapshot。

这避免同一个 Task 身份指向两个不同输入事实。

## 15. Skill 行为

Skill 只需要：

1. 首次提交业务级 Task Request。
2. 收到 `NEEDS_BINDING` 后比较 Slot、Candidate 和证据。
3. 仅选择 Candidate ID，并提交 Runtime 给出的 amendment 路径。
4. 遇到 `REVISION_CONFLICT` 时重新查询状态，不盲目重放旧 patch。
5. 不创建运行目录，不读取源码，不手写物理列映射，不改变 Acceptance。

字段发现、候选生成、修订并发和 Binding hash 均由 Runtime 保证，不能只写在 Skill 中。
