from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..errors import ErrorCode, SheetPilotError
from ..workbook.tables import TableData


ALLOWED_IMPORTS = {"datetime", "math", "re", "statistics"}
FORBIDDEN_CALLS = {"breakpoint", "compile", "eval", "exec", "globals", "input", "locals", "open", "__import__"}
FORBIDDEN_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.Delete, ast.Global, ast.Lambda, ast.Nonlocal, ast.With, ast.AsyncWith)


@dataclass(frozen=True)
class TransformManifest:
    name: str
    timeout_seconds: int = 10
    max_input_rows: int = 200_000
    max_output_rows: int = 200_000
    max_output_columns: int = 100


def analyze_transform(source: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SheetPilotError(ErrorCode.PLAN_INVALID, "Transform 语法错误", {"line": exc.lineno}) from exc
    errors: list[str] = []
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != "transform":
        errors.append("必须且只能定义一个 transform(table, params) 函数")
    elif [arg.arg for arg in functions[0].args.args] != ["table", "params"]:
        errors.append("transform 签名必须为 transform(table, params)")
    if any(not isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)) for node in tree.body):
        errors.append("顶层只允许白名单 import 和 transform 函数")
    if functions and functions[0].decorator_list:
        errors.append("禁止函数装饰器")
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            errors.append(f"禁止语法: {type(node).__name__}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(name not in ALLOWED_IMPORTS for name in names):
                errors.append("导入不在白名单")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            errors.append(f"禁止调用: {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            errors.append("禁止访问 dunder 属性")
    if sum(1 for _ in ast.walk(tree)) > 2_000:
        errors.append("AST 节点超过限制")
    if errors:
        raise SheetPilotError(ErrorCode.DYNAMIC_TRANSFORM_REJECTED, "Transform 静态检查失败", {"errors": sorted(set(errors))})
    return {"passed": True, "ast_nodes": sum(1 for _ in ast.walk(tree)), "allowed_imports": sorted(ALLOWED_IMPORTS)}


class TransformRunner:
    def run(self, source: str, table: TableData, params: dict[str, Any], manifest: TransformManifest, run_dir: Path) -> TableData:
        analysis = analyze_transform(source)
        if len(table.rows) > manifest.max_input_rows:
            raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "Transform 输入行数超过预算")
        script_dir = run_dir / "script"
        script_dir.mkdir(parents=True, exist_ok=True)
        (script_dir / "task.py").write_text(source, encoding="utf-8")
        (script_dir / "manifest.json").write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
        (script_dir / "static_analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        payload = {"headers": table.headers, "rows": table.rows, "params": params}
        (script_dir / "input.json").write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        worker = Path(__file__).with_name("transform_worker.py")
        try:
            completed = subprocess.run([sys.executable, "-I", str(worker), str(script_dir)], capture_output=True, text=True, encoding="utf-8", timeout=manifest.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise SheetPilotError(ErrorCode.EXECUTION_FAILED, "Transform 执行超时") from exc
        (script_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (script_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise SheetPilotError(ErrorCode.EXECUTION_FAILED, "Transform 执行失败", {"stderr": completed.stderr[-2000:]})
        result = json.loads((script_dir / "result.json").read_text(encoding="utf-8"))
        headers, rows = result.get("headers"), result.get("rows")
        if not isinstance(headers, list) or not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise SheetPilotError(ErrorCode.OUTPUT_CORRUPTED, "Transform 输出不符合 TableData 契约")
        if len(headers) > manifest.max_output_columns or len(rows) > manifest.max_output_rows or len(headers) != len(set(headers)):
            raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "Transform 输出超过预算或列名重复")
        if any(set(row) - set(headers) for row in rows):
            raise SheetPilotError(ErrorCode.OUTPUT_CORRUPTED, "Transform 输出包含未声明字段")
        return TableData(headers, rows)
