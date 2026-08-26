# SheetPilot Agent 测评与评分工具

## 批量快速测评

`evaluate_batch.py` 是批量 Fast lane 入口。它接收显式 manifest，按
`scenario_key + run_id` 关联已准备好的 `run-bundle.json`，不会根据目录名猜测
场景，也不会因单个 run 出错而中断整批。

Manifest 最小格式：

```json
{
  "schema_version": "1.0",
  "scenario_root": "tests/agent_contract/scenarios",
  "workers": 1,
  "runs": [
    {
      "scenario_key": "H1",
      "run_id": "run-001",
      "bundle_file": "reviews/H1/run-bundle.json",
      "replay_file": "reviews/H1/replay.raw.json"
    }
  ]
}
```

设置 `scenario_root` 后，`scenario_file` 会按完整 `scenario_key` 自动解析为
`<scenario_root>/<scenario_key>.json`，适合一次提交整个数据集；场景必须存在且为
`active`。

`workers` 控制独立 run 的并行数。默认值为 `1`；证据量较大时可以设置为 `4` 或
其他合适值。每个 worker 只写自己的 run 目录，主线程统一写批次 JSON 和 Excel，
输出顺序仍与 manifest 一致。

也可以从场景 registry 和证据目录生成清单：

```powershell
python -m tests.agent_contract.evaluation.build_manifest `
  --scenario-root tests/agent_contract/scenarios `
  --evidence-root tests/agent_contract/evidence `
  -o tests/agent_contract/manifest.json
```

证据目录约定为 `<scenario_key>/<run_id>/run-bundle.json` 或
`<scenario_key>/<run_id>/replay.raw.json`。缺少场景或证据时生成器返回非零状态，
但仍保存清单和错误列表，便于修复后重新生成。

执行：

```powershell
$env:PYTHONPATH = "src;."
python -m tests.agent_contract.evaluation.evaluate_batch manifest.json -o results
```

输出包含 `batch-summary.json`、`scores.json`、`semantic-queue.json` 和每个 run 的
`score.json`。`benchmark_score` 为 0-100 分；`ERROR` 的分数为 `null`，不会伪造
零分。每次批量执行还会一次性生成 `scores.xlsx`，写入失败不会留下半成品文件。
如果目标文件已经存在，新批次会原子追加到 `BatchScores` 工作表，不会覆盖历史记录；
表头不兼容时归档失败并返回非零退出码。

Manifest 可以仅提供 `replay_file`。当前自动准备只接受 replay 中明确存在的
`run_bundle`，或明确存在的 `task_request`、`task_status`、`final_report` 等结构化
证据；同时会调用仓库内的 replay parser 生成 `replay.raw.json`、
`replay.essential.json` 和 `replay.compact.json`。不会从自然语言命令输出中猜测
字段。证据不完整时，该 run 会生成可追溯的 `ERROR score.json`，其他 run 继续执行。

## 从分享链接采集

如果不想分别运行多个 Python 模块，可以使用一键入口：

```powershell
tests/agent_contract/install_share_batch.cmd
tests/agent_contract/run_share_batch.cmd `
  --links tests/agent_contract/share_links.txt `
  --scenario-root tests/agent_contract/scenarios `
  --evidence-root tests/agent_contract/evidence `
  --output-dir tests/agent_contract/results/share-batch `
  --user-data-dir tests/agent_contract/browser-profile `
  --executable-path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --workers 4
```

也可以直接双击 `run_share_batch.cmd`，但建议先传入上述参数。复制
`share_links.example.txt` 为 `share_links.txt` 后填写链接。每行必须包含完整
场景 key：`scenario_key<TAB>url`，或 `scenario_key<TAB>run_id<TAB>url`；纯 URL
会被拒绝，因为 URL 本身无法可靠推断测试场景。

分享链接需要登录态，先安装浏览器自动化依赖：

```powershell
$py = "C:\Users\nine\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py -m pip install playwright
```

使用独立浏览器 profile 采集。第一次运行会打开 Edge，完成 BitAgent 登录；之后
复用同一个 profile：

```powershell
& $py -m tests.agent_contract.evaluation.acquire_share `
  "https://bitagent.ninetechone.com/web/share/06608c00526f4360801b266252d54ee6?template_version=v3&locale=zh-CN" `
  --scenario-key S2_single_dim_metric `
  --run-id run-001 `
  --evidence-root tests/agent_contract/evidence `
  --user-data-dir tests/agent_contract/browser-profile `
  --executable-path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

成功后会生成：

```text
tests/agent_contract/evidence/S2_single_dim_metric/run-001/replay.raw.json
tests/agent_contract/evidence/S2_single_dim_metric/run-001/acquisition.json
```

采集器只接受包含有效 `snapshot_data` 的分享接口 JSON。HTML、401、登录过期或
不完整 snapshot 会记录为 acquisition `ERROR`，不会进入评分流程。

退出码约定：`0` 表示批次完成且归档成功；`2` 表示场景配置错误、至少一个
run 为 `ERROR`，或 Excel 归档失败。即使归档失败，`scores.json` 和
`batch-summary.json` 仍会保留。

语义复核完成后可重算：

```powershell
python -m tests.agent_contract.evaluation.evaluate_batch manifest.json -o results --resume semantic-results.json
```

默认启用确定性缓存，缓存键包含 replay、scenario、输出文件和评分策略版本。
输入或策略变化会自动失效；需要强制重算时使用：

```powershell
python -m tests.agent_contract.evaluation.evaluate_batch manifest.json -o results --no-cache
```

性能验收可以测量 1、5、31 个 run（实际不足时使用可用数量）：

```powershell
python -m tests.agent_contract.evaluation.benchmark_batch manifest.json -o benchmark.json
```

报告同时记录冷启动耗时、缓存命中耗时、缓存加速比和两次评分结果是否一致；
不在实现前承诺固定倍数。

该工具评价一次完整 Agent run，而不是只检查最终回复。产品入口参考 `bitppt-share-review` 与 `bitppt-ppt-only-scorer`，分为两个 Skill：

- `skills/sheetpilot-run-review`：解析原始 Replay，生成 `replay.essential.json` 与 `replay.compact.json`，准备 `run-bundle.json`。
- `skills/sheetpilot-run-scorer`：执行独立语义复核、确定性评分，并将多个 Skill/版本结果追加到 Excel。

推荐流程：

```text
raw replay
  -> replay.essential.json + replay.compact.json
  -> run-bundle.json + oracle-result.json
  -> independent scorer
  -> score.json
  -> SheetPilotReviews Excel history
```

评分分为两层：

1. 硬门禁：任务结果、Acceptance 完整性、Critical Violation、输入完整性和可选的独立语义复核。
2. 质量分：接口合规 30、执行效率 20、恢复行为 15、证据与报告 20、输出可用性 15。

硬门禁失败时 `task_result=FAIL`、`quality_score=null`；`diagnostic_score` 仅用于定位改进空间，不能当作通过分。

## Run Bundle

```json
{
  "scenario": {
    "id": "M1-city-summary",
    "expected_outcome": "success",
    "cli_call_limit": 3,
    "semantic_review_required": true
  },
  "task_request": {},
  "task_status": {},
  "oracle_result": {},
  "semantic_review": {
    "status": "accepted",
    "reviewer": "independent-agent",
    "rationale": "请求中的过滤、分组和指标忠实覆盖用户要求。"
  },
  "final_report": {},
  "commands": [
    {"command": "python ... task-types", "elapsed_ms": 800}
  ],
  "observations": {
    "source_access_attempts": 0,
    "legacy_cli_calls": 0,
    "manual_workbook_writes": 0,
    "run_dir_operations": 0,
    "agent_authored_internal_plans": 0,
    "unauthorized_amendments": 0,
    "acceptance_reductions": 0,
    "false_success_claims": 0
  }
}
```

`semantic_review` 应由只读 Reviewer Agent 或人工给出。执行 Agent 可以提供自检意见，但不能替代独立复核，也不能覆盖 Runtime/Oracle 失败。

## 使用方式

从仓库根目录运行：

```powershell
python skills\sheetpilot-run-review\scripts\parse_agent_replay.py replay.json --format essential -o replay.essential.json
python skills\sheetpilot-run-review\scripts\parse_agent_replay.py replay.json --format compact -o replay.compact.json
python skills\sheetpilot-run-scorer\scripts\score_run.py run-bundle.json -o score.json
python skills\sheetpilot-run-scorer\scripts\append_score_excel.py scores.xlsx --score-json score.json

python -m tests.agent_contract.evaluation.cli oracle --request request.json --input-hash-before <sha256> --output oracle-result.json
python -m tests.agent_contract.evaluation.cli evaluate --bundle run-bundle.json --output evaluation.json
python -m tests.agent_contract.evaluation.cli archive --bundle run-bundle.json --results-root tests\agent_contract\results --run-id run-01
```

归档目录名为 `<scenario-id>__<skill-version>__<YYYYMMDDTHHMMSS+0800>__<run-id>`。时间优先使用 `tested_at` 并统一转换为北京时间；`skill-version` 缺失时使用 `unversioned`。目录承载版本和时间标识，目录内 Excel 保留有意义的业务文件名。归档前必须先结束 Agent run，且不要把该目录暴露给下一次 Fresh Agent。

命令规则检测只能覆盖轨迹中已记录的行为。Harness 仍须完整记录 Agent 工具调用；缺失命令轨迹或最终报告会直接触发 `evidence_complete=false`，不能被解释为“零违规”。
