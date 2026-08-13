# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The repository root is a handoff/archive area (archived Univer/Excel evaluation bundles, `交接/`, zips). Do **not** edit those. The active, maintained project lives in **`SheetPilot/`** — a deterministic Excel execution Runtime whose public product surface is a business-level **Task API**. Work almost exclusively inside `SheetPilot/`.

## Core product model (read `CONTEXT.md` first)

The Agent-facing interface is deliberately a black box. The Agent submits a **Task Request** (business-level: source, filters, dimensions, metrics, sort, output, acceptance) and the **Runtime** owns field binding, internal plan compilation, Task/Attempt directories, execution, validation and publication. Key invariants:

- Agent never supplies sheet/column coordinates, plan/DAG, run dirs, or attempts. The Runtime binds logical fields to physical columns via `BindingCandidate`s.
- **Acceptance Contract** is frozen on first receive and cannot be silently reduced (no shrinking `required_*`). Attempts are immutable; a failed attempt yields a new `Attempt`, never a rewritten one.
- **Runtime Pass** (all business + system acceptance + evidence + publication passed) is distinct from the Agent's semantic judgment about whether the business wording was right — these must be reported separately.
- Delivery is valid only when `task-status` returns `state=RUNTIME_PASS` **and** `artifact_integrity=MATCHED` **and** `delivery_valid=true` (the output file hash must still match what was validated).

The black-box protocol and the error/binding/recovery machine behavior are specified under `docs/current/*.md` (numbered prototypes). The three entry points are `agent_cli.py` (`task-types`, `task-run`, `task-status`); the old Planner/MVP CLI (`cli.py`, `mvp.py`, `planning/`, `recipes/`, `capabilities/`) is retained only for compatibility tests and is **not** part of the product interface.

## Build, test, run

Python 3.11+ and `openpyxl>=3.1`. From `SheetPilot/`:

```powershell
python -m pip install -e .
$env:PYTHONPATH = "src;."
python -m unittest discover -s tests -p "test_*.py" -v
```

Test layers (from `PROJECT_STRUCTURE.md`):
- `tests/unit/` — shared execution primitives.
- `tests/integration/` — public CLI, Skill package, Task API.
- `tests/agent_contract/` — **fresh-Agent black-box** tests: run a real Agent against the public Skill/CLI, then score against an **independent Oracle** (`evaluation/oracle.py` recomputes the result from the `.xlsx` without importing SheetPilot) and deterministic gates (`evaluation/evaluator.py`).

Run a single test file: `python -m unittest tests.integration.test_task_api -v`.

## Agent black-box evaluation (the review/score pipeline)

The skills drive scoring — these are not product runtime:

- `skills/sheetpilot-excel-agent/` — the packaged Skill the executing Agent is expected to use. It enforces a **stop-gate** (on `CONFIGURATION_REQUIRED`/`INTERNAL_ERROR`/`HUMAN_ACTION_REQUIRED` the run ends immediately), forbids openpyxl/pandas/COM/LibreOffice writes, and requires the first call to be `task-types`.
- `skills/sheetpilot-run-review/` — turns one Agent replay into review evidence: parses raw replay → essential + compact views, builds a `run-bundle.json`.
- `skills/sheetpilot-run-scorer/` — the deterministic scorer. It audits the Agent command stream for violations (`source_access_attempts`, `legacy_cli_calls`, `manual_workbook_writes`, `run_dir_operations`, `acceptance_reductions`, …), computes gates + a quality score, and archives the Excel result.

In `tests/agent_contract/evaluation/evaluator.py`: `ALLOWED_COMMANDS = {"task-types", "task-run", "task-status"}`; `LEGACY_COMMANDS = {"mvp-run", "mvp-validate", "plan", "compile", "execute", "recipes", "capabilities"}`. A PASS requires `critical_violations` total zero and oracle `passed`. Evidence directories live under `tests/agent_contract/results/` and `reviews/` — they are evidence, not source.

## Contract validators

`src/sheetpilot/task_api/contract.py` is the source of truth for the request schema and validation: `FILTER_OPERATORS = {eq,ne,gt,gte,lt,lte,in}`, metric functions `{sum, average, count}` with `count.rows`/`count.non_empty` modes, `field_binding: unique_exact_header_match_with_semantic_candidates`, output `create_new_sheet_and_new_file`. `MINIMAL_EXAMPLE` there is the canonical shape to copy when constructing requests. `compiler.py` turns a validated request + binding snapshot into a deterministic `internal-plan` (byte-identical for identical inputs/version — used as evidence via `plan_hash`).

Field binding in `runtime.py` auto-binds **only** a unique exact (normalized) header match; otherwise it surfaces `BindingCandidate`s — exact and semantic/fuzzy (`_score_header`: exact → substring → character-bigram Dice) — each with `confidence`, `evidence`, and `sample_values`, and returns `NEEDS_BINDING`. A slot with no candidate returns `HUMAN_ACTION_REQUIRED`. The runtime never silently binds a fuzzy match (see `docs/current/16` §6).

## Coded conventions

- 4-space indent; modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`. Schemas/reserved prefixes use `__sp_`.
- Task Request JSON + all state files use UTF-8. Diagnostics are structured (stable code, path, expected/actual), never raw tracebacks.
- Comments explain only non-obvious constraints; don't add boilerplate doc-comments.

## Do / Don't

- Do work inside `SheetPilot/`; treat the root and `交接/` as read-only archives.
- Don't let the Agent-facing wrapper load legacy schemas, old plans, test examples or local run dirs (`archive/`, `docs/archive/`, `tests/agent_contract/results` are not runtime source).
- Don't add current public contracts to `archive/`.
- Don't hardcode API keys/secrets in code, YAML, requests, or commits; prefer env vars. Never commit large run artifacts or paid-API-sensitive outputs.