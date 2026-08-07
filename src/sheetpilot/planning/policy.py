from __future__ import annotations

from pathlib import Path

from ..models import PolicyDecision, PolicyReason, SemanticTask, WorkbookProfile, ExecutionPlan


def evaluate_policy(plan: ExecutionPlan, profile: WorkbookProfile, task: SemanticTask) -> PolicyDecision:
    reasons = []
    if Path(plan.input_file).resolve() == Path(plan.output_file).resolve():
        reasons.append(PolicyReason("OUTPUT_OVERWRITES_INPUT", "输出会覆盖输入文件", True))
    high_risks = [risk for risk in profile.risk_objects if risk.get("severity") in {"high", "unsupported"}]
    if high_risks:
        reasons.append(PolicyReason("UNSUPPORTED_OOXML_OBJECT", "工作簿包含当前引擎无法安全保留的高级对象", True))
    if task.ambiguities and not task.confirmations:
        reasons.append(PolicyReason("KEY_SEMANTIC_AMBIGUITY", "关键业务口径尚未确认", False))
    if any(reason.blocking for reason in reasons): decision = "BLOCK"
    elif reasons: decision = "CONFIRM"
    else: decision = "PROCEED"
    return PolicyDecision(decision, reasons, [])
