---
name: sheetpilot-run-review
description: Parse and prepare a SheetPilot Agent run for black-box evaluation. Use when given an Agent replay, transcript JSON, exported run log, or completed SheetPilot test result and asked to inspect Skill usage, execution efficiency, violations, Runtime evidence, or prepare the run for scoring and Excel archival.
---

# SheetPilot Run Review

Turn one completed Agent run into review-ready evidence. Do not score from the final answer alone.

## Pipeline

1. Create a new immutable review directory outside the next Agent's workspace. Name it `<scenario-id>__<skill-version>__<YYYYMMDDTHHMMSS+0800>__<run-id>` using the execution-time `tested_at`; keep artifact filenames business-readable inside it.
2. Parse the raw replay into both views:

```powershell
python ${SKILL_DIR}\scripts\parse_agent_replay.py replay.json --format essential -o <review-dir>\replay.essential.json
python ${SKILL_DIR}\scripts\parse_agent_replay.py replay.json --format compact -o <review-dir>\replay.compact.json
```

3. Read `replay.essential.json` first. Open the compact view only when a block's `step_id` needs full inputs or outputs.
   Use `stats.total_duration_ms` as end-to-end wall-clock time. Keep tool, Agent-response, and Runtime durations as separate diagnostics.
4. Collect the original prompt, scenario, all Task Requests, latest `task-status`, Runtime Evidence, input hash before execution, final workbook, final report, and independent Oracle result.
5. Before modifying or reinstalling the execution Skill, record `tested_at`, `run_id`, Runtime/package version, Git commit, and SHA-256 of the exact `SKILL.md` used by the execution Agent.
6. Write `<review-dir>\run-bundle.json` using `references/run-bundle-schema.md` from the scorer Skill. Copy generated `stats` to `replay_stats`; leave unavailable timing null rather than zero.
7. Invoke `sheetpilot-run-scorer` with the review directory and score workbook path.

## Evidence Rules

- Preserve the raw replay. Never rewrite it after parsing.
- Record every tool call, command, duration, status, input, and result that is available.
- Do not infer zero violations from a missing replay segment.
- Treat reading packaged `SKILL.md` as allowed. Flag searches for the system command, wrapper source, Runtime source, internal schemas, legacy CLI, direct workbook writes, and Task/Attempt directory management.
- Keep Runtime PASS, Oracle PASS, and semantic assessment separate.
- The execution Agent's self-assessment is evidence, not an independent semantic review.

## Output

Prepare:

```text
<review-dir>/
  replay.raw.json
  replay.essential.json
  replay.compact.json
  run-bundle.json
  oracle-result.json
  output.xlsx
```

Return the review directory and evidence completeness problems. Do not silently fill missing fields.
