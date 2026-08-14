# SheetPilot Excel Agent Skill 优化设计：文本层重构 + 字段清单直供 Agent

- 日期：2026-08-14
- 状态：待用户审阅
- 分支：codex/wayfinder-agent-interface（基线 commit 87d19a1，Route A）

## 1. 背景与动机

Route A 为字段绑定增加了确定性语义评分（char-bigram Dice + 置信度 + 3 样本候选），但存在两个结构性问题：

1. **Runtime 在假装做语义**。char-bigram 评分对中文业务词是弱语义模拟，在最难的歧义场景（净销售额 vs 含税销售额）几乎无用；语义理解本应是 Agent 的核心能力。
2. **Agent 没有足够的判断证据**。候选只带 3 个任意样本，Agent 既不能读表也不能再要信息，语义绑定短板无法真正补上。

同时，Skill 文本层存在稳定性问题：四段重叠禁令、让 Agent 手写 PowerShell 生成结果目录、复述 Runtime 本会校验的契约。

**设计原则**：语义理解全部交给 Agent，Runtime 只负责如实呈现事实（字段清单）与机械正确性（精确匹配校验、执行、审计）。即「把 Route A 丢掉，直接让 Agent 拿到问题与表的字段，去做语义理解」。

## 2. 范围

**做**：

1. SKILL.md 重构：压成「一个循环 + 一张决策表 + 最小报告契约」。
2. 包装脚本增强：结果目录生成收进脚本；`task-types` 支持请求前字段清单查询。
3. 字段清单机制：`NEEDS_BINDING` 响应携带 `field_inventory`，删除 Route A 全部语义评分机制。
4. 评测与文档同步（doc 14/16/19、CLAUDE.md、evaluator、测试用例、SKILL.md）。

**不做（YAGNI，后续立项）**：

- 新任务类型（count_distinct、多源/多 Sheet 任务）。
- 独立的按需深查命令（第 4 个公开入口）——清单已含常见判断所需证据，真不够再加。
- 清单分页、缓存持久化。

## 3. 设计

### 3.1 SKILL.md 新形态（目标 ≤ 50 行）

三块内容：

1. **入口**：从本 SKILL.md 绝对路径取 `<skill-root>`，用包装脚本的三个子命令 `task-types` / `task-run` / `task-status`。
2. **循环**：`task-types`（需要时带 `--input`）→ 按返回契约写 Task Request → `task-run` → 按响应查决策表。输出路径写 `<AUTO-RESULT-DIR>/<文件名>`，`task-run` 带 `--auto-result-dir <父目录>` 由包装脚本生成目录（见 3.2）。
3. **决策表**（以响应 status 为键，每个状态只对应一个允许动作）：

| 响应 | 允许的唯一下一步 |
|---|---|
| `RUNTIME_PASS` | `task-status` 复核：`state=RUNTIME_PASS` + `artifact_integrity=MATCHED` + `delivery_valid=true` 三者齐备才交付 |
| `NEEDS_BINDING` | 对照响应中的 `field_inventory` 做语义判断 → 只选清单给出的 `candidate_id`（或改提精确表头名）→ `task-run` 提交 amendment |
| `REQUEST_INVALID` | 只按 `recovery.allowed_amendments` 修改 → `task-run` 重提 |
| `EXECUTION_FAILED` / `VALIDATION_FAILED` / `PUBLICATION_FAILED` | 按 `recovery.action`：`RETRY_ATTEMPT` 才重试，否则停止报告 |
| `CAPABILITY_UNSUPPORTED` | 停止，报告能力不支持 |
| `INPUT_CHANGED` | 停止，报告需新建 Task |
| `INTERNAL_ERROR` / `CONFIGURATION_REQUIRED` / `HUMAN_ACTION_REQUIRED` | 立即停止（停止门），只向用户报告 |

4. **报告契约**（成功）：`task_id`、`attempt_id`、`request_revision`、最终输出路径、`runtime_status`、`artifact_integrity`、`delivery_valid`、`acceptance_hash`、`internal_plan_hash`、`semantic_assessment`（accepted / rejected / not_assessed 三值）。

**删减**：

- 四段重叠禁令（最高优先级纪律/唯一入口/请求边界/黑盒纪律）→ 合并为一行「只调用三个子命令；一切经包装脚本，不直接读写工作簿」。
- PowerShell 生成结果目录片段 → 收进包装脚本（见 3.2）。
- count.rows/count.non_empty 语义说明、输出新文件新 Sheet 规则 → 删除（Runtime 已校验，失败会带 JSON Pointer 返回）。
- 新增一行：「请求不合规是正常路径，Runtime 会返回精确修订指令，照做即可」——消解 Agent 因怕错而漂移去翻源码的动机。

### 3.2 包装脚本改动

1. `task-run --auto-result-dir <父目录>`：请求中 `output_file` 含 `<AUTO-RESULT-DIR>` 占位符时，包装脚本内部生成并创建结果目录（北京时间戳 + 6 位随机标识，命名格式与现 Skill 定义一致），替换占位符后提交。Agent 只写占位符 + 文件名，不再手写 PowerShell。目录生成逻辑是包装脚本内部实现，不暴露为 Agent 可见子命令。
2. `task-types --input <file> [--sheet <name>]`：请求前字段清单查询（见 3.3），不创建 Task，纯只读。
3. Agent 可见子命令保持三个（`task-types` / `task-run` / `task-status`），原行为不变。

### 3.3 字段清单机制（替换 Route A）

**删除**：`_score_header`、`_semantic_candidates`、`SEMANTIC_CANDIDATE_FLOOR`、候选上的 `confidence`/`evidence`、Route A 两个集成测试。

**NEEDS_BINDING 响应**携带 `field_inventory`——绑定源的全部可见表头，每条含：

```json
{
  "id": "candidate-8f1472c1",
  "header": "净销售额",
  "column": "G",
  "inferred_type": "number",
  "null_ratio": 0.02,
  "sample_values": [100, 200, 300],
  "neighbor_headers": ["数量", "单价"]
}
```

规则：

- 无评分、无 top-K、无「语义候选」。清单按 Sheet/列顺序稳定排序；样本最多 3 个非空值、字符串≤64 字符；不含公式源码、隐藏 Sheet、环境变量。
- **Slot 状态只反映精确匹配事实**：`RESOLVED`（唯一精确 + 类型兼容，自动绑定）/ `AMBIGUOUS`（多个同名列）/ `UNRESOLVED`（无精确匹配）。
- **「无候选 → HUMAN_ACTION_REQUIRED」删除**。Runtime 不替 Agent 判断「这个词跟哪个字段都不像」；Agent 对照清单自行判断，确实无字段可对时自行停止并向用户报告。`HUMAN_ACTION_REQUIRED` 保留给文件缺失、权限、输出冲突等非绑定原因。
- **落地仍只能走 candidate_id**（清单的 id 即候选 id），或重新提交精确表头名。Runtime 只校验存在性与类型兼容。
- **`task-types --input <file> [--sheet <name>]`**：请求前查询同一清单。带 `--sheet` 返回该 Sheet；不带则按可见 Sheet 分组返回。不创建 Task、不持久化 Profile（每次按需读，复用 `_bind` 的读表逻辑——需把清单构建抽成 `_build_inventory` 供两处复用）。
- `contract.py` 的 `field_binding` 描述符改为 `exact_header_match_with_field_inventory`。

**不变项**：精确匹配自动绑定；Acceptance Contract 冻结；修订原子性与 revision conflict；SHA-256 审计链；黑盒纪律（三入口、不读源码、不读写工作簿）。

### 3.4 数据流（净销售收入 案例）

```text
路径 1（请求前查询，新 S8 场景）：
  task-types --input orders.xlsx --sheet 交易流水
    → field_inventory（含 净销售额 / 数量 / 单价 …）
    → Agent 语义理解：用户要的是「净销售额」→ 第一版请求直接写精确表头
    → task-run → 精确自动绑定 → RUNTIME_PASS（≤3 次 CLI 调用）

路径 2（修订，H1 场景）：
  task-run（field=净销售收入，非精确）
    → NEEDS_BINDING + field_inventory
    → Agent 对照清单判断 → task-run 提交 amendment（candidate_id 或精确表头名）
    → READY → 执行 → RUNTIME_PASS
```

### 3.5 错误处理

- `task-types --input` 复用现有 envelope：`INPUT_NOT_FOUND`（文件不存在/不受支持）、`INVALID_VALUE`（--sheet 名不存在）、`CAPABILITY_UNSUPPORTED`（工作簿类型不支持）。
- 清单查询是纯读操作，不产生 Task 状态；无 `INPUT_CHANGED` 语义（未绑定输入身份）。
- 修订阶段的错误处理完全沿用 doc 14 机器可恢复协议，无新增 code。

## 4. 评测与文档同步

| 位置 | 现状 | 改为 |
|---|---|---|
| `evaluator.py` | `ALLOWED_COMMANDS` = 三命令 | 不变（无新命令）；明确「带 `--input` 的 task-types 属允许调用」 |
| 测试用例 H2 | 「Runtime 尚未开放 Binding Amendment，应停止」 | 翻转为成功用例：Agent 对照清单选出正确 candidate_id 完成；为 05 fixture 补 Oracle |
| doc 19 S2 | 「根据 Candidate header、类型和有限样本选择」 | 改为「根据 field_inventory 语义判断选择」 |
| 新增场景 S8 | — | 请求前查询：第一版请求即写对字段名，一次通过，happy path ≤3 次 CLI 调用 |
| H1 | 靠 Route A 模糊候选恢复 | 机制改为「NEEDS_BINDING + 清单 → 选净销售额」，Oracle 不变 |
| doc 16 | §5 候选带 confidence/evidence；§6 语义候选段落；§7 示例 | 改为清单条目 + 「语义判断由 Agent 完成」；示例换 field_inventory |
| doc 14 | §7 示例含 confidence 0.82 语义候选 | 去掉语义候选，换成清单示例 |
| CLAUDE.md | field binding 描述含 `_score_header` | 改「精确匹配自动绑定；未命中返回字段清单，语义判断由 Agent 完成」 |
| SKILL.md | NEEDS_BINDING 行提及 confidence/sample_values | 按 3.1 决策表更新 |

## 5. 测试方案

**单元**：`_build_inventory`（稳定排序、样本截断、64 字符上限、隐藏 Sheet 排除、`--sheet` 过滤）；amendment 校验。

**集成**（`test_task_api.py`）：

- `task-types --input` 返回清单（形状、两次调用字节一致）。
- 模糊字段 → NEEDS_BINDING + 清单 → 按 candidate_id 修订 → RUNTIME_PASS（替换 `test_semantic_fuzzy_field_surfaces_candidate_without_auto_bind`）。
- 无关字段 → NEEDS_BINDING + 清单照给，`recovery.action = PROVIDE_BINDING`（替换 `test_unrelated_field_yields_no_candidate_and_human_action`）。
- 同名列 → AMBIGUOUS slot + 清单两行可区分（样本/邻居不同）。
- 修订后 acceptance_hash 不变（保留原契约测试）。

**Agent 黑盒**：H1 重跑、H2 翻转为成功、新增 S8；全部场景 3 次全新 Agent run 过 Release Gate（门禁规则本身不动）。

## 6. 风险与开放项

1. **清单体积**：几十列大表的清单占用 Agent 上下文。当前条目紧凑（约一行 JSON/列）；先不做分页，S8 及 H1 实测后再定。
2. **「不替 Agent 判死」的边界**：Agent 可能强行选错（如把「区域」绑成「城市」）。由精确匹配校验、类型兼容、Oracle 和独立 semantic_review 兜底；语义错误与 RUNTIME_PASS 分开报告。
3. **H2 fixture 待确认**：两列同名「销售额」必须有可判定的正确答案（样本/相邻表头可区分），否则 Oracle 无法定义——实现前先检查 05 fixture，必要时调整 fixture 或 prompt。
4. **Route A 已提交代码的清理**：删除评分机制会改 `runtime.py` 公开响应形状，需同步全部引用点（integration 测试、CLAUDE.md、SKILL.md）。

## 7. 完成定义

1. SKILL.md 重构落地且 12 用例 + S8 的 Release Gate 通过（S8 3/3，其余保持原门槛）。
2. Route A 语义评分机制从 runtime.py / contract.py 完全移除，测试同步替换。
3. `field_inventory` 与 `task-types --input` 上线，集成测试全绿。
4. doc 14/16/19、CLAUDE.md、evaluator、测试用例文档同步完成，无残留「语义候选/confidence」表述。
5. 评测规则与产品契约漂移清零（H2 预期与 Runtime 实际行为一致）。
