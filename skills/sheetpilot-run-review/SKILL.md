---
name: sheetpilot-run-review
description: Parse and prepare SheetPilot Agent runs for black-box evaluation. Accepts a single replay/link or a batch list of links. Use when given an Agent replay, transcript JSON, exported run log, share URL, or completed SheetPilot test result and asked to inspect Skill usage, execution efficiency, violations, Runtime evidence, or prepare runs for scoring and Excel archival.
---

# SheetPilot Run Review

Turn one or more completed Agent runs into review-ready evidence. Do not score from the final answer alone.

## Single-Run Mode

Given one replay file, export path, or BitAgent share URL, follow the full pipeline below once.

## Batch Mode

Given a list of BitAgent share URLs (or a file containing them), process **each URL in sequence within this session** using the same pipeline. For every run:
- announce which scenario you are processing (`[N/Total] Scenario-ID`)
- complete steps 1–7 in full before moving to the next
- after all runs finish, print a one-line summary table: Scenario | Result | Score | Violations

**Splitting work across sessions**: for large batches, split the list and run each sub-list in a separate parallel Codex session to reduce wall-clock time.

Example batch input accepted:
```
批量评分以下场景：
M1: https://bitagent.ninetechone.com/web/share/abc...
M2: https://bitagent.ninetechone.com/web/share/def...
M3: https://bitagent.ninetechone.com/web/share/ghi...
scores目标文件: D:\bitexcel\SheetPilot\tests\agent_contract\results\scores.xlsx
```

---

## Pipeline (per run)

1. **Fetch replay**: If given a BitAgent share URL, browse the URL and capture the raw replay JSON from the page response (`data.snapshot_data` field if present). Save it as `replay.raw.json`. If given a local file, copy it.

2. **Create review directory**: Name it `<scenario-id>__<skill-version>__<YYYYMMDDTHHMMSS+0800>__<run-id>` using the execution-time `tested_at`. Keep artifact filenames business-readable inside it.

3. **Parse the raw replay** into both views:

```powershell
python ${SKILL_DIR}\scripts\parse_agent_replay.py replay.raw.json --format essential -o <review-dir>\replay.essential.json
python ${SKILL_DIR}\scripts\parse_agent_replay.py replay.raw.json --format compact  -o <review-dir>\replay.compact.json
```

4. **Read `replay.essential.json` only** — do not read the full raw replay or compact view unless a specific `step_id` is missing. The essential view is the compressed evidence; use it for all judgements.
   Use `stats.total_duration_ms` as end-to-end wall-clock time.

5. **Collect evidence**: original prompt, scenario ID, all Task Requests found in the timeline, latest `task-status`, Runtime Evidence, input hash before execution, final workbook path, final report, and independent Oracle result (run Oracle script if output file exists).

6. **Record versions**: `tested_at`, `run_id`, Runtime/package version, Git commit, SHA-256 of the exact `SKILL.md` used by the execution Agent.

7. **Write `run-bundle.json`** using `references/run-bundle-schema.md` from the scorer Skill. Copy generated `stats` to `replay_stats`; leave unavailable timing null rather than zero.

8. **Invoke `sheetpilot-run-scorer`** with the review directory and score workbook path.

---

## Evidence Rules

- Preserve `replay.raw.json`. Never rewrite it after saving.
- Record every tool call, command, duration, status, input, and result that is available in the essential view.
- Do not infer zero violations from a missing replay segment.
- Treat reading packaged `SKILL.md` as allowed. Flag searches for the system command, wrapper source, Runtime source, internal schemas, legacy CLI, direct workbook writes, and Task/Attempt directory management.
- Keep Runtime PASS, Oracle PASS, and semantic assessment separate.
- The execution Agent's self-assessment is evidence, not an independent semantic review.

---

## Output (per run)

```text
<review-dir>/
  replay.raw.json
  replay.essential.json
  replay.compact.json
  run-bundle.json
  oracle-result.json
  output.xlsx          (if delivered)
```

In batch mode, return the full review directory list and a summary table. Report evidence completeness problems per run; do not silently fill missing fields.
