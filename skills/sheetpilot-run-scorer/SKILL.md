---
name: sheetpilot-run-scorer
description: Independently score and archive a prepared SheetPilot Agent run. Use when a review directory contains replay evidence, Task Request, task-status, Runtime evidence, an Excel output, or Oracle result and the user wants task-completion gates, Skill usability and efficiency scoring, semantic review, failure classification, version comparison, or an Excel score history.
---

# SheetPilot Run Scorer

Score only prepared runs. Read `replay.essential.json` first and use `replay.compact.json` only for missing command inputs or results.

## Required Inputs

Read `<review-dir>\run-bundle.json`, the original user prompt, final workbook, and Oracle result. Read the source workbook when semantic meaning or output preservation cannot otherwise be established. Require the execution-time `tested_at`, `run_id`, `runtime_version`, `git_commit`, and `skill_sha256` for version comparisons; do not hash a Skill after it has already been modified.

Use [references/run-bundle-schema.md](references/run-bundle-schema.md) for the bundle and score shapes.
Use Replay wall-clock duration for end-to-end efficiency comparisons. Treat tool-duration sums, Agent-response estimates, and Runtime duration as diagnostics with distinct meanings; never substitute a missing duration with zero.

## Independent Review

1. Compare the prompt with every filter, dimension, metric, count mode, sort, source, output Sheet, and Acceptance component in the Task Request.
2. Inspect the final workbook read-only. Never repair it.
3. Set `semantic_review.status` to `accepted`, `rejected`, or `not_assessed`; bind every rejection to prompt and workbook/request evidence.
4. Do not accept the execution Agent's self-rating as independent review.
5. Run the deterministic scorer. Runtime PASS cannot override Oracle or semantic failure.

```powershell
python ${SKILL_DIR}\scripts\score_run.py <review-dir>\run-bundle.json -o <review-dir>\score.json
```

## Hard Gate

Require expected outcome, complete Acceptance, zero Critical Violations, unchanged input, complete evidence, Oracle PASS for successful tasks, and semantic acceptance when the scenario requires it. A failed gate produces `quality_score=null`; retain `diagnostic_score` only for diagnosis.

## Excel Archive

Check for an existing Prompt group before writing:

```powershell
python ${SKILL_DIR}\scripts\append_score_excel.py <scores.xlsx> --check-prompt "<distinctive prompt keyword>"
python ${SKILL_DIR}\scripts\append_score_excel.py <scores.xlsx> --score-json <review-dir>\score.json --connect <row>
```

Without a match, omit `--connect`. Use `--append-only` only when the workbook must already exist. The script recomputes totals, inserts beside matching Prompt versions, redraws group borders, and highlights the best metric cells inside each multi-run group.

Return `score.json`, Excel row, task result, quality score, critical violations, failure class, and archive card.
