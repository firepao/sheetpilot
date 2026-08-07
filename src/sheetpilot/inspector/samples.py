from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

SENSITIVE = re.compile(r"(手机|电话|身份证|证件|邮箱|email|phone|mobile|姓名)", re.I)


def mask_sample(header: str, value: Any) -> Any:
    if value is None or not SENSITIVE.search(header):
        return value
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    return text[:1] + "*" * (len(text) - 2) + text[-1:]


def infer_type(values: Iterable[Any]) -> str:
    kinds = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool): kinds.add("boolean")
        elif isinstance(value, (datetime, date)): kinds.add("date")
        elif isinstance(value, (int, float)): kinds.add("number")
        else: kinds.add("text")
    return kinds.pop() if len(kinds) == 1 else ("empty" if not kinds else "mixed")


def summarize(header: str, values: list[Any]) -> tuple[str, list[Any], float, Any, Any]:
    nonempty = [v for v in values if v is not None and v != ""]
    samples = [mask_sample(header, v) for v in nonempty[:5]]
    null_ratio = 1.0 - len(nonempty) / len(values) if values else 0.0
    comparable = [v for v in nonempty if isinstance(v, (int, float, date, datetime)) and not isinstance(v, bool)]
    return infer_type(nonempty), samples, round(null_ratio, 6), min(comparable, default=None), max(comparable, default=None)
