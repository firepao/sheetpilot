# 机器可恢复错误协议原型 V1

## 1. 决策目标

本协议让 Agent 在不读取 SheetPilot 源码、内部 Schema 或实现文档的情况下回答四个问题：

1. 失败发生在哪个阶段。
2. 哪个请求字段或外部事实不符合契约。
3. 当前 Task 是否允许恢复。
4. Agent 被允许提交什么修改。

错误响应必须同时适合程序处理和人类排障。自然语言 `message` 只用于解释，恢复逻辑只能依赖稳定字段。

## 2. 统一错误 Envelope

```json
{
  "schema_version": "1.0",
  "status": "REQUEST_INVALID",
  "task_id": null,
  "request_revision": null,
  "attempt_id": null,
  "error": {
    "code": "INVALID_ENUM",
    "phase": "contract_validation",
    "message": "metrics[1].mode 不在允许枚举中。",
    "retryable": true,
    "diagnostics": [],
    "recovery": {}
  }
}
```

顶层 ID 只在对象已经存在时返回。请求尚未被 Runtime 接收时，`task_id`、`request_revision` 和 `attempt_id` 均为 `null`；不能伪造占位 ID。

## 3. Status 与 Code

`status` 表示调用结果类别，`error.code` 表示具体失败原因。

第一阶段错误 status：

| status | 含义 |
|---|---|
| `REQUEST_INVALID` | Task Request 未通过公开契约校验，未创建 Task |
| `CAPABILITY_UNSUPPORTED` | 请求合法，但当前 Task Type 无法表达或执行 |
| `EXECUTION_FAILED` | 已创建 Attempt，执行没有完成 |
| `VALIDATION_FAILED` | 执行完成，但 Runtime 验收失败，不发布 |
| `PUBLICATION_FAILED` | 验证通过，但最终文件未能原子发布 |
| `INTERNAL_ERROR` | 公开契约之外的 Runtime 缺陷或未知异常 |

`NEEDS_BINDING` 是 Task 状态，不是错误。它使用同一套 Diagnostic 和 Recovery 结构，但不放入 `error` 对象。

第一阶段稳定 error code：

```text
MISSING_REQUIRED_FIELD
UNKNOWN_FIELD
INVALID_TYPE
INVALID_ENUM
INVALID_VALUE
INVALID_COMBINATION
INVALID_REFERENCE
REVISION_CONFLICT
INPUT_NOT_FOUND
INPUT_CHANGED
OUTPUT_CONFLICT
CAPABILITY_UNSUPPORTED
EXECUTION_FAILED
VALIDATION_FAILED
PUBLICATION_FAILED
INTERNAL_ERROR
```

现有 `INPUT_INVALID`、`PLAN_INVALID` 等内部错误码可以继续存在于兼容层，但 Agent API 必须映射为上述公开错误码，不能直接泄露内部 Plan 概念。

## 4. Phase

`phase` 是稳定枚举，用于决定 Agent 应查看哪一层事实：

```text
contract_validation
workbook_inspection
field_binding
request_compilation
execution
validation
publication
internal
```

`phase` 不使用 Python 模块、函数名或 Atom 名称。

## 5. Diagnostic

```json
{
  "code": "INVALID_ENUM",
  "path": "/metrics/1/mode",
  "message": "count mode 必须是 rows 或 non_empty。",
  "expected": {
    "kind": "enum",
    "values": ["rows", "non_empty"]
  },
  "actual": {
    "kind": "string",
    "value": "row"
  }
}
```

规则：

- `path` 使用 RFC 6901 JSON Pointer，根节点使用空字符串。
- Diagnostic 按 `path`、`code` 稳定排序，保证相同输入产生相同输出。
- `expected` 和 `actual` 是结构化对象，不能只返回拼接文本。
- `actual.value` 只允许返回请求中本来就由 Agent 提交的非敏感值。
- 文件内容、单元格样本、环境变量、栈信息和内部路径不得进入 `actual.value`。
- 一次响应可以包含多个 Diagnostic；Agent 应一次修复全部互不冲突的问题。

## 6. Recovery

```json
{
  "action": "AMEND_REQUEST",
  "retryable": true,
  "base_revision": null,
  "allowed_amendments": [
    {
      "op": "replace",
      "path": "/metrics/1/mode",
      "constraints": {
        "enum": ["rows", "non_empty"]
      }
    }
  ],
  "suggested_patch": [
    {
      "op": "replace",
      "path": "/metrics/1/mode",
      "value": "rows"
    }
  ]
}
```

`action` 枚举：

| action | 含义 |
|---|---|
| `AMEND_REQUEST` | 按允许路径修改尚未创建 Task 的请求 |
| `PROVIDE_BINDING` | 为已有 Task 提交 Field Binding 修订 |
| `RETRY_ATTEMPT` | 请求内容不变，创建新的 Attempt |
| `CREATE_NEW_TASK` | 当前修复会改变冻结契约，必须创建新 Task |
| `HUMAN_ACTION_REQUIRED` | 需要用户处理文件、权限、路径或业务歧义 |
| `NONE` | Runtime 无法给出安全恢复动作 |

规则：

- `error.retryable` 与 `recovery.retryable` 必须一致，并由 `action` 自动推导，不能分别维护。
- `allowed_amendments` 使用 RFC 6902 的 `add`、`remove`、`replace`，第一阶段不支持 `move`、`copy`、`test`。
- `suggested_patch` 必须是 `allowed_amendments` 的合法子集；Runtime 不确定正确值时必须省略建议，不能猜测。
- 对已有 Task 的修订必须携带 `base_revision`。
- Acceptance Contract 路径不出现在 `allowed_amendments` 中。需要改变 Acceptance 时返回 `CREATE_NEW_TASK`。
- Agent 只能提交 Runtime 返回的允许路径。额外修改使整次修订失败，不部分应用。
- `REVISION_CONFLICT` 要求 Agent 重新读取最新 Task 状态；不能仅替换 `base_revision` 后重放旧 patch。

## 7. 非错误 NEEDS_BINDING

```json
{
  "schema_version": "1.0",
  "status": "NEEDS_BINDING",
  "task_id": "task-01K0...",
  "request_revision": 1,
  "attempt_id": null,
  "diagnostics": [
    {
      "code": "FIELD_BINDING_AMBIGUOUS",
      "path": "/metrics/0/field",
      "message": "业务字段“销售额”存在多个候选列。",
      "expected": {
        "kind": "single_binding"
      },
      "actual": {
        "kind": "candidates",
        "count": 2
      }
    }
  ],
  "recovery": {
    "action": "PROVIDE_BINDING",
    "retryable": true,
    "base_revision": 1,
    "allowed_amendments": [
      {
        "op": "add",
        "path": "/bindings/sales_amount",
        "constraints": {
          "candidate_ids": ["candidate-1", "candidate-2"]
        }
      }
    ],
    "suggested_patch": []
  },
  "field_inventory": [
    {
      "id": "candidate-1",
      "sheet": "清洗明细",
      "header": "销售额",
      "column": "G",
      "header_row": 1,
      "sample_values": [128.5, 300]
    },
    {
      "id": "candidate-2",
      "sheet": "原始明细",
      "header": "销售金额",
      "column": "H",
      "header_row": 1,
      "sample_values": [145.21, 339]
    }
  ]
}
```

Candidate ID 是 Runtime 生成的短期引用。Agent 选择 Candidate ID，不重写 Sheet、列字母和 header_row；Runtime 不生成语义候选，字段语义由 Agent 对照 field_inventory 判断。

## 8. 典型错误示例

### 8.1 非法 count mode

```json
{
  "schema_version": "1.0",
  "status": "REQUEST_INVALID",
  "task_id": null,
  "request_revision": null,
  "attempt_id": null,
  "error": {
    "code": "INVALID_ENUM",
    "phase": "contract_validation",
    "message": "Task Request 包含 1 个契约错误。",
    "retryable": true,
    "diagnostics": [
      {
        "code": "INVALID_ENUM",
        "path": "/metrics/1/mode",
        "message": "count mode 必须是 rows 或 non_empty。",
        "expected": {
          "kind": "enum",
          "values": ["rows", "non_empty"]
        },
        "actual": {
          "kind": "string",
          "value": "row"
        }
      }
    ],
    "recovery": {
      "action": "AMEND_REQUEST",
      "retryable": true,
      "base_revision": null,
      "allowed_amendments": [
        {
          "op": "replace",
          "path": "/metrics/1/mode",
          "constraints": {
            "enum": ["rows", "non_empty"]
          }
        }
      ],
      "suggested_patch": [
        {
          "op": "replace",
          "path": "/metrics/1/mode",
          "value": "rows"
        }
      ]
    }
  }
}
```

### 8.2 已有输出 Sheet

Runtime 不猜测覆盖、重命名或复用策略：

```json
{
  "status": "EXECUTION_FAILED",
  "error": {
    "code": "OUTPUT_CONFLICT",
    "phase": "execution",
    "retryable": false,
    "diagnostics": [
      {
        "code": "OUTPUT_CONFLICT",
        "path": "/output/sheet",
        "message": "目标工作表已存在。",
        "expected": {
          "kind": "new_sheet_name"
        },
        "actual": {
          "kind": "string",
          "value": "城市经营汇总"
        }
      }
    ],
    "recovery": {
      "action": "CREATE_NEW_TASK",
      "retryable": false,
      "base_revision": 1,
      "allowed_amendments": [],
      "suggested_patch": []
    }
  }
}
```

输出 Sheet 属于 Task Request 和 Acceptance Contract 的交付语义，不能在原 Task 中静默改名。

### 8.3 验收失败

```json
{
  "status": "VALIDATION_FAILED",
  "task_id": "task-01K0...",
  "request_revision": 1,
  "attempt_id": "attempt-002",
  "error": {
    "code": "VALIDATION_FAILED",
    "phase": "validation",
    "message": "Runtime 验收未通过，结果未发布。",
    "retryable": true,
    "diagnostics": [
      {
        "code": "AGGREGATE_MISMATCH",
        "path": "/acceptance/required_metrics/0",
        "message": "sales_revenue 的聚合结果与来源复算不一致。",
        "expected": {
          "kind": "number",
          "value": 1200
        },
        "actual": {
          "kind": "number",
          "value": 1190
        }
      }
    ],
    "recovery": {
      "action": "RETRY_ATTEMPT",
      "retryable": true,
      "base_revision": 1,
      "allowed_amendments": [],
      "suggested_patch": []
    }
  }
}
```

验收失败不能通过删除 `required_metrics` 恢复。若相同输入和请求重复失败，Runtime 应升级为 `NONE` 或 `HUMAN_ACTION_REQUIRED`，具体重试预算由 Task 状态机 Ticket 定义。

## 9. CLI 行为

- 所有 Agent API 响应只向 stdout 输出一个 UTF-8 JSON 对象。
- 日志写入 stderr，不能混入 JSON。
- 同一 error code 使用稳定进程退出码；Agent 的主要判断依据仍是 JSON，不依赖文本。
- 未处理异常统一映射为 `INTERNAL_ERROR`，不向 Agent 输出 Python traceback。
- Runtime Evidence 保存完整错误 envelope；Skill 最终报告只能引用其中事实。

## 10. Skill 约束

Skill 不复制错误码、字段枚举或修复规则，只执行以下流程：

1. 读取结构化响应。
2. 当 `recovery.action` 允许时，仅应用 `allowed_amendments` 范围内的修订。
3. 当 action 为 `CREATE_NEW_TASK` 或 `HUMAN_ACTION_REQUIRED` 时停止自动恢复。
4. 不读取源码解释错误，不清空 Attempt 目录，不删除 Acceptance 条件。

错误协议由 Runtime 保证，Skill 只负责遵循。

## 11. 请求前字段清单查询

`task-types --input [--sheet] [--header-row]` 是纯只读查询，不创建 Task、没有 task_id 或 base_revision。查询错误仍使用本协议 envelope：`INPUT_NOT_FOUND` 停止并报告；不可见 Sheet 通过 `/query/sheet` 的可见 Sheet 枚举修正；非法 header row 通过 `/query/header_row` 的 `min=1` 修正；`INVENTORY_TOO_LARGE` 同时提供两条收窄查询路径。Agent 修改查询参数后重新调用 `task-types`，不涉及 Task 状态。
