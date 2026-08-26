# SheetPilot 快速测评设计

## 目标

以最快速度得到可信、可复现、可追溯的测评结果。现有 `sheetpilot-run-review` 与 `sheetpilot-run-scorer` 可以继续作为交互入口，但不作为批量测评的必经层。

成功标准：

- 同一个 run 的单次模式与批量模式生成语义等价的 `run-bundle.json` 和 `score.json`。
- 每个完成测评的 run 都返回 0–100 分；`ERROR` 因证据不足可以没有分数。
- 每个成功场景仍满足现有 run-bundle 契约，包含 `oracle_result`、`final_report`、`commands`、`semantic_review` 和版本信息。
- 缺失证据保持缺失并触发明确错误，不被转换成零违规或默认通过。
- 一个 run 失败不阻断其他 run；批次最终返回逐项状态和非零退出码。
- 性能结论来自固定样本的实测，不在实现前承诺具体倍数。

## 边界

确定性测评核心只接收本地 `replay.raw.json`。分享 URL 的页面抓取依赖浏览器会话、鉴权和页面接口，由独立 acquisition adapter 负责，但属于端到端性能基准的一部分。

已验证的现状是：分享页 GET 返回 HTML；前端使用 `/api/v1/share/get_share`，直接匿名 POST 返回 401。因此 v1 支持两种输入：已导出的本地 replay，以及复用已登录浏览器会话的批量采集器。只有在 BitAgent 提供稳定、文档化且有集成测试的 JSON API 后，才增加无浏览器 HTTP 下载器。

采集器只负责将 URL 原样映射为 `replay.raw.json` 并记录 URL、采集时间、HTTP/页面状态和 SHA-256。采集失败是 acquisition ERROR，不进入评分核心；不得把 HTML、登录页或错误 JSON 当作 replay。

## 核心决策

测评拆成两个速度层级：

- **Fast lane**：解析 replay、提取证据、运行 Oracle、检查违规、计算确定性 gate 和分数。全部由一个 Python CLI 完成，可并行、可缓存，不调用 LLM。
- **Semantic lane**：只处理场景声明要求语义复核，或 Fast lane 无法可靠提取证据的 run。它读取小型 review packet，可由 Codex skill、其他模型或人工完成。

绝大多数结构明确的成功/失败测评应在 Fast lane 结束。不能让每个 run 都为“可能需要的语义判断”支付一次 LLM 往返。

场景注册表包含 31 个与正式 Prompt 一一对应的 active 场景。未声明 `semantic_review_required=true` 不能作为跳过语义复核的依据：部分场景明确要求澄清、能力边界说明或派生指标，当前 Oracle 只验证输出是否忠实执行 Agent 自己提交的 Task Request，并不验证该 Request 是否忠实表达用户 prompt。

因此 Fast lane 的资格由场景预检决定，而不是由字段缺省决定：

- 场景提供结构化 `expected_request` 或 `allowed_requests`，可以确定性比较 prompt 意图与 Agent Request，才可直接 FINAL。
- 正确停止场景提供 `expected_behavior=correct_stop`、允许状态和必须出现的报告要点，才可确定性评分。
- 要求澄清、能力边界解释、派生指标说明或人工判断的场景显式进入 Semantic lane。
- 缺少上述契约的场景是 `SCENARIO_CONFIG_ERROR`，不是自动 PASS/FAIL，也不能生成正式分数。

## 结论与分数

门禁结论和量化分数是两个正交输出：

- `task_result` 回答“是否满足交付标准”，取值为 `PASS`、`FAIL`、`NEEDS_SEMANTIC_REVIEW` 或 `ERROR`。
- `benchmark_score` 回答“这次执行完成得多好”，取值为 0–100。
- `score_status` 标识分数是否可用于正式比较，取值为 `FINAL`、`PROVISIONAL` 或 `UNAVAILABLE`。

兼容现有输出：`quality_score` 继续只在 PASS 时有值，`diagnostic_score` 继续用于诊断；新增的 `benchmark_score` 才是批量横向比较使用的分数。不能直接把现有 `diagnostic_score` 改名使用，因为它没有充分计入 Runtime、Oracle、输入完整性和关键违规。

建议的 100 分组成：

| 维度 | 分值 | 证据 |
| --- | ---: | --- |
| 结果正确性 | 50 | 预期 Runtime 结果、Oracle、输入未变化 |
| 契约与安全 | 20 | Acceptance 完整、零 Critical Violations |
| 接口与效率 | 15 | 只用公开命令、调用次数、无无关探索、耗时 |
| 证据与报告 | 10 | 命令轨迹、task-status、final report、版本和哈希 |
| 输出可用性 | 5 | 文件存在、可打开、目标 Sheet 与交付路径有效 |

计分规则：

- `PASS` 或确定性 `FAIL` 都产生 `FINAL` 分数。失败场景仍能看到部分完成度和具体失分项。
- `NEEDS_SEMANTIC_REVIEW` 先产生 `PROVISIONAL` 分数和待定的语义维度；复核后重算为 `FINAL`。
- `ERROR` 不伪造零分，输出 `benchmark_score=null`、`score_status=UNAVAILABLE`。零分表示完整测评后确认所有计分项均未完成，和工具失败含义不同。
- Critical Violation 既导致 FAIL，也在“契约与安全”维度扣分；Oracle 或预期 Runtime 结果失败在“结果正确性”维度扣分。门禁失败不能只改变标签而不影响分数。
- 批次比较按 `PASS rate`、`ERROR rate`、平均 `benchmark_score` 的顺序报告，不允许只用平均分掩盖失败率。

具体子项权重与扣分表必须在实现前用现有历史 run 校准，并冻结成版本化 scoring policy。改变 policy 必须提升版本，旧分数保留原 policy 版本，禁止静默重算后混在同一比较组。

## 架构

```text
batch-manifest.json
  -> evaluate_batch.py
       -> 获取/校验输入
       -> 解析 replay + 提取证据
       -> Oracle + 违规审计 + 确定性评分
       -> PASS / FAIL / NEEDS_SEMANTIC_REVIEW / ERROR
  -> semantic-queue.json（仅包含待复核 run）
  -> 可选 Reviewer（Codex skill / 其他模型 / 人工）
  -> evaluate_batch.py --resume
  -> scores.json + scores.xlsx
```

单次模式调用同一 CLI，只使用包含一个 run 的 manifest。`score_run.py` 与 evaluation CLI 的核心逻辑提取成共享库，避免命令之间互相调用或形成第二套评分实现。

## 批次清单

清单是显式 JSON，不从目录名猜测场景 ID：

```json
{
  "schema_version": "1.0",
  "scores_file": "D:/bitexcel/SheetPilot/tests/agent_contract/results/scores.xlsx",
  "runs": [
    {
      "scenario_key": "M3_marketing_roi",
      "replay_file": "D:/evidence/M3/replay.raw.json",
      "output_file": "D:/evidence/M3/output.xlsx",
      "tested_at": "2026-08-25T10:00:00+08:00",
      "run_id": "run-abc123"
    }
  ]
}
```

`scenario_key` 必须精确匹配 scenario 文件名（不含 `.json`），例如 `M3_marketing_roi`。scenario JSON 内的短 `id` 仅用于展示，不能作为关联键：当前仓库存在多个 `M3`、`H2`、`S2` 等重复短 ID。路径经解析后必须位于用户指定的证据根目录。重复 `scenario_key + run_id` 在准备阶段直接报错，不覆盖已有证据。

`output_file`、scenario 和 replay 中 Task Request 的文件路径必须交叉校验。存在多个候选或哈希不一致时进入 ERROR，不按目录名或“最新文件”猜测。

## 场景预检

批量测评前先验证整个 scenario registry。每个场景必须声明一种可执行判定策略：

```json
{
  "scenario_key": "M3_marketing_roi",
  "evaluation_mode": "deterministic_request",
  "expected_request": {},
  "oracle": {"kind": "summarize_table_v1"},
  "semantic_review_required": false,
  "scoring_policy": "benchmark-v1"
}
```

允许的 `evaluation_mode`：

- `deterministic_request`：精确或规范化比较 filters、dimensions、metrics、sort、source、output 和 Acceptance。
- `allowed_requests`：多个业务等价 Request 均可接受，逐个规范化匹配。
- `correct_stop`：验证状态、无输出、报告内容和禁止行为。
- `semantic`：需要判断澄清、能力边界、业务含义或开放式质量。

预检还要确认 scenario key 唯一、数据文件存在、prompt 与数据路径一致、Oracle 类型已实现、expected outcome 与 evaluation mode 相容。目前 `oracle_params.method` 中存在 `manual_verification`、`capability_boundary`、`two_pass_calculation` 等方法，而现有 `evaluate_summarize_table` 并未消费这些配置；在对应 adapter 实现前，它们必须进入 Semantic lane 或配置错误，不能落入通用 Oracle。

当前 31 个场景先以 `evaluation_mode=semantic` 保守启用，确保 Prompt 与 workbook 可以真实执行。后续从 Prompt 中的标准 Task Request 迁移 `expected_request`，逐项通过已知 run 验证后再切换到 deterministic；不能因文档中存在示例 JSON 就自动宣告可确定性评分。

## Fast Lane

新增仓库级入口 `tests/agent_contract/evaluation/evaluate_batch.py`。它复用稳定的 replay parser 与现有 evaluator，不从 skill 目录导入含连字符的路径，也不复制解析逻辑。

每个 run 生成：

- `replay.raw.json`：原样保存并记录 SHA-256。
- `replay.essential.json` 与 `replay.compact.json`。
- `review-packet.json`：只包含 prompt、命令、所有 Task Request、最新 task-status、最终报告、输出路径、时间和缺失字段列表。
- `run-bundle.json`：写入确定提取的字段；不需要语义复核的场景直接使用 `semantic_review.status=not_assessed`。
- `score.json`：现有 evaluator 的完整输出。

提取基于 parser 的 normalized steps/timeline，不直接假设原始 replay 的字段名。工具运行后使用 run-bundle JSON Schema 校验草稿，并输出逐项准备报告。

Oracle 结果只写入 `oracle_result`。Oracle 异常记录为 ERROR，不能降级成空结果继续评分。

Fast lane 的终态：

- `PASS`：所有 gate 通过，输出 `FINAL` 分数。
- `FAIL`：有确定性证据证明 gate 失败，仍输出包含失分明细的 `FINAL` 分数。
- `NEEDS_SEMANTIC_REVIEW`：场景要求语义复核，或证据提取存在明确歧义，输出 `PROVISIONAL` 分数。
- `ERROR`：输入、解析、Oracle 或工具执行异常，分数为 `UNAVAILABLE`。

只有通过场景预检的 run 才进入以上状态机。场景配置问题单列为 `SCENARIO_CONFIG_ERROR`，不计入 Agent 的 ERROR rate，避免把测试集缺陷归责给被测 Agent。

## Semantic Lane

CLI 将所有待复核项合并为一个 `semantic-queue.json`。Reviewer 一次读取队列，逐项返回结构化 `semantic-results.json`；默认只读 review packet，证据不足时才按 `step_id` 打开 compact 视图或工作簿。

Reviewer 负责：

- 确认证据提取完整性，补充有证据支持的 observations。
- 比较 prompt、Task Request、task-status、最终报告和工作簿。
- 写入独立 `semantic_review`，不得采用执行 Agent 的自评替代。
- 输出 `accepted`、`rejected` 或 `not_assessed` 及证据理由。

`evaluate_batch.py --resume semantic-results.json` 合并结果、重新运行现有 evaluator，并完成归档。Reviewer 不直接实现评分，也不直接写 Excel。

## Skill 的定位

两个 skill 保留给以下交互场景：

- 用户只给了分享链接，需要浏览器取回原始 replay。
- Semantic lane 需要 Codex 做独立复核。
- 用户要深入解释某个 FAIL 或比较多个版本。

日常批量回归直接运行 CLI，不触发 skill。skill 调用 CLI，而不是维护自己的 bundle 构造和评分步骤。

Excel 收集所有 score 后只加载一次。写入前创建临时副本，全部写入成功后原子替换目标文件，避免半批次损坏历史记录。

## 性能策略

- 原始 replay 只解析一次；两个 skill 默认读取 review packet 或 essential 视图。
- Oracle 和 replay 解析按 run 并行；语义队列一次提交，只包含必要字段。
- Excel 只加载和保存一次。
- 基于 replay SHA-256、scenario SHA-256、output SHA-256 和工具版本形成缓存键；任一输入变化即失效。
- 确定性产物按输入哈希缓存。语义结果必须绑定 review packet SHA-256；packet 未变化时可以复用，变化后强制失效。

## 测试与验收

实现顺序遵循 tracer-bullet：先用一个真实成功 run 打通完整链路，再扩展批量。

必须覆盖：

1. 单 run 端到端：raw replay 到 Excel 行。
2. 单次与批量等价：同一 run 的 bundle 和 score 关键字段一致。
3. 真实 BitAgent snapshot 格式及普通导出格式。
4. 成功、正确停止、Oracle 失败、缺少 final report、命令轨迹不完整。
5. 重复 ID、非法路径、缺失文件和现有归档冲突。
6. 批次中 PASS、FAIL、ERROR 混合时继续处理且退出码正确。
7. Excel 写入失败时原文件不变。
8. FAIL 仍有 FINAL 分数，ERROR 没有伪造的零分，待语义复核分数标记为 PROVISIONAL。
9. 每个门禁失败都映射到明确计分项；同一输入和 scoring policy 得到相同分数。
10. 聚合报告同时展示通过率、错误率和平均分，不能只展示一个平均值。
11. 重复短 scenario ID 不会串场；manifest 使用唯一 `scenario_key`。
12. 分享页 HTML、401、登录过期和不完整 snapshot 被识别为 acquisition ERROR。
13. Agent 提交了错误但可执行的 Task Request 时，通用 Oracle 即使通过，prompt-contract gate 仍失败。
14. `manual_verification`、`capability_boundary`、`two_pass_calculation` 不会误走通用 Oracle。
15. scenario 配置错误与 Agent 执行错误分开统计。

性能基准固定使用 1、5、31 个 run，分别记录准备、Oracle、Review、Scorer 和 Excel 归档耗时。优化验收以与原流程的实测对比为准，同时要求评分结果零差异。

## 实施顺序

1. 定义并实现 scenario registry 预检，修正重复 ID、缺失判定策略和未实现 Oracle 类型。
2. 定义 manifest、review packet、semantic queue、bundle 和评分输出的 JSON Schema。
3. 用历史 run 校准并冻结 `benchmark_score` policy v1。
4. 将 replay parser 移到可导入的稳定 evaluation 模块，并补齐两种 replay fixture。
5. 实现单 run Fast lane，使用真实 run 打通 replay 到 score。
6. 扩展为多 run、并行、错误隔离和确定性缓存。
7. 实现 Semantic lane 的队列与 resume 协议。
8. 实现单次 Excel 批量归档和原子写入。
9. 实现并验证本地 replay 输入；再实现复用登录会话的 acquisition adapter。
10. 最后更新两个 skill，使其成为 CLI 的轻量适配层。
11. 用 1/5/31 run 基准测量采集、评分和总耗时，确认正确性与实际加速比。
