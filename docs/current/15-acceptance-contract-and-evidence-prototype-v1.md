# Acceptance Contract 固化与证据模型原型 V1

## 1. 决策目标

Acceptance Contract 必须阻止以下失败方式：

- Agent 为了让执行通过而删除过滤条件、指标或排序要求。
- Validator 只确认某个 Atom 执行过，没有确认声明的数学结果正确。
- Agent 修改请求中的指标定义，但继续复用旧验收范围。
- 已验证文件被修改后仍引用旧 PASS。
- Runtime PASS 与 Agent 的业务语义判断混为一体。

第一阶段不让 Runtime 判断“订单数量应该按行数还是唯一订单号”等业务含义。Agent 选择数学定义；Runtime 冻结并独立验证该定义是否被正确执行。

## 2. 两层 Acceptance

```text
Acceptance Contract
├── Business Acceptance
└── System Acceptance
```

### 2.1 Business Acceptance

Agent 在 Task Request 中只引用必须交付的稳定组件 ID：

```json
{
  "required_filters": ["valid_rows", "not_returned"],
  "required_dimensions": ["city"],
  "required_metrics": [
    "sales_revenue",
    "order_count",
    "average_order_amount"
  ],
  "required_sort": [
    {
      "by": "sales_revenue",
      "direction": "desc"
    }
  ]
}
```

Agent 不提交 Validator 名称、Python 函数、检查 SQL 或可选 severity。第一阶段所有 Acceptance 项都是必需项。

### 2.2 System Acceptance

Runtime 自动加入以下不可删除检查：

```text
input_identity_preserved
request_contract_preserved
acceptance_contract_preserved
attempt_isolated
output_reopenable
validated_artifact_preserved
publication_matches_validation
evidence_complete
```

System Acceptance 不出现在 Agent 可修改的请求路径中。

## 3. Acceptance Snapshot

Runtime 接收合法 Task Request 后，把 Business Acceptance 中的组件 ID 展开为完整定义，并加入 System Acceptance，生成不可变快照：

```json
{
  "schema_version": "1.0",
  "task_type": "summarize_table",
  "input": {
    "path": "D:/data/orders.xlsx",
    "sha256": "..."
  },
  "output": {
    "path": "D:/result/city-summary.xlsx",
    "sheet": "城市经营汇总",
    "anchor": "A1"
  },
  "business": {
    "filters": [
      {
        "id": "valid_rows",
        "field": "清洗状态",
        "operator": "eq",
        "value": "有效"
      },
      {
        "id": "not_returned",
        "field": "是否退货",
        "operator": "eq",
        "value": "否"
      }
    ],
    "dimensions": [
      {
        "id": "city",
        "field": "城市",
        "output_name": "城市"
      }
    ],
    "metrics": [
      {
        "id": "sales_revenue",
        "function": "sum",
        "field": "销售额",
        "output_name": "销售收入"
      },
      {
        "id": "order_count",
        "function": "count",
        "mode": "rows",
        "output_name": "订单数量"
      },
      {
        "id": "average_order_amount",
        "function": "average",
        "field": "销售额",
        "output_name": "平均订单金额"
      }
    ],
    "sort": [
      {
        "by": "sales_revenue",
        "direction": "desc"
      }
    ]
  },
  "system": {
    "required_checks": [
      "input_identity_preserved",
      "request_contract_preserved",
      "acceptance_contract_preserved",
      "attempt_isolated",
      "output_reopenable",
      "validated_artifact_preserved",
      "publication_matches_validation",
      "evidence_complete"
    ]
  }
}
```

快照保存完整定义，而不是只保存 ID。改变 `count.rows` 为 `count.non_empty`、修改过滤值或改变输出 Sheet 都会改变快照。

以下内容不进入 Acceptance Snapshot：

- `user_request` 审计文本；
- 物理 Field Binding；
- Runtime 选择的 Molecule、Atom 或内部 Plan；
- Task/Attempt 运行目录；
- Agent 最终业务语义判断。

Field Binding 可以在同一 Acceptance 下修正，但每个 Attempt 必须记录实际使用的 Binding hash。

## 4. 固化时点

```text
接收 Task Request
→ 校验公开契约
→ 检查 Acceptance 引用完整性
→ 读取并固定输入文件身份
→ 展开 Acceptance Snapshot
→ 计算 acceptance_hash
→ 创建 Task
→ 进行 Field Binding
→ 创建 Attempt
```

若输入文件不存在、Acceptance 引用了不存在的组件 ID，或输入与输出路径相同，不创建 Task。

Task 创建后：

- Acceptance Snapshot 和 `acceptance_hash` 永久不变。
- Field Binding 修订可以创建新的 `request_revision`。
- 每次执行创建新的 Attempt。
- 任何会改变 Acceptance Snapshot 的请求修改必须返回 `CREATE_NEW_TASK`。

## 5. Hash 边界

```text
acceptance_hash = SHA-256(JCS(acceptance_snapshot))
```

- 使用 RFC 8785 JSON Canonicalization Scheme（JCS）生成 UTF-8 字节。
- Snapshot 只允许 JSON 原生类型；禁止 NaN、Infinity、日期对象和平台相关路径对象。
- 路径在计算前规范化为绝对路径和 `/` 分隔形式。
- 数值按 JCS 规则规范化，不能依赖 Python `repr()`。
- 每个 Attempt 开始、验证和发布前都重新读取并核对 `acceptance_hash`。

同时记录以下独立 hash，不能混成一个值：

```text
input_sha256
request_revision_hash
acceptance_hash
binding_hash
internal_plan_hash
temporary_output_sha256
evidence_hash
published_output_sha256
```

独立 hash 使 Runtime 能说明究竟是用户输入、字段绑定、内部编译、输出文件还是证据发生变化。

## 6. Business Acceptance 展开规则

Runtime 根据冻结的组件定义生成检查，不接受 Agent 自写 Validator。

### 6.1 Filters

每个 required filter 生成：

```text
filter_definition_preserved
filter_replay
```

`filter_replay` 独立重放所有声明过滤条件，并生成过滤前行数、过滤后行数和过滤结果摘要。它不是“确认 filter_rows 执行过”。

### 6.2 Dimensions

每个 required dimension 生成：

```text
dimension_column_present
dimension_group_set_reconciliation
```

Validator 独立计算过滤后来源数据的分组键集合，并与输出逐组比较。

### 6.3 Metrics

每个 required metric 生成：

```text
metric_column_present
metric_group_reconciliation
```

`metric_group_reconciliation` 按冻结定义对每个分组独立复算：

- `sum`：对该组有效数值求和。
- `average`：对该组有效数值求平均。
- `count.rows`：统计过滤后该组行数。
- `count.non_empty`：统计过滤后该组指定字段非空值数量。

必须逐分组比较，不能只比较全表总计。容差由 Task Type 契约固定，第一阶段数值默认绝对容差 `1e-6`，Agent 不能调大容差让错误通过。

Runtime 只证明“请求明确声明的数学定义被正确执行”，不证明“该数学定义是用户真正想要的业务口径”。

### 6.4 Sort

每个 required sort 生成：

```text
sort_definition_preserved
sort_order_reconciliation
```

Validator 读取最终输出重新检查顺序。排序字段通过组件 ID 解析，不能依赖 Agent 再次提交列名。

### 6.5 Output shape

根据冻结的 Dimension 和 Metric 顺序生成：

```text
required_sheet_present
output_columns_exact
output_row_count_reconciliation
```

`output_columns_exact` 第一阶段要求表头集合和顺序完全一致，不允许缺列、重复列或未声明附加列。

## 7. Attempt Evidence

每个 Attempt 无论成功或失败都生成不可变 Evidence：

```json
{
  "schema_version": "1.0",
  "task_id": "task-01K0...",
  "request_revision": 2,
  "attempt_id": "attempt-002",
  "status": "RUNTIME_PASS",
  "hashes": {
    "input_sha256": "...",
    "request_revision_hash": "...",
    "acceptance_hash": "...",
    "binding_hash": "...",
    "internal_plan_hash": "...",
    "temporary_output_sha256": "...",
    "published_output_sha256": "..."
  },
  "runtime": {
    "sheetpilot_version": "0.1.0",
    "task_contract_version": "1.0",
    "validator_version": "1.0"
  },
  "checks": [
    {
      "id": "metric_group_reconciliation:sales_revenue",
      "category": "business",
      "subject_id": "sales_revenue",
      "status": "PASS",
      "method": "independent_group_recompute",
      "expected": {
        "group_count": 4
      },
      "actual": {
        "group_count": 4
      },
      "evidence": {
        "matched_groups": 4,
        "mismatched_groups": []
      }
    }
  ],
  "execution": {
    "requested_task_type": "summarize_table",
    "internal_plan_hash": "...",
    "executed_operations": []
  },
  "publication": {
    "output_file": "D:/result/city-summary.xlsx",
    "published": true
  },
  "evidence_hash": "..."
}
```

`executed_operations` 由 Runtime 生成，仅用于审计内部执行事实。Agent 不依据它推断 Acceptance 是否通过；检查结果才是验收事实。

Evidence 计算 `evidence_hash` 时排除自身的 `evidence_hash` 字段，其余内容全部进入规范化 hash。

## 8. RUNTIME_PASS

只有同时满足以下条件才返回 `RUNTIME_PASS`：

1. 所有 Business Acceptance 检查为 PASS。
2. 所有 System Acceptance 检查为 PASS。
3. Evidence 字段完整且 `evidence_hash` 有效。
4. 临时输出 hash 与验证对象一致。
5. 发布成功，最终输出 hash 与验证通过的文件一致。

第一阶段不存在“重要检查失败但整体 PASS”。非阻断信息放入独立 `warnings`，不能伪装成 Acceptance check。

验证失败返回 `VALIDATION_FAILED`，不发布结果。发布失败返回 `PUBLICATION_FAILED`，不能返回 RUNTIME_PASS。

## 9. Agent 语义判断

Agent 在 Runtime Evidence 之外报告：

```json
{
  "runtime_status": "RUNTIME_PASS",
  "semantic_assessment": {
    "status": "accepted",
    "rationale": "用户要求订单数量按过滤后记录行数统计，请求使用 count.rows。",
    "based_on_evidence_hash": "..."
  }
}
```

`semantic_assessment.status`：

```text
accepted
rejected
not_assessed
```

Agent 不能把 `RUNTIME_PASS` 改写成“业务语义验证通过”。若 Agent 判断请求口径不正确，应标记 `rejected` 并创建新 Task；不能修改已冻结 Acceptance 后复用旧 Task。

## 10. 不可缩减规则

以下修改在同一 Task 中全部拒绝：

- 删除 required filter、dimension、metric 或 sort。
- 修改被 Acceptance 引用组件的字段、函数、mode、过滤值或输出名称。
- 修改输出文件、Sheet 或 anchor。
- 调大 Validator 容差。
- 删除或关闭 System Acceptance。
- 用新的 Acceptance 对象覆盖原快照。

允许的同 Task 修订仅限 Runtime 明确返回的 Field Binding 路径。Binding 修订改变 `request_revision_hash` 和 `binding_hash`，但不改变 `acceptance_hash`。

## 11. 持久化边界

建议的逻辑产物：

```text
task.json
acceptance-snapshot.json
request-revisions/<revision>.json
attempts/<attempt-id>/evidence.json
```

具体目录命名由 Task 状态机 Ticket 决定。无论物理布局如何，Acceptance Snapshot 必须是 Task 级不可变对象，Evidence 必须是 Attempt 级不可变对象。

## 12. Skill 影响

Skill 只需要：

1. 在首次 Task Request 中明确列出所有必需组件 ID。
2. 失败恢复时保持 `acceptance_hash` 不变。
3. 最终引用 `evidence_hash` 和 `RUNTIME_PASS`。
4. 独立给出业务语义判断。

Skill 不再选择 Validator、不再手写对账规则、不再根据执行记录自行宣布 PASS。
