# Task、Attempt 与发布状态机原型 V1

## 1. 决策目标

本协议把以下责任从 Agent 和 Skill 移入 Runtime：

- 创建、命名、清空和复用运行目录。
- 为失败重试选择新的目录或编号。
- 防止并发执行同一个 Task。
- 从进程崩溃或中断中恢复。
- 判断旧验证证据是否仍对应当前输出。
- 在验证通过后原子发布最终文件。

Agent 只提交 Task Request、授权的 Task Amendment 或重试动作，并使用 `task_id` 查询状态。

## 2. 身份模型

### 2.1 Task ID

```text
task-<ULID>
```

Task 是固定输入身份、Task Request、Acceptance Snapshot 和输出目标的稳定容器。Task ID 由 Runtime 创建，Agent 不提供。

### 2.2 Request Revision

```text
revision 1, revision 2, ...
```

Revision 是 Task 内不可变请求状态。第一版来自初始 Task Request；后续版本只能包含 Runtime 授权的 Field Binding 修订。

### 2.3 Attempt ID

```text
attempt-001
attempt-002
...
```

Attempt 是某个 Request Revision 的一次不可变执行。编号由 Runtime 在持有 Task 锁时顺序分配，不能复用或删除。

## 3. Runtime 状态根目录

Agent API 不接受 `run-dir`、`task-dir` 或 `attempt-dir` 参数。

Runtime 从安装级配置读取唯一 `state_root`：

```text
<state_root>/tasks/<task-id>/
```

- Windows 默认使用当前用户的 Local App Data 下 SheetPilot 专用目录。
- macOS/Linux 使用对应用户应用数据目录。
- 测试通过 Runtime 构造参数注入临时 `state_root`，不通过 Agent 请求覆盖。
- 环境变量或配置文件只属于部署配置，不进入 Skill 工作流。

目录创建必须使用排他创建和规范化路径检查。Runtime 不接受已有任意目录作为新 Task 目录。

## 4. 逻辑目录结构

```text
tasks/<task-id>/
├── task.json
├── acceptance-snapshot.json
├── workbook-profile.json
├── events.jsonl
├── current-state.json
├── lock
├── revisions/
│   ├── revision-001.json
│   └── revision-002.json
└── attempts/
    ├── attempt-001/
    │   ├── attempt.json
    │   ├── binding-snapshot.json
    │   ├── internal-plan.json
    │   ├── working-copy.xlsx
    │   ├── temporary-output.xlsx
    │   ├── execution.json
    │   ├── evidence.json
    │   └── result.json
    └── attempt-002/
        └── ...
```

这些路径是 Runtime 内部实现。Agent API 返回对象 ID、状态、hash 和证据内容，不要求 Agent 打开目录。

Task 创建后不清空目录。Attempt 终态后其目录只读；后续重试创建新 Attempt。

## 5. Task 状态

第一阶段公开 Task 状态：

```text
RECEIVED
NEEDS_BINDING
READY
RUNNING
VALIDATING
PUBLISHING
RUNTIME_PASS
FAILED
```

`PUBLISHING` 补充了此前简化状态机中没有显式展示的发布阶段，确保 publication error 有稳定状态归属。

### 5.1 状态含义

| 状态 | 含义 |
|---|---|
| `RECEIVED` | Task 已创建，Acceptance 已冻结，尚未完成字段绑定评估 |
| `NEEDS_BINDING` | 存在未解决或歧义 Binding Slot，未创建 Attempt |
| `READY` | 当前 Revision 可执行，当前没有运行中的 Attempt |
| `RUNNING` | 某个 Attempt 正在执行内部计划 |
| `VALIDATING` | Attempt 已生成临时输出，正在独立验收 |
| `PUBLISHING` | 验收通过，正在原子发布并核对最终 hash |
| `RUNTIME_PASS` | 最新成功 Attempt 已发布，Runtime Evidence 完整 |
| `FAILED` | 最新处理失败；是否可恢复由 `terminal` 与 Recovery Directive 决定 |

`FAILED` 不天然表示终态。响应必须同时包含：

```json
{
  "state": "FAILED",
  "terminal": false,
  "recovery": {
    "action": "RETRY_ATTEMPT"
  }
}
```

若 `terminal` 为 true，原 Task 不再接受 Amendment 或 Retry。

## 6. Attempt 状态

```text
CREATED
RUNNING
EXECUTION_FAILED
VALIDATING
VALIDATION_FAILED
PUBLISHING
PUBLICATION_FAILED
RUNTIME_PASS
INTERRUPTED
```

Attempt 只能向前转换。一旦进入 `EXECUTION_FAILED`、`VALIDATION_FAILED`、`PUBLICATION_FAILED`、`RUNTIME_PASS` 或 `INTERRUPTED`，即成为不可变终态。

Task 可以基于 Recovery Directive 创建新 Revision 或新 Attempt，但不会改变旧 Attempt 状态。

## 7. 状态转换

```text
RECEIVED
├── NEEDS_BINDING
│   ├── NEEDS_BINDING   accepted amendment, still unresolved
│   └── READY           all bindings resolved
└── READY               all bindings resolved automatically

READY
└── RUNNING
    ├── FAILED          execution failure or interruption
    └── VALIDATING
        ├── FAILED      validation failure
        └── PUBLISHING
            ├── FAILED  publication failure
            └── RUNTIME_PASS

FAILED (terminal=false)
├── NEEDS_BINDING       authorized binding correction
└── READY               authorized retry without request change
```

`RUNTIME_PASS` 是 Task 成功终态。若用户之后希望改变请求、Acceptance 或输入文件，创建新 Task。

## 8. Initial task-run 幂等性

Runtime 对初始 Task Request 计算：

```text
submission_hash = SHA-256(JCS(task_request_without_user_request))
```

`user_request` 是审计文本，不影响执行身份。

当 `task-run` 收到与现有 Task 相同的 `submission_hash`、`input_sha256` 和规范化输出路径时：

- 现有 Task 非终态：返回现有 Task 状态，不创建重复 Task。
- 现有 Task 为 `RUNTIME_PASS` 且发布文件 hash 仍匹配：返回现有结果。
- 现有 Task 为 terminal failure：返回现有 Task 与 `CREATE_NEW_TASK` 指令。
- 输出文件已被外部修改或替换：返回 artifact integrity failure，不覆盖。

这使 Agent 在命令超时、响应丢失或不确定是否成功时可以安全重试同一请求，无需自己生成 idempotency key。

## 9. Task 锁与并发

每个 Task 使用 Runtime 管理的排他锁：

- 创建 Revision、分配 Attempt ID、状态转换和发布必须持有锁。
- `task-status` 只读查询不需要长期占用执行锁。
- 同一 Task 同时只允许一个非终态 Attempt。
- 并发 `task-run` 不创建两个 Attempt；后到请求返回当前状态。
- 锁包含 owner token、进程身份和 lease expiry，不只依赖永久 lock 文件。

所有状态写入采用：

```text
写入同目录临时文件
→ flush
→ fsync（平台支持时）
→ atomic replace current-state.json
→ append event
```

状态快照可从 append-only `events.jsonl` 重建。

## 10. 崩溃与中断恢复

当 `task-status` 或新的 `task-run` 发现：

- Task 为 `RUNNING`、`VALIDATING` 或 `PUBLISHING`；
- 锁 lease 已过期；
- 没有存活 owner；

Runtime 将对应 Attempt 标记为 `INTERRUPTED`，保存 `PROCESS_INTERRUPTED` Diagnostic，并把 Task 转为：

```text
FAILED, terminal=false, recovery.action=RETRY_ATTEMPT
```

Runtime 不复用中断 Attempt 的工作副本或临时输出。重试创建全新 Attempt。

如果中断发生在原子发布之后但状态尚未更新，恢复流程先核对发布文件 hash：

- 与已验证临时文件一致：补全 publication evidence，可恢复为 `RUNTIME_PASS`。
- 不一致或证据不足：标记 `PUBLICATION_FAILED`，不猜测成功。

## 11. 重试规则

### 11.1 RETRY_ATTEMPT

适用于请求、Acceptance、Binding 和输入均未变化的瞬时执行或发布错误。

```text
same task_id
same request_revision
same acceptance_hash
same binding_hash
new attempt_id
new isolated attempt directory
```

### 11.2 Binding correction

适用于 Recovery Directive 授权的 Binding 路径：

```text
same task_id
new request_revision
same acceptance_hash
new binding_hash
new attempt_id after READY
```

### 11.3 Retry budget

第一阶段每个 Request Revision 最多创建 3 个 Attempt。相同 failure fingerprint 连续出现 2 次后，Runtime 不再建议无变化重试，改为：

```text
FAILED, terminal=false, recovery.action=HUMAN_ACTION_REQUIRED
```

failure fingerprint 使用公开 error code、phase、Diagnostic code/path 和相关 hash 计算，不包含时间戳或自然语言 message。

新 Binding Revision 可以获得新的 Attempt 预算；不能通过提交无效 revision 刷新预算。

## 12. 执行隔离

每个 Attempt：

1. 在自己的目录创建输入工作副本。
2. 只对工作副本执行内部计划。
3. 生成自己的临时输出、执行记录和 Evidence。
4. 不读取或修改其他 Attempt 的工作文件。
5. 不直接写最终输出路径。

执行前重新校验：

```text
input_sha256
request_revision_hash
acceptance_hash
binding_hash
internal_plan_hash
```

任一不一致时，Attempt 在工作簿修改前失败。

## 13. 验证与发布门禁

```text
temporary-output.xlsx
→ reopen
→ Business Acceptance
→ System Acceptance
→ evidence_hash
→ publication staging
→ atomic publish
→ published hash verification
→ RUNTIME_PASS
```

Validator 只能读取固定输入、Binding Snapshot、Acceptance Snapshot 和 Attempt 临时输出。不能依据 Agent 最终解释调整检查范围。

验证失败：

- Attempt 状态 `VALIDATION_FAILED`。
- Task 状态 `FAILED`。
- 不创建或修改最终输出文件。
- Evidence 保留全部失败检查。

## 14. 原子发布

发布在最终输出文件的同一目录创建 Runtime staging 文件：

```text
.<output-name>.sheetpilot-<task-id>-<attempt-id>.tmp
```

流程：

1. 验证输出目标仍符合 Task 固定路径。
2. 确认目标文件不存在；第一阶段不覆盖已有文件。
3. 把已验证临时文件复制到同目录 staging 文件。
4. flush 并在平台支持时 fsync。
5. 校验 staging hash 等于 validated artifact hash。
6. 使用同文件系统的 no-replace 原子操作发布，例如硬链接创建或平台原生 `RENAME_NOREPLACE`。
7. 重新读取最终文件 hash。
8. 写入 publication evidence。
9. Attempt 与 Task 转为 `RUNTIME_PASS`。

若目标文件在步骤 2 之后被其他进程创建，no-replace 操作必须失败，不能覆盖。Runtime 删除自己的 staging 文件并返回 `OUTPUT_CONFLICT`。

Runtime 不得使用可能覆盖已有目标的普通 `os.replace()` 或平台默认 rename。若当前文件系统不支持可证明的 no-replace 原子发布，返回 `PUBLICATION_FAILED`，不能降级为先删除再复制。

第一阶段不支持 overwrite。用户要求替换已有输出时必须先由人处理旧文件或选择新的输出路径并创建新 Task。

## 15. 发布后的完整性

`RUNTIME_PASS` 是历史 Attempt 结论，不因外部修改而改写。`task-status` 额外返回当前 Artifact Integrity：

```text
MATCHED
MISSING
MODIFIED
```

```json
{
  "state": "RUNTIME_PASS",
  "artifact_integrity": "MODIFIED",
  "delivery_valid": false,
  "validated_published_sha256": "...",
  "current_published_sha256": "..."
}
```

Agent 只有在 `state=RUNTIME_PASS`、`artifact_integrity=MATCHED` 且 `delivery_valid=true` 时才能交付当前文件。

外部修改不会触发 Runtime 自动覆盖或恢复。需要重新生成时创建新 Task。

## 16. task-status 响应

```json
{
  "schema_version": "1.0",
  "task_id": "task-01K0...",
  "state": "FAILED",
  "terminal": false,
  "request_revision": 2,
  "acceptance_hash": "...",
  "latest_attempt": {
    "attempt_id": "attempt-002",
    "state": "VALIDATION_FAILED",
    "request_revision": 2,
    "started_at": "...",
    "finished_at": "..."
  },
  "artifact_integrity": null,
  "delivery_valid": false,
  "recovery": {
    "action": "RETRY_ATTEMPT",
    "retryable": true
  },
  "evidence": {
    "evidence_hash": "...",
    "runtime_status": "VALIDATION_FAILED"
  }
}
```

Agent 不需要路径信息即可恢复。必要证据通过 `task-status` 或后续只读 evidence 查询返回。

## 17. 事件模型

至少记录：

```text
task_created
acceptance_frozen
inspection_completed
binding_required
revision_created
task_ready
attempt_created
execution_started
execution_completed
validation_started
validation_failed
validation_passed
publication_started
publication_failed
publication_completed
attempt_interrupted
task_failed
task_runtime_passed
artifact_integrity_changed
```

Event 包含 event ID、Task ID、可选 Revision/Attempt ID、前后状态、时间和相关 hash。Event 不保存敏感单元格内容。

## 18. Skill 行为

Skill 只需要：

1. 调用 `task-run --request <json>`。
2. 根据返回状态提供 Binding、请求 Retry 或停止并报告。
3. 使用 `task-status --task-id <id>` 恢复未知命令结果。
4. 仅在 `RUNTIME_PASS + MATCHED + delivery_valid` 时交付。

Skill 不创建目录、不清理失败产物、不复用 Attempt、不直接调用 Validator、不修改已发布文件。
