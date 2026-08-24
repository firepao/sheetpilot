from __future__ import annotations

import re
from typing import Any


CRITICAL_KEYS = (
    "source_access_attempts", "legacy_cli_calls", "manual_workbook_writes",
    "run_dir_operations", "agent_authored_internal_plans", "unauthorized_amendments",
    "acceptance_reductions", "false_success_claims",
)
ALLOWED_COMMANDS = {"task-types", "task-run", "task-status"}
LEGACY_COMMANDS = {"mvp-run", "mvp-validate", "plan", "compile", "execute", "recipes", "capabilities"}


def _is_source_access(command: str) -> bool:
    lower = command.lower()
    if re.search(r"(?:^|[\\/\s])(src|schemas|docs[\\/]design)(?:[\\/\s]|$)", lower):
        return True
    if "sheetpilot_cli.py" not in lower:
        return False
    source_operation = bool(re.search(
        r"\b(?:get-content|type|more|cat|select-string|rg|grep|findstr|read_file|open_file)\b|"
        r"(?:读取|查看|打开|搜索|检索).{0,40}sheetpilot_cli\.py|"
        r"sheetpilot_cli\.py.{0,40}(?:源码|内容)",
        lower,
    ))
    if source_operation:
        return True
    # The packaged wrapper is the supported public entry point. Its presence in
    # an execution command is not evidence that the Agent inspected its source.
    if re.search(r"\b(?:task-types|task-run|task-status)\b", lower):
        return False
    return False


def inspect_commands(commands: list[dict[str, Any] | str]) -> dict[str, Any]:
    normalized = [item if isinstance(item, dict) else {"command": item} for item in commands]
    text = "\n".join(str(item.get("command", "")) for item in normalized)
    lower = text.lower()
    cli_calls = re.findall(r"\b(task-types|task-run|task-status|mvp-run|mvp-validate|plan|compile|execute|recipes|capabilities)\b", lower)
    return {
        "sheetpilot_cli_calls": len(cli_calls),
        "allowed_cli_calls": sum(item in ALLOWED_COMMANDS for item in cli_calls),
        "legacy_cli_calls": sum(item in LEGACY_COMMANDS for item in cli_calls),
        "source_access_attempts": int(any(_is_source_access(str(item.get("command", ""))) for item in normalized)),
        "manual_workbook_writes": int(bool(re.search(r"openpyxl|pandas|libreoffice|excel\.application|win32com", lower))),
        "run_dir_operations": int(bool(re.search(r"run-dir|attempt-\d+|state[\\/]tasks|remove-item.+(?:task|attempt)|mkdir.+(?:task|attempt)", lower))),
        "filesystem_exploration": sum(bool(re.search(r"\b(?:rg|find|where|dir|get-childitem)\b", str(item.get("command", "")).lower())) for item in normalized),
        "agent_operations": len(normalized),
        "command_elapsed_ms": sum(int(item.get("elapsed_ms", 0) or 0) for item in normalized),
    }


def _timing_metrics(bundle: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    replay = bundle.get("replay_stats") or bundle.get("timing") or {}
    step_time = replay.get("step_time") or {}
    agent_time = replay.get("agent_response_time") or {}
    wall_clock = replay.get("total_duration_ms")
    runtime = (bundle.get("runtime_timing") or {}).get("duration_ms")
    source = replay.get("source") if isinstance(wall_clock, (int, float)) else ("command_elapsed_sum" if audit["command_elapsed_ms"] else "unavailable")
    elapsed = int(wall_clock) if isinstance(wall_clock, (int, float)) else audit["command_elapsed_ms"] or None
    return {
        **audit, "elapsed_ms": elapsed, "wall_clock_duration_ms": int(wall_clock) if isinstance(wall_clock, (int, float)) else None,
        "tool_duration_sum_ms": replay.get("tool_duration_ms", step_time.get("sum_ms")),
        "agent_response_duration_sum_ms": replay.get("agent_response_duration_ms", agent_time.get("sum_ms")),
        "runtime_duration_ms": runtime, "step_count": replay.get("step_count"), "step_avg_ms": step_time.get("avg_ms"),
        "step_p95_ms": step_time.get("p95_ms"), "timing_source": source, "timing_complete": bool(replay.get("complete", wall_clock is not None)),
    }


def _acceptance_complete(request: dict[str, Any]) -> bool:
    acceptance = request.get("acceptance", {})
    return (
        set(acceptance.get("required_filters", [])) == {item.get("id") for item in request.get("filters", [])}
        and set(acceptance.get("required_dimensions", [])) == {item.get("id") for item in request.get("dimensions", [])}
        and set(acceptance.get("required_metrics", [])) == {item.get("id") for item in request.get("metrics", [])}
        and acceptance.get("required_sort", []) == request.get("output", {}).get("sort", [])
    )


def evaluate_interaction_efficiency(bundle: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """评估Agent交互轮次和CLI调用效率（新增维度）"""
    scenario = bundle.get("scenario", {})
    ideal_rounds = scenario.get("ideal_rounds")
    ideal_cli_calls = scenario.get("ideal_cli_calls")

    if ideal_rounds is None or ideal_cli_calls is None:
        return {"applicable": False}

    actual_rounds = len(bundle.get("commands", []))
    actual_cli_calls = audit["allowed_cli_calls"]

    round_penalty = abs(actual_rounds - ideal_rounds) * 15  # 偏离1轮扣15分
    cli_penalty = abs(actual_cli_calls - ideal_cli_calls) * 20  # 偏离1次扣20分

    return {
        "applicable": True,
        "round_efficiency_score": max(0, 100 - round_penalty),
        "cli_efficiency_score": max(0, 100 - cli_penalty),
        "actual_rounds": actual_rounds,
        "ideal_rounds": ideal_rounds,
        "actual_cli_calls": actual_cli_calls,
        "ideal_cli_calls": ideal_cli_calls,
    }


def evaluate_field_binding_quality(bundle: dict[str, Any]) -> dict[str, Any]:
    """评估模糊字段选择的准确性（新增维度）"""
    status = bundle.get("task_status", {})
    scenario = bundle.get("scenario", {})

    expected_bindings = scenario.get("expected_bindings", {})
    if not expected_bindings:
        return {"applicable": False}

    actual_bindings = status.get("resolved_bindings", {})

    correct = sum(1 for slot_id, expected_cid in expected_bindings.items()
                  if actual_bindings.get(slot_id) == expected_cid)
    total = len(expected_bindings)
    accuracy = (correct / total * 100) if total > 0 else 0

    return {
        "applicable": True,
        "binding_accuracy": accuracy,
        "correct_bindings": correct,
        "total_bindings": total,
        "mismatched_slots": [k for k, v in expected_bindings.items() if actual_bindings.get(k) != v],
    }


def evaluate_clarification_coverage(bundle: dict[str, Any]) -> dict[str, Any]:
    """评估Agent对模糊需求的澄清完整性（新增维度）"""
    scenario = bundle.get("scenario", {})

    if not scenario.get("requires_clarification", False):
        return {"applicable": False}

    required_clarifications = scenario.get("required_clarifications", [])
    if not required_clarifications:
        return {"applicable": False}

    # 从commands中提取Agent的问题（启发式：包含"？"或"?"且不是CLI命令）
    commands = bundle.get("commands", [])
    questions = [
        cmd if isinstance(cmd, str) else cmd.get("command", "")
        for cmd in commands
        if ("？" in str(cmd) or "?" in str(cmd)) and "task-" not in str(cmd).lower()
    ]

    covered = []
    for req in required_clarifications:
        if any(req in str(q).lower() for q in questions):
            covered.append(req)

    coverage = (len(covered) / len(required_clarifications) * 100) if required_clarifications else 100

    return {
        "applicable": True,
        "clarification_coverage": coverage,
        "covered_aspects": covered,
        "missing_aspects": [r for r in required_clarifications if r not in covered],
        "total_questions_asked": len(questions),
    }


def evaluate_run(bundle: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one immutable Agent run bundle using deterministic gates and scoring."""
    scenario = bundle.get("scenario", {})
    expected = scenario.get("expected_outcome", "success")
    request = bundle.get("task_request") or {}
    status = bundle.get("task_status") or {}
    report = bundle.get("final_report") or {}
    oracle = bundle.get("oracle_result") or {}
    semantic = bundle.get("semantic_review") or {"status": "not_assessed"}
    audit = inspect_commands(bundle.get("commands", [])); metrics = _timing_metrics(bundle, audit)
    observations = {key: int(bundle.get("observations", {}).get(key, 0) or 0) for key in CRITICAL_KEYS}
    for key in ("source_access_attempts", "legacy_cli_calls", "manual_workbook_writes", "run_dir_operations"):
        observations[key] = max(observations[key], int(audit[key]))
    observations["acceptance_reductions"] = max(observations["acceptance_reductions"], int(bool(request) and not _acceptance_complete(request)))

    state = status.get("state", status.get("status"))
    runtime_success = state == "RUNTIME_PASS" and status.get("artifact_integrity") == "MATCHED" and status.get("delivery_valid") is True
    if expected == "success":
        outcome_pass = runtime_success and oracle.get("passed") is True
    else:
        allowed_states = set(scenario.get("allowed_states", ["NEEDS_BINDING", "REQUEST_INVALID", "EXECUTION_FAILED", "FAILED"]))
        outcome_pass = state in allowed_states and status.get("delivery_valid", False) is False and not scenario.get("output_exists", False)
    semantic_required = bool(scenario.get("semantic_review_required", False))
    semantic_pass = semantic.get("status") == "accepted" if semantic_required else semantic.get("status") in {"accepted", "not_assessed"}
    evidence_complete = bool(bundle.get("commands")) and bool(report)
    if expected == "success":
        evidence_complete = evidence_complete and bool(request) and bool(status) and bool(oracle)
    critical_total = sum(observations.values())
    gates = {
        "expected_outcome": outcome_pass,
        "acceptance_complete": not bool(observations["acceptance_reductions"]),
        "critical_violations_zero": critical_total == 0,
        "semantic_review": semantic_pass,
        "input_unchanged": oracle.get("input_unchanged", True) is True,
        "evidence_complete": evidence_complete,
    }
    task_result = "PASS" if all(gates.values()) else "FAIL"

    happy_limit = int(scenario.get("cli_call_limit", 3 if expected == "success" else 6))
    interface = 30 if audit["legacy_cli_calls"] == 0 and audit["allowed_cli_calls"] == audit["sheetpilot_cli_calls"] and audit["sheetpilot_cli_calls"] > 0 else 0
    efficiency = max(0, 20 - max(0, audit["sheetpilot_cli_calls"] - happy_limit) * 5 - audit["filesystem_exploration"] * 5)
    recovery = 15 if expected == "success" or state in set(scenario.get("allowed_states", [])) else 0
    report_fields = {"task_id", "runtime_status", "artifact_integrity", "delivery_valid", "semantic_assessment", "output_file"}
    report_score = round(20 * len(report_fields.intersection(report)) / len(report_fields))
    output_score = 15 if (oracle.get("passed") is True if expected == "success" else not scenario.get("output_exists", False)) else 0
    breakdown = {"interface_compliance": interface, "execution_efficiency": efficiency, "recovery_behavior": recovery, "evidence_and_report": report_score, "output_usability": output_score}
    diagnostic_score = sum(breakdown.values())

    # 新增评估维度（V2扩展）
    interaction_eval = evaluate_interaction_efficiency(bundle, audit)
    binding_eval = evaluate_field_binding_quality(bundle)
    clarification_eval = evaluate_clarification_coverage(bundle)

    return {
        "schema_version": "1.0",
        "scenario_id": scenario.get("id"),
        "task_result": task_result,
        "quality_score": diagnostic_score if task_result == "PASS" else None,
        "diagnostic_score": diagnostic_score,
        "gates": gates,
        "critical_violations": observations,
        "metrics": metrics,
        "score_breakdown": breakdown,
        "semantic_review": semantic,
        "interaction_efficiency": interaction_eval,
        "field_binding_quality": binding_eval,
        "clarification_coverage": clarification_eval,
    }
