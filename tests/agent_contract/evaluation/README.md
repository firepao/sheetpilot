# SheetPilot Agent 测评与评分工具

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
