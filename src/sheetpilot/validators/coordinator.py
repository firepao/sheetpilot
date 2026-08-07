from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..errors import ErrorCode, SheetPilotError
from ..models import ExecutionPlan, TaskResult
from .business import check_business
from .diff import check_original_sheets_unchanged
from .integrity import check_integrity
from .layout import check_layout
from .formulas import check_formulas


def validate_and_publish(plan: ExecutionPlan, temporary: Path, run_dir: Path) -> TaskResult:
    new_sheets = [s.parameters["sheet"] for s in plan.steps if s.handler == "create_sheet"]
    checks = check_integrity(Path(plan.input_file), temporary, plan.input_sha256, new_sheets)
    checks += [check_original_sheets_unchanged(Path(plan.input_file), temporary), check_business(plan, temporary), check_formulas(plan, temporary), check_layout(plan, temporary)]
    critical_failed = any(not check.passed and check.severity == "critical" for check in checks)
    warnings = [{"code": check.name.upper(), "message": check.message} for check in checks if not check.passed and check.severity != "critical"]
    if critical_failed:
        result = TaskResult("FAIL", None, "验收失败，未发布结果文件", checks, warnings)
    else:
        output = Path(plan.output_file).resolve(); output.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(temporary, output)
        result = TaskResult("PASS_WITH_WARNINGS" if warnings else "PASS", str(output), "工作簿处理和核心业务对账完成", checks, warnings)
    (run_dir / "evidence.json").write_text(json.dumps({"checks": [c.__dict__ for c in checks]}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (run_dir / "result.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if critical_failed: raise SheetPilotError(ErrorCode.VALIDATION_FAILED, result.summary, result.to_dict())
    return result
