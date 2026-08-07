from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from ..engines import OpenPyxlEngine
from ..errors import ErrorCode, SheetPilotError
from ..events import EventWriter
from ..inspector.ooxml_risk import inspect_ooxml
from ..models import ExecutionPlan
from ..workbook import WorkbookContext
from ..workspace import Workspace, sha256_file
from .change_recorder import ChangeRecorder
from .dispatcher import dispatch


def execute_plan(plan: ExecutionPlan, run_dir: Path) -> tuple[Path, dict]:
    run_dir.mkdir(parents=True, exist_ok=True)
    events = EventWriter(run_dir / "events.jsonl")
    source = Path(plan.input_file).resolve()
    if sha256_file(source) != plan.input_sha256:
        raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "输入文件在编译后发生变化")
    risks = inspect_ooxml(source)
    if any(risk.get("severity") in {"high", "unsupported"} for risk in risks):
        raise SheetPilotError(ErrorCode.WORKBOOK_UNSUPPORTED, "输入包含 openpyxl 无法安全保留的高级对象", {"risk_objects": risks})
    workspace = Workspace(run_dir, Path(plan.output_file).resolve().parent)
    workspace.validate_output(source, Path(plan.output_file))
    working = workspace.create_working_copy(source)
    recorder = ChangeRecorder(run_dir / "execution.json", plan.change_budget)
    engine = OpenPyxlEngine.open(working)
    context, results = WorkbookContext(engine, recorder, run_dir), {}
    temporary = run_dir / "temporary_output.xlsx"
    try:
        events.emit("execution_started", plan_id=plan.plan_id)
        for step in plan.steps:
            events.emit("step_started", step_id=step.id)
            dispatch(context, step, results)
            events.emit("step_completed", step_id=step.id)
        engine.save(temporary)
    except SheetPilotError:
        events.emit("execution_failed")
        raise
    except Exception as exc:
        events.emit("execution_failed", reason=str(exc))
        raise SheetPilotError(ErrorCode.EXECUTION_FAILED, "执行步骤失败", {"reason": str(exc)}) from exc
    finally:
        engine.close(); recorder.save()
    try:
        check = load_workbook(temporary, read_only=True, data_only=False); check.close()
    except Exception as exc:
        raise SheetPilotError(ErrorCode.OUTPUT_CORRUPTED, "临时输出无法重新打开") from exc
    events.emit("execution_completed", temporary_output=str(temporary))
    return temporary, recorder.snapshot()
