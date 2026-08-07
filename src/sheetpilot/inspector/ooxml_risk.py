from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from ..errors import ErrorCode, SheetPilotError

RISK_PARTS = {
    "vbaProject.bin": ("VBA", "high"),
    "activeX": ("ACTIVEX", "high"),
    "embeddings": ("OLE", "high"),
    "externalLinks": ("EXTERNAL_LINK", "high"),
    "connections.xml": ("DATA_CONNECTION", "high"),
    "pivotCache": ("PIVOT_CACHE", "unsupported"),
    "slicer": ("SLICER", "unsupported"),
    "model/": ("DATA_MODEL", "unsupported"),
}


def inspect_ooxml(path: Path) -> list[dict]:
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
    except BadZipFile as exc:
        raise SheetPilotError(ErrorCode.INPUT_INVALID, "输入不是有效的 OOXML ZIP 文件") from exc
    found = []
    for marker, (kind, severity) in RISK_PARTS.items():
        matches = [name for name in names if marker.lower() in name.lower()]
        if matches:
            found.append({"type": kind, "severity": severity, "parts": matches[:10]})
    return found
