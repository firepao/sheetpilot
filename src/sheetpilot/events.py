from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventWriter:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **payload: Any) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
