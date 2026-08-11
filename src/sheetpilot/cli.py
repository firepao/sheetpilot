from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .errors import ErrorCode, SheetPilotError
from .executor import execute_plan
from .inspector import inspect_workbook
from .models import ExecutionPlan, HighLevelPlan, Requirement, SemanticTask
from .planning.hybrid import HybridPlanner
from .planning.compiler import compile_plan
from .planning.policy import evaluate_policy
from .validators import validate_and_publish
from .capabilities import DEFAULT_REGISTRY
from .recipes import DEFAULT_RECIPE_REGISTRY
from .mvp import manifest as mvp_manifest, run_plan as run_mvp_plan, validate_run as validate_mvp_run
from .task_api import TaskRuntime

ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))
def _write_json(path: Path, value: dict) -> None: path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _validate_schema(value: dict, name: str) -> None:
    schema = _read_json(ROOT / "schemas" / name)
    errors = []
    if not isinstance(value, dict): errors.append("根节点必须是对象")
    else:
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in value]
        unknown = [key for key in value if schema.get("additionalProperties") is False and key not in properties]
        if missing: errors.append("缺少必填字段: " + ", ".join(missing))
        if unknown: errors.append("包含未知字段: " + ", ".join(unknown))
        for key, rule in properties.items():
            if key not in value: continue
            item = value[key]
            if "const" in rule and item != rule["const"]: errors.append(f"{key} 必须为 {rule['const']}")
            if "enum" in rule and item not in rule["enum"]: errors.append(f"{key} 不在允许枚举中")
            expected = rule.get("type")
            allowed = expected if isinstance(expected, list) else [expected]
            type_map = {"object": dict, "array": list, "string": str, "null": type(None)}
            if expected and not any(isinstance(item, type_map[t]) for t in allowed if t in type_map): errors.append(f"{key} 类型错误")
    if errors: raise SheetPilotError(ErrorCode.INPUT_INVALID, "JSON Schema 校验失败", {"errors": errors[:10]})


def _load_plan(path: Path) -> ExecutionPlan:
    value = _read_json(path); _validate_schema(value, "execution-plan.schema.json"); return ExecutionPlan.from_dict(value)


def cmd_inspect(args):
    run_dir = Path(args.run_dir); run_dir.mkdir(parents=True, exist_ok=True)
    profile = inspect_workbook(Path(args.input)); _write_json(run_dir / "workbook_profile.json", profile.to_dict()); return profile.to_dict()


def cmd_capabilities(args):
    manifest = DEFAULT_REGISTRY.public_manifest()
    if args.name:
        manifest["capabilities"] = [item for item in manifest["capabilities"] if item["name"] == args.name]
    if args.kind:
        manifest["capabilities"] = [item for item in manifest["capabilities"] if item["kind"] == args.kind]
    return manifest


def cmd_recipes(args):
    recipes = DEFAULT_RECIPE_REGISTRY.manifest()
    if args.name:
        recipes = [item for item in recipes if item["id"] == args.name]
    return {"schema_version": "1.0", "recipes": recipes}

def cmd_mvp_capabilities(args):
    return mvp_manifest()


def cmd_mvp_run(args):
    plan = _read_json(Path(args.plan))
    if Path(args.input).resolve() != Path(plan.get("input_file", "")).resolve():
        raise SheetPilotError(ErrorCode.INPUT_INVALID, "--input 与计划 input_file 不一致")
    if Path(args.output).resolve() != Path(plan.get("output_file", "")).resolve():
        raise SheetPilotError(ErrorCode.INPUT_INVALID, "--output 与计划 output_file 不一致")
    return run_mvp_plan(plan, Path(args.run_dir), Path(args.dynamic_script) if args.dynamic_script else None)


def cmd_mvp_validate(args):
    return validate_mvp_run(Path(args.run_dir))


def _task_runtime() -> TaskRuntime:
    return TaskRuntime()


def cmd_task_types(args):
    return _task_runtime().task_types()


def cmd_task_run(args):
    return _task_runtime().run(_read_json(Path(args.request)))


def cmd_task_status(args):
    return _task_runtime().status(args.task_id)


def cmd_plan(args):
    task_data = _read_json(Path(args.task))
    _validate_schema(task_data, "semantic-task.schema.json")
    raw_requirements = _read_json(Path(args.requirements))
    if not isinstance(raw_requirements, list):
        raise SheetPilotError(ErrorCode.INPUT_INVALID, "Requirement 文件根节点必须是数组")
    try:
        requirements = [Requirement(**item) for item in raw_requirements]
    except (TypeError, ValueError) as exc:
        raise SheetPilotError(ErrorCode.INPUT_INVALID, "Requirement 字段不合法", {"reason": str(exc)}) from exc
    decision = HybridPlanner().choose(SemanticTask.from_dict(task_data), requirements)
    return {
        "strategy": decision.strategy,
        "components": decision.components,
        "coverage": [asdict(item) for item in decision.coverage],
        "rationale": decision.rationale,
        "executable": decision.executable,
    }


def cmd_compile(args):
    run_dir = Path(args.run_dir); run_dir.mkdir(parents=True, exist_ok=True)
    task_data, high_data = _read_json(Path(args.task)), _read_json(Path(args.high_level_plan))
    _validate_schema(task_data, "semantic-task.schema.json"); _validate_schema(high_data, "high-level-plan.schema.json")
    task, high = SemanticTask.from_dict(task_data), HighLevelPlan.from_dict(high_data)
    profile = inspect_workbook(Path(task.input_file)); plan = compile_plan(task, high, profile); decision = evaluate_policy(plan, profile, task)
    _write_json(run_dir / "workbook_profile.json", profile.to_dict()); _write_json(run_dir / "execution_plan.json", plan.to_dict()); _write_json(run_dir / "policy_decision.json", decision.to_dict())
    if decision.decision == "BLOCK": raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "策略门禁阻断执行", decision.to_dict())
    if decision.decision == "CONFIRM": raise SheetPilotError(ErrorCode.CONFIRMATION_REQUIRED, "需要用户确认", decision.to_dict())
    return {"execution_plan": str(run_dir / "execution_plan.json"), "policy": decision.to_dict()}


def cmd_execute(args):
    temporary, record = execute_plan(_load_plan(Path(args.plan)), Path(args.run_dir)); return {"temporary_output": str(temporary), "execution": record}


def cmd_validate(args):
    run_dir = Path(args.run_dir); plan = _load_plan(run_dir / "execution_plan.json")
    return validate_and_publish(plan, run_dir / "temporary_output.xlsx", run_dir).to_dict()


def cmd_run(args):
    cmd_compile(args); run_dir = Path(args.run_dir); plan = _load_plan(run_dir / "execution_plan.json")
    temporary, _ = execute_plan(plan, run_dir); return validate_and_publish(plan, temporary, run_dir).to_dict()


def build_parser():
    parser = argparse.ArgumentParser(prog="sheetpilot"); sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect"); inspect.add_argument("--input", required=True); inspect.add_argument("--run-dir", required=True); inspect.set_defaults(func=cmd_inspect)
    capabilities = sub.add_parser("capabilities"); capabilities.add_argument("--name"); capabilities.add_argument("--kind", choices=["CAPABILITY", "COMPOSITE"]); capabilities.set_defaults(func=cmd_capabilities)
    recipes = sub.add_parser("recipes"); recipes.add_argument("--name"); recipes.set_defaults(func=cmd_recipes)
    mvp = sub.add_parser("mvp-capabilities", help="列出轻量 MVP 的原子和分子能力"); mvp.set_defaults(func=cmd_mvp_capabilities)
    mvp_run = sub.add_parser("mvp-run", help="执行轻量计划并生成待验证工作簿")
    mvp_run.add_argument("--input", required=True); mvp_run.add_argument("--output", required=True); mvp_run.add_argument("--plan", required=True); mvp_run.add_argument("--run-dir", required=True); mvp_run.add_argument("--dynamic-script"); mvp_run.set_defaults(func=cmd_mvp_run)
    mvp_validate = sub.add_parser("mvp-validate", help="独立验证并发布轻量计划结果")
    mvp_validate.add_argument("--run-dir", required=True); mvp_validate.set_defaults(func=cmd_mvp_validate)
    task_types = sub.add_parser("task-types", help="列出完整的 Agent-facing Task Type 契约"); task_types.set_defaults(func=cmd_task_types)
    task_run = sub.add_parser("task-run", help="提交 Task Request；Runtime 自动管理 Task、Attempt 和发布")
    task_run.add_argument("--request", required=True); task_run.set_defaults(func=cmd_task_run)
    task_status = sub.add_parser("task-status", help="查询 Task 状态和发布文件完整性")
    task_status.add_argument("--task-id", required=True); task_status.set_defaults(func=cmd_task_status)
    plan = sub.add_parser("plan"); plan.add_argument("--task", required=True); plan.add_argument("--requirements", required=True); plan.set_defaults(func=cmd_plan)
    for name, func in (("compile", cmd_compile), ("run", cmd_run)):
        command = sub.add_parser(name); command.add_argument("--task", required=True); command.add_argument("--high-level-plan", required=True); command.add_argument("--run-dir", required=True); command.set_defaults(func=func)
    execute = sub.add_parser("execute"); execute.add_argument("--plan", required=True); execute.add_argument("--run-dir", required=True); execute.set_defaults(func=cmd_execute)
    validate = sub.add_parser("validate"); validate.add_argument("--run-dir", required=True); validate.set_defaults(func=cmd_validate)
    return parser


EXIT_CODES = {ErrorCode.INPUT_INVALID: 2, ErrorCode.PLAN_INVALID: 2, ErrorCode.WORKBOOK_UNSUPPORTED: 3, ErrorCode.CAPABILITY_UNSUPPORTED: 3, ErrorCode.DYNAMIC_TRANSFORM_REJECTED: 4, ErrorCode.CONFIRMATION_REQUIRED: 4, ErrorCode.POLICY_BLOCKED: 4, ErrorCode.EXECUTION_FAILED: 5, ErrorCode.OUTPUT_CORRUPTED: 5, ErrorCode.VALIDATION_FAILED: 6}


def main(argv=None):
    try:
        args = build_parser().parse_args(argv); print(json.dumps(args.func(args), ensure_ascii=False, default=str)); return 0
    except SheetPilotError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False), file=sys.stdout); return EXIT_CODES.get(exc.code, 2)
    except Exception as exc:
        error = SheetPilotError(ErrorCode.EXECUTION_FAILED, "未处理的内部错误", {"reason": str(exc)})
        print(json.dumps(error.to_dict(), ensure_ascii=False), file=sys.stdout); return 5


if __name__ == "__main__": raise SystemExit(main())
