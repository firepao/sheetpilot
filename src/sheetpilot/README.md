# Runtime Module Map

## Current Agent Runtime

```text
agent_cli.py
  -> task_api/contract.py
  -> task_api/compiler.py
  -> task_api/runtime.py
       -> engines/
       -> workbook/tables.py
       -> workspace.py
```

This is the only Agent-facing execution path. `agent_cli.py` registers only `task-types`, `task-run`, and `task-status`.

## Shared Execution Base

- `engines/`: workbook engine abstraction and openpyxl implementation.
- `workbook/`: in-memory table operations reused by the deterministic compiler.
- `workspace.py`: file hashing and shared workspace utilities.

These modules are implementation dependencies, not Agent contracts.

## Legacy Compatibility

The following modules belong to the older Planner/MVP architecture and must not be imported or inspected by an execution Agent:

```text
cli.py
mvp.py
planning/
recipes/
capabilities/
composites/
executor/
inspector/
runtime/
validators/
models.py
```

Their historical schemas are stored under `archive/legacy-runtime/schemas`. Keep legacy compatibility changes separate from `task_api` changes.
