# Project Structure

## Product Surface

| Area | Canonical path | Responsibility |
|---|---|---|
| Agent CLI | `src/sheetpilot/agent_cli.py` | Only `task-types`, `task-run`, `task-status` |
| Task Runtime | `src/sheetpilot/task_api/` | Contract, binding, deterministic compile, Task/Attempt, validation and publication |
| Execution base | `src/sheetpilot/engines/`, `src/sheetpilot/workbook/` | Workbook IO and table operations used by Task Runtime |
| Execution Skill | `skills/sheetpilot-excel-agent/` | Agent workflow and packaged wrapper |
| Review Skill | `skills/sheetpilot-run-review/` | Replay evidence preparation |
| Scorer Skill | `skills/sheetpilot-run-scorer/` | Semantic review, deterministic score and Excel archive |

## Tests

| Layer | Path | Meaning |
|---|---|---|
| Unit | `tests/unit/` | Legacy/shared execution primitives |
| Integration | `tests/integration/` | Public CLI, Skill package and Task API |
| Agent contract | `tests/agent_contract/` | Fresh-Agent behavior, Oracle and scoring |
| Fixtures | `tests/fixtures/` | Stable test workbooks |

Black-box results and review workbooks belong under `tests/agent_contract/results` and `tests/agent_contract/reviews`. They are evidence, not Runtime source.

## Legacy And Archive

- `archive/legacy-runtime/schemas`: schemas used only by the old Planner/MVP CLI.
- `archive/legacy-test-artifacts`: old one-off generation and workbook scripts.
- `archive/local-runs`: developer run outputs; never an Agent-facing state location.
- `archive/experiments`: unrelated experiments retained for reference.
- `archive/duplicates`: superseded copies retained temporarily during migration.
- `docs/archive/legacy-mvp`: historical design and implementation handoff documents.

Do not add current public contracts to `archive`. Do not let the Agent-facing wrapper discover or load legacy schemas, old plans, test examples or local run directories.
