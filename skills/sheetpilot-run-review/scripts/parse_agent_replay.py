#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from datetime import timedelta


try:
    LOCAL_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    # Windows Python installations may not ship the IANA tzdata package.
    # Asia/Shanghai has a fixed UTC+8 offset, which is sufficient here.
    LOCAL_TZ = timezone(timedelta(hours=8))


def _jsonish(value: Any) -> Any:
    if not isinstance(value, str): return value
    text = value.strip()
    if text[:1] not in {"{", "["}: return value
    try: return json.loads(text)
    except json.JSONDecodeError: return value


def _trim(value: Any, limit: int) -> Any:
    if isinstance(value, str) and limit and len(value) > limit: return value[:limit] + f"...[truncated {len(value)-limit} chars]"
    if isinstance(value, list): return [_trim(item, limit) for item in value]
    if isinstance(value, dict): return {key: _trim(item, limit) for key, item in value.items() if key != "schema"}
    return value


def _timestamp_ms(value: Any) -> int | None:
    if not isinstance(value, (int, float)): return None
    return int(value if value > 10_000_000_000 else value * 1000)


def _iso(value: Any, tz: timezone | ZoneInfo = timezone.utc) -> str | None:
    value = _timestamp_ms(value)
    if value is None: return None
    try: return datetime.fromtimestamp(value / 1000, tz).isoformat()
    except (OSError, OverflowError, ValueError): return None


def _human_duration(value: int | float | None) -> str | None:
    if value is None: return None
    seconds = int(round(value / 1000)); hours, remainder = divmod(seconds, 3600); minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values: return None
    ordered = sorted(values)
    if len(ordered) == 1: return ordered[0]
    rank = (len(ordered) - 1) * percentile; lower = int(rank); upper = min(lower + 1, len(ordered) - 1); weight = rank - lower
    return int(round(ordered[lower] * (1 - weight) + ordered[upper] * weight))


def _duration_stats(values: list[int]) -> dict[str, Any]:
    if not values: return {"count": 0}
    average = int(round(sum(values) / len(values))) if values else None
    maximum = max(values) if values else None; p95 = _percentile(values, 0.95)
    return {key: value for key, value in {
        "count": len(values), "sum_ms": sum(values), "sum": _human_duration(sum(values)),
        "avg_ms": average, "avg": _human_duration(average), "max_ms": maximum,
        "max": _human_duration(maximum), "p95_ms": p95, "p95": _human_duration(p95),
    }.items() if value is not None}


def _normalize(raw: dict[str, Any], limit: int) -> dict[str, Any]:
    if raw.get("code") == "200" and isinstance(raw.get("data"), dict) and raw["data"].get("snapshot_data"):
        snapshot = json.loads(raw["data"]["snapshot_data"])
        roots = snapshot.get("messages") or []
        root = roots[0] if roots else {}
        messages = (root.get("exploration") or {}).get("messages") or roots
        steps = root.get("steps") or []
        metadata = {"source": "bit-agent-share", "id": raw["data"].get("id"), "name": raw["data"].get("name")}
    else:
        messages = raw.get("messages") or raw.get("conversation") or raw.get("items") or []
        steps = raw.get("steps") or raw.get("tool_calls") or []
        metadata = {"source": raw.get("source", "exported-replay"), "id": raw.get("id")}
    normalized_steps = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict): continue
        start = _timestamp_ms(step.get("timestamp") or step.get("start_ms")); end = _timestamp_ms(step.get("lastEventTimestamp") or step.get("end_ms"))
        explicit_duration = step.get("duration_ms")
        duration = int(explicit_duration) if isinstance(explicit_duration, (int, float)) else ((end - start) if start is not None and end is not None and end >= start else None)
        normalized_steps.append({key: value for key, value in {
            "index": index, "step_id": step.get("stepId") or step.get("step_id") or step.get("id"),
            "activity": step.get("activityName") or step.get("activity") or step.get("name"),
            "description": step.get("description"), "status": step.get("status"), "start_ms": start,
            "start_utc": _iso(start), "start_local": _iso(start, LOCAL_TZ), "end_ms": end, "end_utc": _iso(end), "end_local": _iso(end, LOCAL_TZ),
            "duration_ms": duration, "duration": _human_duration(duration), "inputs": _trim(_jsonish(step.get("inputs") or step.get("command")), limit),
            "outputs": _trim(_jsonish(step.get("outputs") or step.get("result") or step.get("message")), limit),
            "files": _trim(step.get("files") or step.get("clientLocalFiles"), limit),
        }.items() if value not in (None, "", [], {})})
    ordered_messages = sorted([item for item in messages if isinstance(item, dict)], key=lambda item: (_timestamp_ms(item.get("timestamp") or item.get("timestamp_ms")) or -1, item.get("messageSegmentIndex") or 0))
    normalized_messages = []
    for index, message in enumerate(ordered_messages):
        if not isinstance(message, dict): continue
        timestamp = _timestamp_ms(message.get("timestamp") or message.get("timestamp_ms")); finished = _timestamp_ms(message.get("finishedTimestamp") or message.get("finished_ms"))
        next_timestamp = _timestamp_ms(ordered_messages[index + 1].get("timestamp") or ordered_messages[index + 1].get("timestamp_ms")) if index + 1 < len(ordered_messages) else None
        duration_to_next = next_timestamp - timestamp if timestamp is not None and next_timestamp is not None and next_timestamp >= timestamp else None
        normalized_messages.append({key: value for key, value in {
            "index": index, "id": message.get("id"), "role": "agent" if message.get("role") == "robot" else message.get("role"),
            "content_type": message.get("contentType") or message.get("content_type"), "content": _trim(message.get("content"), limit),
            "timestamp_ms": timestamp, "time_utc": _iso(timestamp), "time_local": _iso(timestamp, LOCAL_TZ),
            "finished_ms": finished, "finished_utc": _iso(finished), "finished_local": _iso(finished, LOCAL_TZ),
            "duration_to_next_ms": duration_to_next, "duration_to_next": _human_duration(duration_to_next), "status": message.get("status"),
            "step_id": (message.get("step") or {}).get("stepId") if isinstance(message.get("step"), dict) else message.get("step_id"),
        }.items() if value not in (None, "", [], {})})
    timestamps = [item[key] for item in normalized_messages + normalized_steps for key in ("timestamp_ms", "finished_ms", "start_ms", "end_ms") if isinstance(item.get(key), (int, float))]
    start = min(timestamps) if timestamps else None; end = max(timestamps) if timestamps else None
    duration = end - start if start is not None and end is not None and end >= start else None
    step_durations = [int(item["duration_ms"]) for item in normalized_steps if isinstance(item.get("duration_ms"), (int, float))]
    agent_durations = [int(item["duration_to_next_ms"]) for item in normalized_messages if item.get("role") == "agent" and isinstance(item.get("duration_to_next_ms"), (int, float))]
    timing = {
        "source": "replay_timestamps" if duration is not None else "unavailable", "complete": duration is not None,
        "start_ms": start, "start_utc": _iso(start), "start_local": _iso(start, LOCAL_TZ),
        "end_ms": end, "end_utc": _iso(end), "end_local": _iso(end, LOCAL_TZ),
        "total_duration_ms": duration, "total_duration": _human_duration(duration),
        "step_count": len(normalized_steps), "message_count": len(normalized_messages),
        "step_time": _duration_stats(step_durations), "agent_response_time": _duration_stats(agent_durations),
    }
    return {"schema_version": "1.1", "replay": metadata, "timing": timing, "conversation": normalized_messages, "steps": normalized_steps}


def _essential(compact: dict[str, Any]) -> dict[str, Any]:
    steps = {item.get("step_id"): item for item in compact["steps"]}
    timeline = []
    used = set()
    for message in compact["conversation"]:
        item = {key: message[key] for key in ("role", "content", "status", "timestamp_ms") if key in message}
        step = steps.get(message.get("step_id"))
        if step:
            used.add(message.get("step_id")); item["tool"] = {key: step.get(key) for key in ("index", "step_id", "activity", "description", "status", "duration_ms") if step.get(key) is not None}
            item["tool"]["inputs"] = str(step.get("inputs", ""))[:500]; item["tool"]["result"] = str(step.get("outputs", ""))[:800]
        if item: timeline.append(item)
    for step in compact["steps"]:
        if step.get("step_id") not in used: timeline.append({"role": "tool", "tool": {key: step.get(key) for key in ("index", "step_id", "activity", "description", "status", "duration_ms", "inputs", "outputs") if step.get(key) is not None}})
    return {"schema_version": "1.1", "replay": compact["replay"], "timeline": timeline, "stats": {**compact["timing"], "tool_duration_ms": compact["timing"]["step_time"].get("sum_ms"), "agent_response_duration_ms": compact["timing"]["agent_response_time"].get("sum_ms"), "failed_steps": sum(item.get("status") not in {None, "success", "completed", "ok"} for item in compact["steps"])}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse an Agent replay into SheetPilot scoring evidence")
    parser.add_argument("replay", type=Path); parser.add_argument("--format", choices=["essential", "compact"], default="essential")
    parser.add_argument("-o", "--output", type=Path); parser.add_argument("--max-string", type=int, default=0)
    args = parser.parse_args(); raw = json.loads(args.replay.read_text(encoding="utf-8")); compact = _normalize(raw, args.max_string)
    result = _essential(compact) if args.format == "essential" else compact
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output: args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(text + "\n", encoding="utf-8")
    else: print(text)
    return 0


if __name__ == "__main__": raise SystemExit(main())
