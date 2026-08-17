#!/usr/bin/env python3
"""Locate SheetPilot and delegate only to the Agent-facing Task API."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def find_root() -> Path:
    configured = os.environ.get("SHEETPILOT_ROOT")
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend(Path(__file__).resolve().parents)
    current = Path.cwd().resolve()
    candidates.extend([current, *current.parents])
    for candidate in candidates:
        if (candidate / "src" / "sheetpilot" / "agent_cli.py").is_file():
            return candidate.resolve()
    raise SystemExit(
        '{"schema_version":"1.0","status":"CONFIGURATION_REQUIRED",'
        '"message":"找不到 SheetPilot Runtime；本次运行已停止。请用户在新会话前配置 SHEETPILOT_ROOT。",'
        '"recovery":{"action":"HUMAN_ACTION_REQUIRED","retryable":false,'
        '"allowed_amendments":[]}}'
    )


AUTO_RESULT_PLACEHOLDER = "<AUTO-RESULT-DIR>"
SCENARIO_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _reject(message: str) -> None:
    print(json.dumps({"schema_version": "1.0", "status": "REQUEST_INVALID", "task_id": None,
                      "error": {"code": "INVALID_VALUE", "phase": "contract_validation", "message": message, "retryable": False,
                                "recovery": {"action": "HUMAN_ACTION_REQUIRED", "retryable": False, "base_revision": None, "allowed_amendments": [], "suggested_patch": []}}}, ensure_ascii=False))


def _flag_value(argv: list[str], flag: str) -> str | None:
    try:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else None
    except ValueError:
        return None


def _generate_result_dir(parent: str, scenario_id: str) -> Path:
    base = Path(parent).expanduser().resolve(); base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%dT%H%M%S+0800")
    for _ in range(20):
        candidate = base / f"{scenario_id}__{stamp}__run-{uuid.uuid4().hex[:6]}"
        if candidate.resolve().parent != base: continue
        try:
            candidate.mkdir(); return candidate
        except FileExistsError: continue
    raise RuntimeError("无法创建唯一结果目录")


def _substitute_result_dir(request_path: str, parent: str, scenario_id: str):
    data = json.loads(Path(request_path).read_text(encoding="utf-8")); output = data.get("output_file", "")
    if AUTO_RESULT_PLACEHOLDER not in output: return request_path, None, None
    if "task_id" in data: _reject("Amendment 请求不得使用 <AUTO-RESULT-DIR>，请复用首次响应的目录。"); return None
    if not SCENARIO_ID.fullmatch(scenario_id): _reject("scenario-id 只允许字母、数字、下划线和连字符。"); return None
    filename = output.split(AUTO_RESULT_PLACEHOLDER, 1)[1].lstrip("/\\")
    if not filename or any(c in filename for c in "/\\:") or filename in {".", ".."}: _reject("输出文件名必须是结果目录内的单层文件名。"); return None
    generated = _generate_result_dir(parent, scenario_id); data["output_file"] = str(generated / filename)
    handle = tempfile.NamedTemporaryFile(prefix="sheetpilot-request-", suffix=".json", delete=False, mode="w", encoding="utf-8")
    try: handle.write(json.dumps(data, ensure_ascii=False))
    finally: handle.close()
    return handle.name, str(generated), handle.name


def main() -> int:
    root = find_root()
    sys.path.insert(0, str(root / "src"))
    from sheetpilot.agent_cli import main as sheetpilot_main

    delegated = list(sys.argv[1:]); generated = None; temporary = None
    parent = _flag_value(delegated, "--auto-result-dir")
    if "task-run" in delegated and parent:
        request_index = delegated.index("--request") if "--request" in delegated else -1
        if request_index < 0 or request_index + 1 >= len(delegated): _reject("task-run 必须携带 --request。"); return 0
        scenario = _flag_value(delegated, "--scenario-id") or "sheetpilot"
        result = _substitute_result_dir(delegated[request_index + 1], parent, scenario)
        if result is None: return 0
        effective, generated, temporary = result
        for flag in ("--auto-result-dir", "--scenario-id"):
            if flag in delegated:
                i = delegated.index(flag); del delegated[i:i + 2]
        delegated[delegated.index("--request") + 1] = effective
    try:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer): code = sheetpilot_main(delegated)
        text = buffer.getvalue().strip()
        if code == 0 and generated and text:
            payload = json.loads(text); payload["generated_result_dir"] = generated; print(json.dumps(payload, ensure_ascii=False))
        elif text: print(text)
        return code
    finally:
        if temporary: Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
