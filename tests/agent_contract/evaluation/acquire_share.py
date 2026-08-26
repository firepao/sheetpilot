#!/usr/bin/env python3
"""Acquire BitAgent share snapshots with a logged-in browser profile.

The adapter deliberately accepts only the JSON share response containing a
valid snapshot_data payload. HTML, 401 responses, and incomplete snapshots are
recorded as acquisition errors and never enter the scoring lane.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SHARE_API_MARKER = "/api/v1/share/get_share"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("missing_dependency: install playwright with `python -m pip install playwright`") from exc
    return sync_playwright


def _validate_share_payload(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "response_is_not_json_object"
    if str(payload.get("code")) not in {"200", "0"}:
        return False, f"share_api_status:{payload.get('code', 'missing')}"
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("snapshot_data"), str):
        return False, "missing_snapshot_data"
    try:
        snapshot = json.loads(data["snapshot_data"])
    except json.JSONDecodeError:
        return False, "snapshot_data_is_invalid_json"
    if not isinstance(snapshot, dict) or not (snapshot.get("messages") or snapshot.get("steps")):
        return False, "snapshot_is_incomplete"
    return True, "ok"


def acquire(url: str, scenario_key: str, run_id: str, evidence_root: Path, user_data_dir: Path, executable_path: str | None = None, timeout_ms: int = 45_000) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_share_url")
    target_dir = evidence_root.resolve() / scenario_key / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"schema_version": "1.0", "source_url": url, "scenario_key": scenario_key, "run_id": run_id, "acquired_at": datetime.now(timezone.utc).isoformat(), "status": "ERROR"}
    raw_payload: dict[str, Any] | None = None
    api_status: int | None = None
    sync_playwright = _load_playwright()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            str(user_data_dir.resolve()),
            headless=False,
            executable_path=executable_path,
            viewport={"width": 1440, "height": 1000},
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        def on_response(response):
            nonlocal raw_payload, api_status
            if SHARE_API_MARKER not in response.url:
                return
            api_status = response.status
            try:
                candidate = response.json()
            except Exception:
                return
            if isinstance(candidate, dict):
                raw_payload = candidate

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        deadline = time.monotonic() + timeout_ms / 1000
        while raw_payload is None and time.monotonic() < deadline:
            page.wait_for_timeout(250)
        if raw_payload is None:
            report.update({"status": "ERROR", "error": f"share_api_response_not_captured:http_status={api_status}"})
        else:
            valid, reason = _validate_share_payload(raw_payload)
            if valid:
                replay_path = target_dir / "replay.raw.json"
                replay_path.write_text(json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
                report.update({"status": "OK", "http_status": api_status, "replay_file": str(replay_path), "replay_sha256": _sha256(replay_path)})
            else:
                report.update({"status": "ERROR", "http_status": api_status, "error": reason})
        browser.close()
    (target_dir / "acquisition.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Acquire a BitAgent share replay using a logged-in browser profile")
    parser.add_argument("url")
    parser.add_argument("--scenario-key", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--user-data-dir", type=Path, required=True)
    parser.add_argument("--executable-path", help="Edge/Chrome executable path")
    parser.add_argument("--timeout-ms", type=int, default=45_000)
    args = parser.parse_args(argv)
    try:
        report = acquire(args.url, args.scenario_key, args.run_id, args.evidence_root, args.user_data_dir, args.executable_path, args.timeout_ms)
    except Exception as exc:
        report = {"schema_version": "1.0", "status": "ERROR", "error": str(exc)}
        print(json.dumps(report, ensure_ascii=False, indent=2)); return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
