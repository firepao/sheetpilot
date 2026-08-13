# Run Bundle And Score Contract

## Run Bundle

Required for a successful scenario: `scenario`, `prompt`, `task_request`, `task_status`, `oracle_result`, `final_report`, `commands`, and `semantic_review`.

```json
{
  "scenario": {"id": "M1", "expected_outcome": "success", "cli_call_limit": 3, "semantic_review_required": true},
  "prompt": "original user prompt",
  "platform": "Codex",
  "model": "model name",
  "run_id": "S1-v4-run-01",
  "tested_at": "2026-08-11T16:20:00+08:00",
  "skill_version": "v4-task-api",
  "runtime_version": "0.1.0",
  "git_commit": "full git commit sha",
  "skill_sha256": "SHA-256 of the exact SKILL.md used by the execution Agent",
  "task_request": {},
  "task_status": {},
  "oracle_result": {},
  "semantic_review": {"status": "accepted", "reviewer": "independent-agent", "rationale": "..."},
  "final_report": {},
  "commands": [{"command": "... task-types", "elapsed_ms": 800}],
  "replay_stats": {
    "source": "replay_timestamps",
    "complete": true,
    "total_duration_ms": 74000,
    "step_count": 3,
    "tool_duration_ms": 12000,
    "agent_response_duration_ms": 18000,
    "step_time": {"avg_ms": 4000, "p95_ms": 7000}
  },
  "runtime_timing": {"duration_ms": 5200, "source": "runtime_evidence"},
  "observations": {}
}
```

`score_run.py` adds `evaluated_at`, a generated `run_id` when absent, and `bundle_sha256`. Excel uses `skill_version` as the display label; if absent it deterministically falls back to Git and Skill hash prefixes. Record the exact execution-time Skill hash, not the later modified file.

Copy `replay_stats` from generated `replay.essential.json.stats`; do not hand-author timing values. `total_duration_ms` is wall-clock time from the earliest Replay event to the latest completion event. Tool duration is a diagnostic sum and may exceed wall-clock time when calls overlap. Record `runtime_timing` only when Runtime evidence exposes a measured duration. Missing timing remains null and incomplete; it is never converted to zero.

Correct-stop scenarios use `expected_outcome=correct_stop`, list `allowed_states`, and set `output_exists` from observed filesystem evidence.

## Score

The deterministic output contains `task_result`, nullable `quality_score`, `diagnostic_score`, gates, critical violations, raw metrics, and five score dimensions. Add reviewer-authored `failure_class` and evidence-grounded `review_notes` before Excel archival when a run fails.

Allowed failure classes: `PRODUCT_CONTRACT_GAP`, `RUNTIME_BUG`, `SKILL_WORKFLOW_DEFECT`, `AGENT_REASONING_FAILURE`, `HARNESS_FAILURE`, `ORACLE_FAILURE`.
