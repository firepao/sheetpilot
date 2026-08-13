from __future__ import annotations

import copy
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import coordinate_to_tuple

from ..engines import OpenPyxlEngine
from ..workbook.tables import TableData, aggregate, filter_rows, read_table, select_columns, sort_rows
from ..workspace import sha256_file
from .compiler import collect_fields, compile_plan
from .contract import acceptance_snapshot, invalid_response, stable_hash, task_type_manifest, validate_request


def default_state_root() -> Path:
    configured = os.environ.get("SHEETPILOT_STATE_ROOT")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "SheetPilot"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class TaskRuntime:
    def __init__(self, state_root: Path | None = None):
        self.state_root = (state_root or default_state_root()).resolve()
        self.tasks_root = self.state_root / "tasks"

    def task_types(self) -> dict[str, Any]:
        return task_type_manifest()

    def run(self, request: Any) -> dict[str, Any]:
        if isinstance(request, dict) and "task_id" in request:
            return self._amend(request)
        errors = validate_request(request)
        if errors:
            return invalid_response(errors)
        return self._create_and_run(copy.deepcopy(request))

    def status(self, task_id: str) -> dict[str, Any]:
        task_dir = self._task_dir(task_id)
        state_path = task_dir / "current-state.json"
        if not state_path.is_file():
            return self._error("REQUEST_INVALID", "INVALID_REFERENCE", "contract_validation", "Task 不存在。", None, None, None, False, "NONE")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        response = copy.deepcopy(state)
        response.update({"schema_version": "1.0", "task_id": task_id, "acceptance_hash": task["acceptance_hash"]})
        output = Path(task["output_file"])
        expected = state.get("validated_published_sha256")
        if state["state"] == "RUNTIME_PASS":
            current = sha256_file(output) if output.is_file() else None
            response["artifact_integrity"] = "MATCHED" if current == expected else ("MISSING" if current is None else "MODIFIED")
            response["delivery_valid"] = current == expected
            response["current_published_sha256"] = current
        else:
            response.setdefault("artifact_integrity", None); response.setdefault("delivery_valid", False)
        return response

    def _create_and_run(self, request: dict[str, Any]) -> dict[str, Any]:
        self.tasks_root.mkdir(parents=True, exist_ok=True)
        source, output = Path(request["input_file"]).expanduser().resolve(), Path(request["output_file"]).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in {".xlsx", ".xlsm"}:
            return self._error("REQUEST_INVALID", "INPUT_NOT_FOUND", "workbook_inspection", "输入文件不存在或不是受支持的工作簿。", None, None, None, False, "HUMAN_ACTION_REQUIRED")
        if source == output:
            return self._error("REQUEST_INVALID", "INVALID_VALUE", "contract_validation", "输出文件不能覆盖输入文件。", None, None, None, False, "CREATE_NEW_TASK")
        request["input_file"], request["output_file"] = str(source), str(output)
        input_hash = sha256_file(source)
        submission = copy.deepcopy(request); submission.pop("user_request", None)
        submission_hash = stable_hash(submission)
        existing = self._find_submission(submission_hash, input_hash, str(output))
        if existing:
            return self.status(existing)
        if output.exists():
            return self._error("REQUEST_INVALID", "OUTPUT_CONFLICT", "publication", "输出文件已存在。", None, None, None, False, "HUMAN_ACTION_REQUIRED")
        task_id = f"task-{uuid.uuid4().hex[:26]}"
        task_dir = self.tasks_root / task_id
        task_dir.mkdir()
        acceptance = acceptance_snapshot(request); acceptance_hash = stable_hash(acceptance)
        task = {"task_id": task_id, "created_at": _now(), "input_file": str(source), "input_sha256": input_hash, "output_file": str(output), "submission_hash": submission_hash, "acceptance_hash": acceptance_hash}
        _write_json(task_dir / "task.json", task); _write_json(task_dir / "acceptance-snapshot.json", acceptance)
        try:
            binding = self._bind(request, input_hash)
        except Exception as exc:
            response = self._error("EXECUTION_FAILED", "INTERNAL_ERROR", "workbook_inspection", str(exc), task_id, 1, None, False, "HUMAN_ACTION_REQUIRED")
            _write_json(task_dir / "current-state.json", {"state": "FAILED", "terminal": True, "request_revision": 1, "latest_attempt": None, "delivery_valid": False, "error": response["error"]})
            return response
        revision = {"request_revision": 1, "request": request, "bindings": binding, "request_revision_hash": stable_hash(request)}
        _write_json(task_dir / "revisions" / "revision-001.json", revision)
        if binding["unresolved"]:
            state = self._binding_response(task_id, acceptance_hash, binding)
            _write_json(task_dir / "current-state.json", {key: value for key, value in state.items() if key not in {"schema_version", "status", "binding_slots", "binding_candidates", "diagnostics"}} | {"state": "NEEDS_BINDING", "terminal": False})
            return state
        return self._execute(task_dir, task, revision)

    def _bind(self, request: dict[str, Any], input_hash: str) -> dict[str, Any]:
        workbook = load_workbook(request["input_file"], read_only=True, data_only=True)
        try:
            requested_sheet = request["source"].get("sheet")
            if not requested_sheet or requested_sheet not in workbook.sheetnames:
                return {"source": None, "slots": [], "candidates": [], "unresolved": [{"kind": "source", "logical_field": None}]}
            ws = workbook[requested_sheet]; header_row = request["source"].get("header_row", 1)
            if ws.max_column is None or ws.max_row is None:
                ws.calculate_dimension(force=True)
            headers: dict[str, list[dict[str, Any]]] = {}
            for column in range(1, ws.max_column + 1):
                raw = ws.cell(header_row, column).value
                if raw in (None, ""): continue
                header = str(raw); candidate_id = "candidate-" + stable_hash([input_hash, requested_sheet, header_row, column, header])[:8]
                values = [ws.cell(row, column).value for row in range(header_row + 1, min(ws.max_row, header_row + 20) + 1)]
                non_empty = [value for value in values if value not in (None, "")]
                inferred = "number" if non_empty and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_empty) else "text"
                candidate = {"id": candidate_id, "source_id": "source-001", "sheet": requested_sheet, "header_row_start": header_row, "header_row_end": header_row, "column": get_column_letter(column), "header": header, "inferred_type": inferred, "confidence": 1.0, "evidence": ["exact_header_match"]}
                headers.setdefault(header, []).append(candidate)
            slots, candidates, unresolved = [], [], []
            for index, (field, references) in enumerate(collect_fields(request), 1):
                matches = headers.get(field, []); slot_id = f"binding-{index:03d}"
                uses = self._field_uses(request, field); numeric = any(use in {"metric:sum", "metric:average"} for use in uses)
                compatible = [item for item in matches if not numeric or item["inferred_type"] == "number"]
                status = "RESOLVED" if len(compatible) == 1 and len(matches) == 1 else ("AMBIGUOUS" if compatible else "UNRESOLVED")
                resolution = ({"candidate_id": compatible[0]["id"], "sheet": requested_sheet, "header_row": header_row, "column": compatible[0]["column"], "header": compatible[0]["header"]} if status == "RESOLVED" else None)
                slot = {"id": slot_id, "logical_field": field, "references": references, "requirements": {"accepted_types": ["number"] if numeric else ["text", "number", "boolean", "unknown"], "uses": uses}, "status": status, "selected_candidate_id": resolution["candidate_id"] if resolution else None, "candidate_ids": [item["id"] for item in compatible], "resolution": resolution}
                slots.append(slot); candidates.extend(compatible)
                if status != "RESOLVED": unresolved.append(slot)
            return {"source": {"id": "source-001", "sheet": requested_sheet, "header_row": header_row}, "slots": slots, "candidates": candidates, "unresolved": unresolved}
        finally:
            workbook.close()

    def _execute(self, task_dir: Path, task: dict[str, Any], revision: dict[str, Any]) -> dict[str, Any]:
        attempt_id = "attempt-001"; attempt_dir = task_dir / "attempts" / attempt_id; attempt_dir.mkdir(parents=True)
        request, binding = revision["request"], revision["bindings"]
        binding_snapshot = {"source": binding["source"], "slots": binding["slots"]}
        plan, plan_hash = compile_plan(task["task_id"], revision["request_revision"], request, task["acceptance_hash"], binding_snapshot, task["input_sha256"])
        _write_json(attempt_dir / "binding-snapshot.json", binding_snapshot); _write_json(attempt_dir / "internal-plan.json", plan)
        working = attempt_dir / "working-copy.xlsx"; shutil.copy2(task["input_file"], working)
        engine = OpenPyxlEngine.open(working)
        results: dict[str, Any] = {}
        try:
            for step in plan["steps"]:
                op = step["op"]
                if op == "read_table": results[step["id"]] = read_table(engine, step["sheet"], step["header_row"], step["columns"])
                elif op == "summarize_by_dimension":
                    table = results[step["input"]]
                    if "where" in step: table = filter_rows(table, step["where"])
                    table = aggregate(table, step["group_by"], step["metrics"])
                    if "sort" in step: table = sort_rows(table, step["sort"])
                    results[step["id"]] = table
                elif op == "project_columns":
                    results[step["id"]] = select_columns(results[step["input"]], step["fields"])
                elif op == "create_sheet":
                    if step["sheet"] in engine.sheet_names():
                        return self._attempt_failure(task_dir, task, attempt_id, "OUTPUT_CONFLICT", "execution", "目标工作表已存在。")
                    engine.create_sheet(step["sheet"])
                elif op == "write_table": self._write_table(engine, results[step["input"]], step["sheet"], step["anchor"])
            temporary = attempt_dir / "temporary-output.xlsx"; engine.save(temporary)
        except Exception as exc:
            return self._attempt_failure(task_dir, task, attempt_id, "EXECUTION_FAILED", "execution", str(exc))
        finally:
            engine.close()
        if sha256_file(Path(task["input_file"])) != task["input_sha256"]:
            return self._attempt_failure(task_dir, task, attempt_id, "INPUT_CHANGED", "validation", "输入文件在执行期间发生变化。")
        output = Path(task["output_file"]); output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists(): return self._attempt_failure(task_dir, task, attempt_id, "OUTPUT_CONFLICT", "publication", "输出文件已存在。")
        staging = output.with_name(f".{output.name}.sheetpilot-{task['task_id']}-{attempt_id}.tmp")
        shutil.copy2(temporary, staging)
        try:
            os.link(staging, output)
        except FileExistsError:
            staging.unlink(missing_ok=True); return self._attempt_failure(task_dir, task, attempt_id, "OUTPUT_CONFLICT", "publication", "输出文件已存在。")
        except OSError:
            staging.unlink(missing_ok=True); return self._attempt_failure(task_dir, task, attempt_id, "PUBLICATION_FAILED", "publication", "当前文件系统不支持 no-replace 原子发布。")
        staging.unlink(missing_ok=True); published_hash = sha256_file(output)
        evidence = {"runtime_status": "RUNTIME_PASS", "internal_plan_hash": plan_hash, "validated_artifact_sha256": sha256_file(temporary), "published_sha256": published_hash, "coverage": plan["coverage"]}
        evidence["evidence_hash"] = stable_hash(evidence); _write_json(attempt_dir / "evidence.json", evidence)
        state = {"state": "RUNTIME_PASS", "terminal": True, "request_revision": revision["request_revision"], "latest_attempt": {"attempt_id": attempt_id, "state": "RUNTIME_PASS", "request_revision": revision["request_revision"], "finished_at": _now()}, "validated_published_sha256": published_hash, "delivery_valid": True, "artifact_integrity": "MATCHED", "evidence": evidence}
        _write_json(task_dir / "current-state.json", state)
        return {"schema_version": "1.0", "status": "RUNTIME_PASS", "task_id": task["task_id"], "request_revision": revision["request_revision"], "attempt_id": attempt_id, "output_file": str(output), "acceptance_hash": task["acceptance_hash"], "internal_plan_hash": plan_hash, "artifact_integrity": "MATCHED", "delivery_valid": True, "evidence": evidence}

    def _write_table(self, engine: OpenPyxlEngine, table: TableData, sheet: str, anchor: str) -> None:
        row, column = coordinate_to_tuple(anchor); ws = engine.worksheet(sheet)
        for offset, header in enumerate(table.headers): ws.cell(row, column + offset).value = header
        for row_offset, item in enumerate(table.rows, 1):
            for column_offset, header in enumerate(table.headers): ws.cell(row + row_offset, column + column_offset).value = item.get(header)

    def _field_uses(self, request: dict[str, Any], field: str) -> list[str]:
        uses = [f"filter:{item['operator']}" for item in request["filters"] if item["field"] == field]
        uses += ["dimension"] * sum(item["field"] == field for item in request["dimensions"])
        uses += [f"metric:{item['function']}" for item in request["metrics"] if item.get("field") == field]
        return uses

    def _binding_response(self, task_id: str, acceptance_hash: str, binding: dict[str, Any]) -> dict[str, Any]:
        unresolved = [item for item in binding["unresolved"] if item.get("id")]
        allowed = [{"op": "add", "path": f"/bindings/{item['id']}", "constraints": {"candidate_ids": item["candidate_ids"]}} for item in unresolved]
        diagnostics = [{"code": "FIELD_BINDING_AMBIGUOUS" if item["candidate_ids"] else "FIELD_BINDING_NOT_FOUND", "path": item["references"][0], "message": f"业务字段“{item['logical_field']}”无法唯一精确绑定。", "expected": {"kind": "single_binding"}, "actual": {"kind": "candidates", "count": len(item["candidate_ids"])}} for item in unresolved]
        if not binding["source"]:
            diagnostics = [{"code": "SOURCE_BINDING_REQUIRED", "path": "/source/sheet", "message": "来源 Sheet 无法唯一确定。", "expected": {"kind": "existing_sheet"}, "actual": {"kind": "unresolved"}}]
        return {"schema_version": "1.0", "status": "NEEDS_BINDING", "task_id": task_id, "request_revision": 1, "attempt_id": None, "acceptance_hash": acceptance_hash, "binding_slots": unresolved, "binding_candidates": binding["candidates"], "diagnostics": diagnostics, "recovery": {"action": "PROVIDE_BINDING" if allowed else "HUMAN_ACTION_REQUIRED", "retryable": bool(allowed), "base_revision": 1, "allowed_amendments": allowed, "suggested_patch": []}}

    def _amend(self, amendment: dict[str, Any]) -> dict[str, Any]:
        return self._error("REQUEST_INVALID", "CAPABILITY_UNSUPPORTED", "field_binding", "第一批实现尚未开放 Binding Amendment 执行。", amendment.get("task_id"), amendment.get("base_revision"), None, False, "HUMAN_ACTION_REQUIRED")

    def _attempt_failure(self, task_dir: Path, task: dict[str, Any], attempt_id: str, code: str, phase: str, message: str) -> dict[str, Any]:
        response = self._error("EXECUTION_FAILED" if phase == "execution" else "PUBLICATION_FAILED", code, phase, message, task["task_id"], 1, attempt_id, phase != "publication", "RETRY_ATTEMPT" if phase != "publication" else "HUMAN_ACTION_REQUIRED")
        _write_json(task_dir / "current-state.json", {"state": "FAILED", "terminal": False, "request_revision": 1, "latest_attempt": {"attempt_id": attempt_id, "state": response["status"], "request_revision": 1, "finished_at": _now()}, "delivery_valid": False, "recovery": response["error"]["recovery"]})
        return response

    def _error(self, status: str, code: str, phase: str, message: str, task_id: str | None, revision: int | None, attempt_id: str | None, retryable: bool, action: str) -> dict[str, Any]:
        return {"schema_version": "1.0", "status": status, "task_id": task_id, "request_revision": revision, "attempt_id": attempt_id, "error": {"code": code, "phase": phase, "message": message, "retryable": retryable, "diagnostics": [], "recovery": {"action": action, "retryable": retryable, "base_revision": revision, "allowed_amendments": [], "suggested_patch": []}}}

    def _task_dir(self, task_id: str) -> Path:
        suffix = task_id.removeprefix("task-")
        if not task_id.startswith("task-") or not suffix or any(char not in "0123456789abcdef" for char in suffix):
            return self.tasks_root / "invalid"
        return self.tasks_root / task_id

    def _find_submission(self, submission_hash: str, input_hash: str, output_file: str) -> str | None:
        if not self.tasks_root.is_dir():
            return None
        for path in self.tasks_root.glob("task-*/task.json"):
            try: task = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): continue
            if task.get("submission_hash") == submission_hash and task.get("input_sha256") == input_hash and task.get("output_file") == output_file and (path.parent / "current-state.json").is_file():
                return task["task_id"]
        return None
