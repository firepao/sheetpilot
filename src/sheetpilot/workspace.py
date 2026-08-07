from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .errors import ErrorCode, SheetPilotError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Workspace:
    def __init__(self, run_dir: Path, allowed_root: Path | None = None):
        self.run_dir = run_dir.resolve()
        self.allowed_root = (allowed_root or Path.cwd()).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def validate_input(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_file() or resolved.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise SheetPilotError(ErrorCode.INPUT_INVALID, "输入必须是存在的 .xlsx 或 .xlsm 文件", {"path": str(resolved)})
        return resolved

    def validate_output(self, input_path: Path, output_path: Path) -> Path:
        output = output_path.resolve()
        if output == input_path.resolve():
            raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "输出文件不能覆盖输入文件")
        try:
            output.relative_to(self.allowed_root)
        except ValueError as exc:
            raise SheetPilotError(ErrorCode.POLICY_BLOCKED, "输出路径越出允许目录", {"path": str(output)}) from exc
        return output

    def create_working_copy(self, source: Path) -> Path:
        target = self.run_dir / "working.xlsx"
        shutil.copy2(source, target)
        return target
