# SheetPilot Excel Agent 优化（文本层重构 + 字段清单直供 Agent）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans。**本执行环境未安装这两个 skill**，执行时用等价流程：每个任务派发独立子代理（Agent 工具）执行、任务间做两阶段审查；或按 executing-plans 的批执行 + 检查点方式内联执行。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 Route A 弱语义评分，改为字段清单直供 Agent 做语义判断；同时把 SKILL.md 压成决策表、把结果目录生成收进包装脚本，并实现 Binding Amendment 执行。

**Architecture:** Runtime 只保留精确匹配自动绑定 + 事实呈现（`field_inventory`）；语义判断全部交给 Agent。新增 `task_api/inventory.py` 统一清单构建（掩码、上限、表头候选探测），`runtime._bind`/`_binding_response` 重写，`_amend` 从 stub 变为完整修订协议（doc 16 §8-9）。`task-types --input` 支持请求前查询，包装脚本实现 `--auto-result-dir` 幂等五规则。

**Tech Stack:** Python 3.11+、openpyxl>=3.1、unittest（非 pytest）、argparse CLI。

**Spec:** `docs/superpowers/specs/2026-08-14-sheetpilot-excel-agent-optimization-design.md`（v2，commit 60e711c）

## Global Constraints

- 公开入口保持三个：`task-types` / `task-run` / `task-status`，不得新增第 4 个 Agent 可见命令。
- `MAX_INVENTORY_ENTRIES = 64`、`MAX_INVENTORY_BYTES = 65536`、样本最多 3 个/列、字符串样本 ≤64 字符。
- 已有 Task 的 amendment 只接受 `/bindings/<slot>` 的 candidate_id；修改原请求 field 一律拒绝并指引 `CREATE_NEW_TASK`。
- 精确匹配自动绑定、Acceptance 冻结、修订原子性、revision conflict 语义不变。
- 测试命令（在 `SheetPilot/` 目录，PowerShell 先 `$env:PYTHONPATH="src;."`）：`python -m unittest tests.<module> -v`。
- 提交信息使用 `feat:`/`refactor:`/`docs:` 前缀，并以 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 结尾。
- 黑盒纪律不变：不读源码、不读写工作簿、不碰 Runtime 状态目录。

---

### Task 1: 新建 `inventory.py`（掩码 + 上限 + 清单构建）

**Files:**
- Create: `src/sheetpilot/task_api/inventory.py`
- Test: `tests/unit/test_inventory.py`

**Interfaces:**
- Consumes: `from .contract import stable_hash`（contract.py 已有，不变）。
- Produces:
  - `read_headers(source: Path, input_sha256: str, sheet: str, header_row: int) -> list[dict[str, Any]]` —— 按列序返回该表头行全部候选条目（含 id/header/column/inferred_type/null_ratio/sample_values/neighbor_headers），KeyError 当 Sheet 不存在。
  - `cap_entries(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]` —— 施加条目数与字节数上限，返回 (裁剪后, truncated)。
  - `detect_header_candidates(ws) -> list[int]` —— 前 10 行内按 inspector/headers.py 同款评分公式（coverage×0.4 + text_ratio×0.4 + uniqueness×0.2）打分，返回得分 ≥ max(`HEADER_SCORE_FLOOR`=0.5, 最高分−`HEADER_SCORE_MARGIN`=0.1) 的行号；正常数据行不得成为候选。
  - `build_inventory(source: Path, input_sha256: str, sheet: str | None = None, header_row: int | None = None) -> dict[str, Any]` —— 返回 `{"header_candidates": [...], "field_inventory": [...], "truncated": bool, "error_code": str | None}`；`error_code == "INVENTORY_TOO_LARGE"` 仅当未带 `--sheet` 且合并后超字节上限。
  - 常量 `MAX_INVENTORY_ENTRIES = 64`、`MAX_INVENTORY_BYTES = 65536`、`MAX_SAMPLES = 3`、`MAX_SAMPLE_CHARS = 64`。

- [ ] **Step 1: 写失败测试** — 创建 `tests/unit/test_inventory.py`：

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from sheetpilot.task_api.inventory import (
    MAX_INVENTORY_BYTES, MAX_INVENTORY_ENTRIES, build_inventory, cap_entries, read_headers,
)


class InventoryTest(unittest.TestCase):
    def make_workbook(self, directory: Path, rows: list[list]) -> Path:
        source = directory / "source.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "明细"
        for row in rows: sheet.append(row)
        workbook.save(source); workbook.close()
        return source

    def test_read_headers_orders_by_column_and_masks_sensitive_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.make_workbook(Path(temporary), [
                ["净销售额", "手机号", "证件号", "邮箱"],
                [100, "13800138000", "110101199001011234", "zhangsan@example.com"],
            ])
            entries = read_headers(source, "h", "明细", 1)
            self.assertEqual([item["header"] for item in entries], ["净销售额", "手机号", "证件号", "邮箱"])
            self.assertEqual(entries[1]["sample_values"], ["138****8000"])
            self.assertEqual(entries[2]["sample_values"], ["110101********1234"])
            self.assertEqual(entries[3]["sample_values"], ["zhangsan***@example.com"])
            self.assertEqual(entries[0]["inferred_type"], "number")
            self.assertEqual(entries[0]["neighbor_headers"], ["手机号"])

    def test_candidate_id_is_stable_and_sheet_qualified(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.make_workbook(Path(temporary), [["金额"], [1]])
            first = read_headers(source, "h", "明细", 1)[0]
            second = read_headers(source, "h", "明细", 1)[0]
            self.assertEqual(first["id"], second["id"])
            self.assertTrue(first["id"].startswith("candidate-"))

    def test_cap_entries_truncates_over_entry_and_byte_limits(self):
        small = [{"id": f"candidate-{index:03d}", "header": f"列{index}", "sample_values": ["x" * 60]} for index in range(MAX_INVENTORY_ENTRIES + 5)]
        capped, truncated = cap_entries(small)
        self.assertTrue(truncated)
        self.assertLessEqual(len(capped), MAX_INVENTORY_ENTRIES)
        # 64 条 × 约 2KB 表头 ≈ 128KB > 65536，触发字节上限裁剪（条目数未超限）。
        wide = [{"id": f"candidate-{index:03d}", "header": f"超长表头{index}_" + "甲" * 600, "sample_values": [1]} for index in range(MAX_INVENTORY_ENTRIES)]
        capped, truncated = cap_entries(wide)
        self.assertTrue(truncated)
        self.assertLessEqual(len(json.dumps(capped, ensure_ascii=False).encode("utf-8")), MAX_INVENTORY_BYTES)

    def test_build_inventory_returns_header_candidates_when_ambiguous(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "multi.xlsx"
            workbook = Workbook(); sheet = workbook.active; sheet.title = "数据"
            sheet.append(["城市", "金额"]); sheet.append(["地区", "金额"]); sheet.append(["北京", 10])
            workbook.save(source); workbook.close()
            # 两行全字符串、评分并列第一 → 无法唯一确定表头行，返回全部候选。
            result = build_inventory(source, "h", sheet=None, header_row=None)
            self.assertEqual(result["error_code"], None)
            self.assertEqual([item["header_row"] for item in result["header_candidates"]], [1, 2])
            self.assertEqual(result["field_inventory"], [])
            resolved = build_inventory(source, "h", sheet=None, header_row=1)
            self.assertEqual([item["header"] for item in resolved["field_inventory"]], ["城市", "金额"])

    def test_normal_data_rows_are_not_header_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "plain.xlsx"
            workbook = Workbook(); sheet = workbook.active; sheet.title = "数据"
            sheet.append(["城市", "金额"]); sheet.append(["北京", 10]); sheet.append(["上海", 30]); sheet.append(["华南", 20])
            workbook.save(source); workbook.close()
            # 数据行 ["北京", 10] 的评分（0.8）低于表头行（1.0）且超出 margin，不得成为候选。
            result = build_inventory(source, "h", sheet=None, header_row=None)
            self.assertEqual(result["header_candidates"], [])
            self.assertEqual([item["header"] for item in result["field_inventory"]], ["城市", "金额"])

    def test_build_inventory_errors_when_multisheet_over_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "wide.xlsx"
            workbook = Workbook()
            for name in ("甲", "乙", "丙"):
                sheet = workbook.create_sheet(name)
                sheet.append([f"列{index}_" + "甲" * 600 for index in range(40)])
                sheet.append([1] * 40)
            workbook.save(source); workbook.close()
            # 每 Sheet 约 74KB（超字节上限、触发单 Sheet 截断）；三 Sheet 合并仍超 → 要求收窄。
            result = build_inventory(source, "h", sheet=None, header_row=1)
            self.assertEqual(result["error_code"], "INVENTORY_TOO_LARGE")
            single = build_inventory(source, "h", sheet="甲", header_row=1)
            self.assertEqual(single["error_code"], None)
            self.assertTrue(single["truncated"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.unit.test_inventory -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'sheetpilot.task_api.inventory'`）

- [ ] **Step 3: 实现 `src/sheetpilot/task_api/inventory.py`**

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .contract import stable_hash

MAX_INVENTORY_ENTRIES = 64
MAX_INVENTORY_BYTES = 65536
MAX_SAMPLES = 3
MAX_SAMPLE_CHARS = 64

_PHONE = re.compile(r"^1\d{10}$")
_ID_CARD = re.compile(r"^\d{17}[\dXx]$")
_EMAIL = re.compile(r"^([^@]{1,8})[^@]*(@.+)$")


def _mask_sensitive(value: str) -> str:
    if _PHONE.match(value):
        return value[:3] + "****" + value[-4:]
    if _ID_CARD.match(value):
        return value[:6] + "********" + value[-4:]
    match = _EMAIL.match(value)
    if match:
        return match.group(1) + "***" + match.group(2)
    return value


def _sample_values(non_empty: list[Any]) -> list[Any]:
    samples: list[Any] = []
    for value in non_empty[:MAX_SAMPLES]:
        if isinstance(value, str):
            value = _mask_sensitive(value[:MAX_SAMPLE_CHARS])
        samples.append(value)
    return samples


def read_headers(source: Path, input_sha256: str, sheet: str, header_row: int) -> list[dict[str, Any]]:
    """Return every column of one header row as inventory entries, in column order."""
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        ws = workbook[sheet]  # KeyError propagates when the sheet does not exist
        if ws.max_column is None or ws.max_row is None:
            ws.calculate_dimension(force=True)
        entries: list[dict[str, Any]] = []
        for column in range(1, ws.max_column + 1):
            raw = ws.cell(header_row, column).value
            if raw in (None, ""):
                continue
            header = str(raw)
            values = [ws.cell(row, column).value for row in range(header_row + 1, min(ws.max_row, header_row + 20) + 1)]
            non_empty = [value for value in values if value not in (None, "")]
            inferred = "number" if non_empty and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_empty) else "text"
            left = ws.cell(header_row, column - 1).value if column > 1 else None
            right = ws.cell(header_row, column + 1).value
            entries.append({
                "id": "candidate-" + stable_hash([input_sha256, sheet, header_row, column, header])[:8],
                "source_id": "source-001", "sheet": sheet,
                "header_row_start": header_row, "header_row_end": header_row,
                "column": get_column_letter(column), "header": header,
                "inferred_type": inferred,
                "null_ratio": round(1 - len(non_empty) / max(1, len(values)), 4),
                "sample_values": _sample_values(non_empty),
                "neighbor_headers": [str(item) for item in (left, right) if item not in (None, "")],
            })
        return entries
    finally:
        workbook.close()


def cap_entries(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    truncated = False
    if len(entries) > MAX_INVENTORY_ENTRIES:
        entries = entries[:MAX_INVENTORY_ENTRIES]
        truncated = True
    while entries and len(json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_INVENTORY_BYTES:
        entries.pop()
        truncated = True
    return entries, truncated


HEADER_SCORE_FLOOR = 0.5
HEADER_SCORE_MARGIN = 0.1


def _header_row_score(ws, row: int, max_col: int) -> float:
    # Same scoring formula as inspector/headers.py detect_headers:
    # coverage * 0.4 + text ratio * 0.4 + uniqueness * 0.2. Kept inline to
    # avoid the inspector's models dependency; keep in sync when it changes.
    values = [ws.cell(row, col).value for col in range(1, max_col + 1)]
    present = [value for value in values if value not in (None, "")]
    if not present:
        return 0.0
    text_ratio = sum(isinstance(value, str) for value in present) / len(present)
    uniqueness = len({str(value) for value in present}) / len(present)
    return len(present) / max(max_col, 1) * 0.4 + text_ratio * 0.4 + uniqueness * 0.2


def detect_header_candidates(ws) -> list[int]:
    """Rows whose header score is within HEADER_SCORE_MARGIN of the best row."""
    max_col = min(ws.max_column or 0, 200)
    scored = [(row, _header_row_score(ws, row, max_col)) for row in range(1, min(ws.max_row or 1, 10) + 1)]
    best = max(scored, key=lambda pair: pair[1])
    if best[1] < HEADER_SCORE_FLOOR:
        return []
    return [row for row, score in scored if score >= best[1] - HEADER_SCORE_MARGIN]


def _inventory_for_sheet(workbook, source: Path, input_sha256: str, sheet: str, header_row: int | None) -> dict[str, Any]:
    ws = workbook[sheet]
    if ws.max_row is None or ws.max_column is None:
        ws.calculate_dimension(force=True)
    if header_row is None:
        candidates = detect_header_candidates(ws)
        if len(candidates) != 1:
            return {"header_candidates": [{"sheet": sheet, "header_row": row, "confidence": 1.0, "evidence": ["header_candidate_detected"]} for row in candidates], "field_inventory": [], "truncated": False}
        header_row = candidates[0]
    entries, truncated = cap_entries(read_headers(source, input_sha256, sheet, header_row))
    return {"header_candidates": [], "field_inventory": entries, "truncated": truncated}


def build_inventory(source: Path, input_sha256: str, sheet: str | None = None, header_row: int | None = None) -> dict[str, Any]:
    """Read-only inventory of visible sheets. error_code is set only when a narrowable query overflowed."""
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        visible = [name for name in workbook.sheetnames if workbook[name].sheet_state == "visible"]
        groups = [_inventory_for_sheet(workbook, source, input_sha256, name, header_row) for name in (visible if sheet is None else [name for name in visible if name == sheet])]
        result: dict[str, Any] = {"header_candidates": [], "field_inventory": [], "truncated": False, "error_code": None}
        for group in groups:
            result["header_candidates"].extend(group["header_candidates"])
            result["field_inventory"].extend(group["field_inventory"])
            result["truncated"] = result["truncated"] or group["truncated"]
        if sheet is None and groups:
            merged, _ = cap_entries(result["field_inventory"])
            if merged != result["field_inventory"]:
                return {"header_candidates": [], "field_inventory": [], "truncated": False, "error_code": "INVENTORY_TOO_LARGE"}
        if sheet is not None and groups and not groups[0]["field_inventory"] and groups[0]["header_candidates"]:
            result["header_candidates"] = groups[0]["header_candidates"]
        return result
    finally:
        workbook.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.unit.test_inventory -v`
Expected: 6 tests PASS

- [ ] **Step 5: 提交**

```bash
git add src/sheetpilot/task_api/inventory.py tests/unit/test_inventory.py
git commit -m "feat: add deterministic field-inventory builder with masking and caps

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Runtime 绑定重写（删 Route A，`field_inventory` 上线）

**Files:**
- Modify: `src/sheetpilot/task_api/runtime.py`（删 23-61 行评分常量与函数；重写 `_bind` 158-205；重写 `_binding_response` 292-300；`_create_and_run` 152-155 行不动的部分保持）
- Test: `tests/integration/test_task_api.py`（替换 78-122 行两个 Route A 测试）

**Interfaces:**
- Consumes: `from .inventory import cap_entries, read_headers`（Task 1）。
- Produces: `binding` dict 新增键 `"inventory"`（裁剪后的全部条目）与 `"truncated"`（bool）；`NEEDS_BINDING` 响应键从 `binding_candidates` 改为 `field_inventory`（+ 可选 `truncated`）。

- [ ] **Step 1: 定位全部 Route A 引用**

Run: `grep -rn "_score_header\|_semantic_candidates\|SEMANTIC_CANDIDATE_FLOOR\|binding_candidates" src tests skills --include="*.py"`
Expected: 命中点仅为 runtime.py 自身与 `tests/integration/test_task_api.py` 78-122 行；若有其他命中，先在本任务一并处理。

- [ ] **Step 2: 重写集成测试为失败态** — 替换 `tests/integration/test_task_api.py` 78-122 行两个测试：

```python
    def test_fuzzy_field_needs_binding_with_inventory_then_amendment_resolves(self):
        source = self.root / "net_sales.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "交易流水"
        sheet.append(["净销售额", "数量"]); sheet.append([100, 1]); sheet.append([200, 2]); sheet.append([300, 3])
        workbook.save(source); workbook.close()
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(source); request["output_file"] = str(self.root / "net-result.xlsx")
        request["source"] = {"sheet": "交易流水", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "net", "field": "净销售收入", "output_name": "净销售收入"}]
        request["metrics"] = [{"id": "total", "function": "sum", "field": "净销售收入", "output_name": "合计"}]
        request["output"] = {"sheet": "汇总", "anchor": "A1", "sort": []}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["net"]
        request["acceptance"]["required_metrics"] = ["total"]
        request["acceptance"]["required_sort"] = []
        result = self.runtime.run(request)
        self.assertEqual(result["status"], "NEEDS_BINDING")
        slot = result["binding_slots"][0]
        self.assertEqual(slot["status"], "UNRESOLVED")
        inventory = result["field_inventory"]
        self.assertEqual(slot["candidate_ids"], [item["id"] for item in inventory])
        net_entry = next(item for item in inventory if item["header"] == "净销售额")
        self.assertNotIn("confidence", net_entry)
        self.assertNotIn("evidence", net_entry)
        self.assertEqual(net_entry["sample_values"], [100, 200, 300])
        self.assertEqual(result["recovery"]["action"], "PROVIDE_BINDING")
        self.assertEqual(
            result["recovery"]["allowed_amendments"][0]["constraints"]["candidate_ids"],
            slot["candidate_ids"],
        )

    def test_unrelated_field_gets_inventory_without_runtime_verdict(self):
        source = self.root / "unrelated.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "交易流水"
        sheet.append(["区域"]); sheet.append(["华东"])
        workbook.save(source); workbook.close()
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(source); request["output_file"] = str(self.root / "unrelated-result.xlsx")
        request["source"] = {"sheet": "交易流水", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "region", "field": "净利润", "output_name": "净利润"}]
        request["metrics"] = [{"id": "rows", "function": "count", "mode": "rows", "output_name": "行数"}]
        request["output"] = {"sheet": "汇总", "anchor": "A1", "sort": []}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["region"]
        request["acceptance"]["required_metrics"] = ["rows"]
        request["acceptance"]["required_sort"] = []
        result = self.runtime.run(request)
        self.assertEqual(result["status"], "NEEDS_BINDING")
        self.assertEqual([item["header"] for item in result["field_inventory"]], ["区域"])
        self.assertEqual(result["recovery"]["action"], "PROVIDE_BINDING")

    def test_binding_uses_full_inventory_beyond_display_cap(self):
        source = self.root / "wide.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "宽表"
        sheet.append([f"列{index}" for index in range(1, 66)])  # 65 列，超过 64 显示上限
        sheet.append(list(range(1, 66)))
        workbook.save(source); workbook.close()
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(source); request["output_file"] = str(self.root / "wide-result.xlsx")
        request["source"] = {"sheet": "宽表", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "late", "field": "列65", "output_name": "列65"}]
        request["metrics"] = [{"id": "rows", "function": "count", "mode": "rows", "output_name": "行数"}]
        request["output"] = {"sheet": "汇总", "anchor": "A1", "sort": []}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["late"]
        request["acceptance"]["required_metrics"] = ["rows"]
        request["acceptance"]["required_sort"] = []
        result = self.runtime.run(request)
        self.assertEqual(result["status"], "RUNTIME_PASS")  # 第 65 列唯一精确匹配 → 完整清单参与机械绑定

    def test_unresolved_beyond_display_cap_returns_inventory_too_large(self):
        source = self.root / "wide.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "宽表"
        sheet.append([f"列{index}" for index in range(1, 66)])
        sheet.append(list(range(1, 66)))
        workbook.save(source); workbook.close()
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(source); request["output_file"] = str(self.root / "wide-result.xlsx")
        request["source"] = {"sheet": "宽表", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "fuzzy", "field": "不存在", "output_name": "不存在"}]
        request["metrics"] = [{"id": "rows", "function": "count", "mode": "rows", "output_name": "行数"}]
        request["output"] = {"sheet": "汇总", "anchor": "A1", "sort": []}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["fuzzy"]
        request["acceptance"]["required_metrics"] = ["rows"]
        request["acceptance"]["required_sort"] = []
        result = self.runtime.run(request)
        self.assertEqual(result["status"], "REQUEST_INVALID")
        self.assertEqual(result["error"]["code"], "INVENTORY_TOO_LARGE")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m unittest tests.integration.test_task_api -v`
Expected: 两个新测试 FAIL（`KeyError: 'field_inventory'`），其余全部 PASS（含 `test_ambiguous_exact_headers_return_needs_binding_without_attempt` 与 `test_compiler_is_byte_deterministic_and_hides_display_names`，它们不依赖被删机制）。

- [ ] **Step 4: 删除评分机制** — runtime.py：删除第 23-24 行（`SEMANTIC_CANDIDATE_FLOOR`、`_TOP_K`）与第 27-61 行（`_normalize_header`、`_character_bigrams`、`_score_header`）；模块顶部 import 区新增：

```python
from .inventory import cap_entries, read_headers
```

- [ ] **Step 5: 重写 `_bind`** — 替换 runtime.py 158-205 行为：

```python
    def _bind(self, request: dict[str, Any], input_hash: str) -> dict[str, Any]:
        requested_sheet = request["source"].get("sheet")
        if not requested_sheet:
            return {"source": None, "slots": [], "inventory": [], "truncated": False, "inventory_error": False, "unresolved": [{"kind": "source", "logical_field": None}]}
        header_row = request["source"].get("header_row", 1)
        try:
            full_entries = read_headers(Path(request["input_file"]), input_hash, requested_sheet, header_row)
        except KeyError:
            return {"source": None, "slots": [], "inventory": [], "truncated": False, "inventory_error": False, "unresolved": [{"kind": "source", "logical_field": None}]}
        # Mechanical binding runs on the FULL entry list — display caps must never
        # turn a unique exact match beyond column 64 into UNRESOLVED.
        by_header: dict[str, list[dict[str, Any]]] = {}
        for item in full_entries:
            by_header.setdefault(item["header"], []).append(item)
        slots, unresolved = [], []
        for index, (field, references) in enumerate(collect_fields(request), 1):
            matches = by_header.get(field, [])
            slot_id = f"binding-{index:03d}"
            uses = self._field_uses(request, field)
            numeric = any(use in {"metric:sum", "metric:average"} for use in uses)
            compatible = [item for item in full_entries if not numeric or item["inferred_type"] == "number"]
            exact_compatible = [item for item in matches if item in compatible]
            requirements = {"accepted_types": ["number"] if numeric else ["text", "number", "boolean", "unknown"], "uses": uses}
            if len(exact_compatible) == 1 and len(matches) == 1:
                entry = exact_compatible[0]
                slots.append({"id": slot_id, "logical_field": field, "references": references, "requirements": requirements, "status": "RESOLVED",
                              "selected_candidate_id": entry["id"], "candidate_ids": [entry["id"]],
                              "resolution": {"candidate_id": entry["id"], "sheet": requested_sheet, "header_row": header_row, "column": entry["column"], "header": entry["header"]}})
                continue
            # AMBIGUOUS: several columns share the exact header. UNRESOLVED: no exact
            # match; the agent chooses from the full type-compatible inventory itself.
            candidate_ids = [item["id"] for item in exact_compatible] if exact_compatible else [item["id"] for item in compatible]
            status = "AMBIGUOUS" if exact_compatible else "UNRESOLVED"
            slots.append({"id": slot_id, "logical_field": field, "references": references, "requirements": requirements,
                          "status": status, "selected_candidate_id": None, "candidate_ids": candidate_ids, "resolution": None})
            unresolved.append(slots[-1])
        # The response inventory is capped for display; if that hides an entry the
        # agent is authorized to choose, refuse instead of presenting a partial set.
        inventory, truncated = cap_entries(full_entries)
        visible_ids = {item["id"] for item in inventory}
        inventory_error = any(slot["candidate_ids"] and not set(slot["candidate_ids"]) <= visible_ids for slot in unresolved)
        return {"source": {"id": "source-001", "sheet": requested_sheet, "header_row": header_row}, "slots": slots, "inventory": inventory, "truncated": truncated, "inventory_error": inventory_error, "unresolved": unresolved}
```

同一步在 `_create_and_run` 中，把「revision 落盘 + NEEDS_BINDING 分支」改为先检查 `inventory_error`（现 runtime.py 150-155 行）：

```python
        if binding.get("inventory_error"):
            response = self._error("REQUEST_INVALID", "INVENTORY_TOO_LARGE", "field_binding", "字段清单超出展示上限，Agent 无法从完整候选集选择，请收窄任务后重试。", task_id, 1, None, False, "HUMAN_ACTION_REQUIRED")
            _write_json(task_dir / "current-state.json", {"state": "FAILED", "terminal": True, "request_revision": 1, "latest_attempt": None, "delivery_valid": False, "error": response["error"]})
            return response
        revision = {"request_revision": 1, "request": request, "bindings": binding, "request_revision_hash": stable_hash(request)}
        _write_json(task_dir / "revisions" / "revision-001.json", revision)
        if binding["unresolved"]:
```

- [ ] **Step 6: 重写 `_binding_response`** — 替换 runtime.py 292-300 行为：

```python
    def _binding_response(self, task_id: str, acceptance_hash: str, binding: dict[str, Any]) -> dict[str, Any]:
        unresolved = [item for item in binding["unresolved"] if item.get("id")]
        allowed = [{"op": "add", "path": f"/bindings/{item['id']}", "constraints": {"candidate_ids": item["candidate_ids"]}} for item in unresolved if item["candidate_ids"]]
        diagnostics = [{"code": "FIELD_BINDING_AMBIGUOUS" if item["status"] == "AMBIGUOUS" else "FIELD_BINDING_NOT_FOUND",
                        "path": item["references"][0], "message": f"业务字段“{item['logical_field']}”无法唯一精确绑定，请对照 field_inventory 选择候选。",
                        "expected": {"kind": "single_binding"}, "actual": {"kind": "candidates", "count": len(item["candidate_ids"])}} for item in unresolved]
        if not binding["source"]:
            diagnostics = [{"code": "SOURCE_BINDING_REQUIRED", "path": "/source/sheet", "message": "来源 Sheet 无法唯一确定。", "expected": {"kind": "existing_sheet"}, "actual": {"kind": "unresolved"}}]
        response = {"schema_version": "1.0", "status": "NEEDS_BINDING", "task_id": task_id, "request_revision": 1, "attempt_id": None,
                    "acceptance_hash": acceptance_hash, "binding_slots": unresolved, "field_inventory": binding["inventory"],
                    "diagnostics": diagnostics,
                    "recovery": {"action": "PROVIDE_BINDING", "retryable": True, "base_revision": 1, "allowed_amendments": allowed, "suggested_patch": []}}
        if binding["truncated"]:
            response["truncated"] = True
        return response
```

注意：`binding["inventory"]` 在无 sheet 分支为空列表（第 5 步代码已保证键存在）。

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m unittest tests.integration.test_task_api -v`
Expected: 全部 PASS（两个新测试只断言 NEEDS_BINDING 行为，不涉及 amendment；`_amend` 仍为 stub 不影响本任务）。

- [ ] **Step 8: 提交**

```bash
git add src/sheetpilot/task_api/runtime.py tests/integration/test_task_api.py
git commit -m "refactor: replace Route A scoring with field_inventory surfaced to the agent

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 实现 Binding Amendment 执行（doc 16 §8-9）

**Files:**
- Modify: `src/sheetpilot/task_api/runtime.py`（`_amend` 302-303 行重写）
- Test: `tests/integration/test_task_api.py`（新增修订协议测试 + 恢复 Task 2 Step 7 的断言）

**Interfaces:**
- Consumes: Task 2 的 binding 结构（`slots[].candidate_ids`、`inventory`、`unresolved`）、`self._execute(task_dir, task, revision)`（runtime.py 230 行，签名不变）。
- Produces: `_amend` 接受 envelope `{"task_id", "base_revision", "amendments": [{"op": "add"|"replace", "path": "/bindings/<slot>", "value": {"candidate_id": "<id>"}}]}`；返回 `REQUEST_INVALID`（含 REVISION_CONFLICT / CREATE_NEW_TASK 指引）或 `_execute` 的结果。

- [ ] **Step 1: 写失败测试** — 在 `tests/integration/test_task_api.py` 追加（放在新测试之后）：

```python
    def test_amendment_rejects_out_of_set_candidate_and_field_changes(self):
        source = self.root / "net_sales.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "交易流水"
        sheet.append(["净销售额"]); sheet.append([100]); sheet.append([200])
        workbook.save(source); workbook.close()
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(source); request["output_file"] = str(self.root / "net-result.xlsx")
        request["source"] = {"sheet": "交易流水", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "net", "field": "净销售收入", "output_name": "净销售收入"}]
        request["metrics"] = [{"id": "total", "function": "sum", "field": "净销售收入", "output_name": "合计"}]
        request["output"] = {"sheet": "汇总", "anchor": "A1", "sort": []}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["net"]
        request["acceptance"]["required_metrics"] = ["total"]
        request["acceptance"]["required_sort"] = []
        result = self.runtime.run(request)
        slot = result["binding_slots"][0]
        bogus = {"task_id": result["task_id"], "base_revision": 1,
                 "amendments": [{"op": "add", "path": f"/bindings/{slot['id']}", "value": {"candidate_id": "candidate-deadbeef"}}]}
        rejected = self.runtime.run(bogus)
        self.assertEqual(rejected["status"], "REQUEST_INVALID")
        self.assertEqual(rejected["error"]["recovery"]["action"], "PROVIDE_BINDING")
        field_change = {"task_id": result["task_id"], "base_revision": 1,
                        "amendments": [{"op": "replace", "path": "/dimensions/0/field", "value": {"field": "净销售额"}}]}
        rejected = self.runtime.run(field_change)
        self.assertEqual(rejected["status"], "REQUEST_INVALID")
        self.assertEqual(rejected["error"]["recovery"]["action"], "CREATE_NEW_TASK")
        net_entry = next(item for item in result["field_inventory"] if item["header"] == "净销售额")
        valid = {"task_id": result["task_id"], "base_revision": 1,
                 "amendments": [{"op": "add", "path": f"/bindings/{slot['id']}", "value": {"candidate_id": net_entry["id"]}}]}
        final = self.runtime.run(valid)
        self.assertEqual(final["status"], "RUNTIME_PASS")
        self.assertTrue(final["delivery_valid"])

    def test_amendment_conflict_and_atomicity(self):
        source = self.root / "net_sales.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "交易流水"
        sheet.append(["净销售额"]); sheet.append([100]); sheet.append([200])
        workbook.save(source); workbook.close()
        request = copy.deepcopy(MINIMAL_EXAMPLE)
        request["input_file"] = str(source); request["output_file"] = str(self.root / "net-result.xlsx")
        request["source"] = {"sheet": "交易流水", "header_row": 1}
        request["filters"] = []
        request["dimensions"] = [{"id": "net", "field": "净销售收入", "output_name": "净销售收入"}]
        request["metrics"] = [{"id": "total", "function": "sum", "field": "净销售收入", "output_name": "合计"}]
        request["output"] = {"sheet": "汇总", "anchor": "A1", "sort": []}
        request["acceptance"]["required_filters"] = []
        request["acceptance"]["required_dimensions"] = ["net"]
        request["acceptance"]["required_metrics"] = ["total"]
        request["acceptance"]["required_sort"] = []
        result = self.runtime.run(request)
        slot = result["binding_slots"][0]
        candidate_id = slot["candidate_ids"][0]
        stale = {"task_id": result["task_id"], "base_revision": 2,
                 "amendments": [{"op": "add", "path": f"/bindings/{slot['id']}", "value": {"candidate_id": candidate_id}}]}
        conflict = self.runtime.run(stale)
        self.assertEqual(conflict["error"]["code"], "REVISION_CONFLICT")
        self.assertEqual(conflict["error"]["recovery"]["base_revision"], 1)
        partial = {"task_id": result["task_id"], "base_revision": 1,
                   "amendments": [{"op": "add", "path": f"/bindings/{slot['id']}", "value": {"candidate_id": candidate_id}},
                                  {"op": "add", "path": "/bindings/binding-999", "value": {"candidate_id": candidate_id}}]}
        rejected = self.runtime.run(partial)
        self.assertEqual(rejected["status"], "REQUEST_INVALID")
        # 原子性证明：若部分修订已落盘，base_revision=1 的合法修订会 REVISION_CONFLICT。
        good = {"task_id": result["task_id"], "base_revision": 1,
                "amendments": [{"op": "add", "path": f"/bindings/{slot['id']}", "value": {"candidate_id": candidate_id}}]}
        final = self.runtime.run(good)
        self.assertEqual(final["status"], "RUNTIME_PASS")
        # 审计链（doc 16 §11.2/§12）：修订后 binding_hash 与 request_revision_hash 必变、acceptance 不变。
        revisions = Path(self.runtime.tasks_root) / result["task_id"] / "revisions"
        revision_one = json.loads((revisions / "revision-001.json").read_text(encoding="utf-8"))
        revision_two = json.loads((revisions / "revision-002.json").read_text(encoding="utf-8"))
        self.assertNotEqual(revision_one["binding_hash"], revision_two["binding_hash"])
        self.assertNotEqual(revision_one["request_revision_hash"], revision_two["request_revision_hash"])
        self.assertEqual(result["acceptance_hash"], final["acceptance_hash"])
```

若 `test_task_api.py` 顶部未导入 `json` / `from pathlib import Path`，先补上（本任务其余测试已用到两者，一般已存在）。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.integration.test_task_api -v`
Expected: 两个新测试 FAIL（`_amend` 仍返回 CAPABILITY_UNSUPPORTED，RUNTIME_PASS 与 REVISION_CONFLICT 断言均失败），其余全部 PASS。

- [ ] **Step 3: 实现 `_amend`** — 替换 runtime.py 302-303 行为：

```python
    def _amend(self, amendment: dict[str, Any]) -> dict[str, Any]:
        task_id = amendment.get("task_id")
        base_revision = amendment.get("base_revision")
        items = amendment.get("amendments")
        if not isinstance(task_id, str) or not task_id:
            return self._error("REQUEST_INVALID", "INVALID_VALUE", "field_binding", "修订必须携带 task_id。", None, base_revision, None, False, "NONE")
        task_dir = self._task_dir(task_id)
        task_path = task_dir / "task.json"; state_path = task_dir / "current-state.json"
        if not task_path.is_file() or not state_path.is_file():
            return self._error("REQUEST_INVALID", "INVALID_REFERENCE", "contract_validation", "Task 不存在。", task_id, base_revision, None, False, "NONE")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("state") != "NEEDS_BINDING":
            return self._error("REQUEST_INVALID", "INVALID_COMBINATION", "field_binding", "当前任务不在待绑定状态。", task_id, base_revision, None, False, "HUMAN_ACTION_REQUIRED")
        current_revision = state.get("request_revision", 1)
        if base_revision != current_revision:
            return self._error("REQUEST_INVALID", "REVISION_CONFLICT", "field_binding", "修订基于过期版本。", task_id, current_revision, None, True, "PROVIDE_BINDING")
        if not isinstance(items, list) or not items:
            return self._error("REQUEST_INVALID", "INVALID_VALUE", "field_binding", "amendments 必须是非空数组。", task_id, base_revision, None, False, "NONE")
        revision = json.loads((task_dir / "revisions" / f"revision-{current_revision:03d}.json").read_text(encoding="utf-8"))
        binding = revision["bindings"]
        unresolved_by_id = {slot["id"]: slot for slot in binding["unresolved"] if slot.get("id")}
        entries_by_id = {item["id"]: item for item in binding["inventory"]}
        selected: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict) or item.get("op") not in {"add", "replace"}:
                return self._error("REQUEST_INVALID", "INVALID_ENUM", "field_binding", "修订只支持 add/replace。", task_id, base_revision, None, False, "NONE")
            path = item.get("path", "")
            if not path.startswith("/bindings/"):
                # Any path outside /bindings would change frozen request components.
                return self._error("REQUEST_INVALID", "INVALID_REFERENCE", "field_binding", f"路径 {path} 会改变冻结的请求组件，请创建新 Task。", task_id, base_revision, None, False, "CREATE_NEW_TASK")
            slot_id = path.removeprefix("/bindings/")
            slot = unresolved_by_id.get(slot_id)
            if slot is None:
                return self._error("REQUEST_INVALID", "INVALID_REFERENCE", "field_binding", f"修订路径 {path} 不在允许范围内。", task_id, base_revision, None, False, "PROVIDE_BINDING")
            candidate_id = (item.get("value") or {}).get("candidate_id")
            if candidate_id not in slot["candidate_ids"] or candidate_id not in entries_by_id:
                return self._error("REQUEST_INVALID", "INVALID_VALUE", "field_binding", f"候选 {candidate_id} 不在该 Slot 的允许范围内。", task_id, base_revision, None, False, "PROVIDE_BINDING")
            entry = entries_by_id[candidate_id]
            if any(use in {"metric:sum", "metric:average"} for use in slot["requirements"]["uses"]) and entry["inferred_type"] != "number":
                return self._error("REQUEST_INVALID", "INVALID_COMBINATION", "field_binding", "候选类型不满足 Slot 全部用途。", task_id, base_revision, None, False, "PROVIDE_BINDING")
            selected[slot_id] = candidate_id
        if set(selected) != set(unresolved_by_id):
            return self._error("REQUEST_INVALID", "INVALID_COMBINATION", "field_binding", "一次修订必须解决全部待绑定 Slot。", task_id, base_revision, None, False, "PROVIDE_BINDING")
        new_revision = current_revision + 1
        for slot_id, candidate_id in selected.items():
            slot = unresolved_by_id[slot_id]; entry = entries_by_id[candidate_id]
            slot["status"] = "RESOLVED"; slot["selected_candidate_id"] = candidate_id
            slot["resolution"] = {"candidate_id": candidate_id, "sheet": entry["sheet"], "header_row": entry["header_row_start"], "column": entry["column"], "header": entry["header"]}
        binding["unresolved"] = []
        # doc 16 §11.2/§12：修订后 request_revision_hash 与 binding_hash 必须改变，
        # acceptance_hash 不变（task.json 未动）。hash 定义集中在 _revision_hashes。
        binding_hash, request_revision_hash = self._revision_hashes(revision["request"], binding, new_revision)
        next_revision = {"request_revision": new_revision, "request": revision["request"], "bindings": binding,
                         "binding_hash": binding_hash, "request_revision_hash": request_revision_hash}
        _write_json(task_dir / "revisions" / f"revision-{new_revision:03d}.json", next_revision)
        return self._execute(task_dir, task, next_revision)
```

同一步新增 `_revision_hashes` 方法（放在 `_amend` 之后），并同步修改 `_create_and_run` 第 150 行（revision-001 用同一 hash 定义）：

```python
    def _revision_hashes(self, request: dict[str, Any], binding: dict[str, Any], revision_number: int) -> tuple[str, str]:
        # doc 16 §12 binding snapshot 形状：source + slot→candidate 映射（只含最终执行事实）。
        snapshot = {"source": binding["source"], "bindings": {slot["id"]: slot["selected_candidate_id"] for slot in binding["slots"] if slot.get("selected_candidate_id")}}
        return stable_hash(snapshot), stable_hash([revision_number, request, snapshot])
```

```python
        binding_hash, request_revision_hash = self._revision_hashes(request, binding, 1)
        revision = {"request_revision": 1, "request": request, "bindings": binding, "binding_hash": binding_hash, "request_revision_hash": request_revision_hash}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.integration.test_task_api -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/sheetpilot/task_api/runtime.py tests/integration/test_task_api.py
git commit -m "feat: implement binding amendment execution with revision conflict protection

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `task-types --input` 请求前清单查询

**Files:**
- Modify: `src/sheetpilot/task_api/runtime.py`（`task_types` 91-92 行扩展签名）
- Modify: `src/sheetpilot/agent_cli.py`（task-types 子命令加参数）
- Test: `tests/integration/test_task_api.py`（新增运行时级测试）、`tests/integration/test_skill.py`（新增 CLI 级测试）

**Interfaces:**
- Consumes: `build_inventory`（Task 1）。
- Produces: `TaskRuntime.task_types(input_file: str | None = None, sheet: str | None = None, header_row: int | None = None) -> dict[str, Any]` —— 无 `input_file` 时行为与现在完全一致；有则返回 manifest + `input_profile`；查询错误统一走 `_query_error(code, message, action, allowed)`。

- [ ] **Step 1: 写失败测试** — `tests/integration/test_task_api.py` 追加：

```python
    def test_task_types_with_input_returns_manifest_plus_inventory(self):
        source = self.root / "net_sales.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "交易流水"
        sheet.append(["净销售额", "数量"]); sheet.append([100, 1]); sheet.append([200, 2])
        workbook.save(source); workbook.close()
        result = self.runtime.task_types(str(source), sheet="交易流水", header_row=1)
        self.assertEqual(result["task_types"][0]["name"], "summarize_table")
        profile = result["input_profile"]
        self.assertEqual(profile["input_file"], str(source))
        self.assertEqual(len(profile["input_sha256"]), 64)
        self.assertEqual([item["header"] for item in profile["field_inventory"]], ["净销售额", "数量"])
        self.assertEqual(profile["truncated"], False)
        unchanged = self.runtime.task_types()
        self.assertNotIn("input_profile", unchanged)

    def test_task_types_with_input_errors(self):
        missing = self.runtime.task_types(str(self.root / "nope.xlsx"))
        self.assertEqual(missing["status"], "REQUEST_INVALID")
        self.assertEqual(missing["error"]["code"], "INPUT_NOT_FOUND")
        self.assertEqual(missing["error"]["recovery"]["action"], "HUMAN_ACTION_REQUIRED")
        self.assertEqual(missing["error"]["retryable"], False)
        source = self.root / "sheet-check.xlsx"
        workbook = Workbook(); sheet = workbook.active; sheet.title = "数据"; sheet.append(["金额"]); sheet.append([1])
        workbook.save(source); workbook.close()
        bad_sheet = self.runtime.task_types(str(source), sheet="不存在的表")
        self.assertEqual(bad_sheet["error"]["code"], "INVALID_VALUE")
        recovery = bad_sheet["error"]["recovery"]
        self.assertEqual(recovery["action"], "AMEND_REQUEST")
        self.assertTrue(recovery["retryable"])
        sheet_amend = next(a for a in recovery["allowed_amendments"] if a["path"] == "/query/sheet")
        self.assertEqual(sheet_amend["constraints"]["enum"], ["数据"])
        bad_row = self.runtime.task_types(str(source), sheet="数据", header_row=0)
        row_amend = next(a for a in bad_row["error"]["recovery"]["allowed_amendments"] if a["path"] == "/query/header_row")
        self.assertEqual(row_amend["constraints"]["min"], 1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.integration.test_task_api -v`
Expected: 新测试 FAIL（`task_types() takes 1 positional argument`）。

- [ ] **Step 3: 实现 runtime.task_types** — 替换 runtime.py 91-92 行，并新增 `_query_error` 辅助方法（查询错误走 doc 14 的可重试修正协议：`op=replace`、路径为 `/query/sheet` / `/query/header_row`；不可修正的错误才用 `HUMAN_ACTION_REQUIRED`，不再出现 retryable=false + 空 allowed_amendments 的矛盾组合）：

```python
    def _query_error(self, code: str, message: str, action: str = "AMEND_REQUEST",
                     allowed: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        # task-types --input 是纯只读查询：无 task_id、无 base_revision；
        # 参数修正协议见 doc 14 修订（/query/sheet 用可见 Sheet 枚举，/query/header_row 用 min=1）。
        retryable = action == "AMEND_REQUEST"
        return {"schema_version": "1.0", "status": "REQUEST_INVALID", "task_id": None,
                "request_revision": None, "attempt_id": None,
                "error": {"code": code, "phase": "workbook_inspection", "message": message, "retryable": retryable,
                          "diagnostics": [{"code": code, "path": None, "message": message}],
                          "recovery": {"action": action, "retryable": retryable,
                                       "base_revision": None, "allowed_amendments": allowed or [], "suggested_patch": []}}}

    def task_types(self, input_file: str | None = None, sheet: str | None = None, header_row: int | None = None) -> dict[str, Any]:
        manifest = task_type_manifest()
        if not input_file:
            return manifest
        source = Path(input_file).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in {".xlsx", ".xlsm"}:
            return self._query_error("INPUT_NOT_FOUND", "输入文件不存在或不是受支持的工作簿。", "HUMAN_ACTION_REQUIRED")
        if header_row is not None and header_row < 1:
            return self._query_error("INVALID_VALUE", "header_row 必须是大于等于 1 的整数。",
                                     allowed=[{"op": "replace", "path": "/query/header_row", "constraints": {"min": 1}}])
        if sheet is not None:
            from openpyxl import load_workbook
            workbook = load_workbook(source, read_only=True, data_only=True)
            try:
                visible = [name for name in workbook.sheetnames if workbook[name].sheet_state == "visible"]
            finally:
                workbook.close()
            if sheet not in visible:
                return self._query_error("INVALID_VALUE", "Sheet 不存在或不可见。",
                                         allowed=[{"op": "replace", "path": "/query/sheet", "constraints": {"enum": visible}}])
        input_sha256 = sha256_file(source)
        profile = build_inventory(source, input_sha256, sheet=sheet, header_row=header_row)
        if profile["error_code"] == "INVENTORY_TOO_LARGE":
            from openpyxl import load_workbook
            workbook = load_workbook(source, read_only=True, data_only=True)
            try:
                visible = [name for name in workbook.sheetnames if workbook[name].sheet_state == "visible"]
            finally:
                workbook.close()
            return self._query_error("INVENTORY_TOO_LARGE", "字段清单超出上限，请用 --sheet/--header-row 收窄查询。",
                                     allowed=[{"op": "replace", "path": "/query/sheet", "constraints": {"enum": visible}},
                                              {"op": "replace", "path": "/query/header_row", "constraints": {"min": 1}}])
        result = copy.deepcopy(manifest)
        result["input_profile"] = {"input_file": str(source), "input_sha256": input_sha256,
                                   "header_candidates": profile["header_candidates"],
                                   "field_inventory": profile["field_inventory"], "truncated": profile["truncated"]}
        return result
```

同时把 runtime.py 顶部 import 区补上 `from .inventory import build_inventory, cap_entries, read_headers`（Task 2 已导入后两项，此处合并为一行）。

- [ ] **Step 4: agent_cli.py 加参数** — 替换 `build_parser` 中 task-types 子命令定义：

```python
    types = commands.add_parser("task-types", help="Return the complete public Task Contract")
    types.add_argument("--input", required=False)
    types.add_argument("--sheet", required=False)
    types.add_argument("--header-row", required=False, type=int)
```

并把 main 中 task-types 分支改为：

```python
    if args.command == "task-types":
        result = runtime.task_types(args.input, args.sheet, args.header_row)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m unittest tests.integration.test_task_api -v`
Expected: 全部 PASS

- [ ] **Step 6: 新增 CLI 级测试** — `tests/integration/test_skill.py` 追加：

```python
    def test_task_types_with_input_flag_returns_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "source.xlsx"
            wb = Workbook(); ws = wb.active; ws.title = "数据"; ws.append(["城市", "金额"]); ws.append(["北京", 10])
            wb.save(source); wb.close()
            result = self.run_cli("task-types", "--input", str(source), "--sheet", "数据", "--header-row", "1")
            self.assertEqual(result["task_types"][0]["name"], "summarize_table")
            self.assertEqual([item["header"] for item in result["input_profile"]["field_inventory"]], ["城市", "金额"])
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m unittest tests.integration.test_skill -v`
Expected: 8 tests PASS

- [ ] **Step 8: 提交**

```bash
git add src/sheetpilot/task_api/runtime.py src/sheetpilot/agent_cli.py tests/integration/test_task_api.py tests/integration/test_skill.py
git commit -m "feat: add pre-request field inventory via task-types --input

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 包装脚本 `--auto-result-dir`（幂等五规则）

**Files:**
- Modify: `skills/sheetpilot-excel-agent/scripts/sheetpilot_cli.py`
- Test: `tests/integration/test_skill.py`（新增 3 个测试）

**Interfaces:**
- Consumes: `find_root()`（本文件 11-25 行，不变）。
- Produces: 包装脚本拦截 `task-run` 的 `--auto-result-dir <父目录>` 与 `--scenario-id <id>`（可选，默认 `"sheetpilot"`；必须匹配 `^[A-Za-z0-9_-]+$`）参数；替换请求中 `<AUTO-RESULT-DIR>` 占位符后委托给 agent_cli，并在 exit 0 的任意响应 JSON（含 `REQUEST_INVALID`）上附加 `generated_result_dir`；替换后的请求写临时文件、finally 删除。`_substitute_result_dir` 返回 `(effective, generated, temp_path) | None`。

- [ ] **Step 1: 写失败测试** — `tests/integration/test_skill.py` 追加：

```python
    def test_auto_result_dir_generates_once_and_retry_reuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / "source.xlsx"; parent = root / "results"; request_path = root / "request.json"
            self.state_root = root / "state"
            wb = Workbook(); ws = wb.active; ws.title = "数据"; ws.append(["城市", "金额"]); ws.append(["北京", 10]); ws.append(["上海", 30]); wb.save(source); wb.close()
            # 首次请求故意契约无效（未知 task_type）：目录生成仍发生，generated_result_dir 附加在 REQUEST_INVALID 响应上（spec 3.2 规则 3）。
            request = {"schema_version": "1.0", "task_type": "no_such_type", "input_file": str(source), "output_file": "<AUTO-RESULT-DIR>/summary.xlsx",
                       "user_request": "按城市汇总金额", "source": {"sheet": "数据", "header_row": 1}, "filters": [],
                       "dimensions": [{"id": "city", "field": "城市", "output_name": "城市"}],
                       "metrics": [{"id": "amount", "function": "sum", "field": "金额", "output_name": "总额"}],
                       "output": {"sheet": "汇总", "anchor": "A1", "sort": [{"by": "amount", "direction": "desc"}]},
                       "acceptance": {"required_filters": [], "required_dimensions": ["city"], "required_metrics": ["amount"], "required_sort": [{"by": "amount", "direction": "desc"}]}}
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            first = self.run_cli("task-run", "--request", str(request_path), "--auto-result-dir", str(parent), "--scenario-id", "S9")
            self.assertEqual(first["status"], "REQUEST_INVALID")
            generated = Path(first["generated_result_dir"])
            self.assertTrue(generated.is_dir())
            self.assertRegex(generated.name, r"^S9__\d{8}T\d{6}\+0800__run-[0-9a-f]{6}$")
            self.assertEqual(len(list(parent.iterdir())), 1)
            # 修复后复用真实路径重提：契约无效的首次提交不会创建 Task（无去重命中），
            # 第二次提交为首次有效提交 → 正常执行成功；不再生成第二个目录，也不附加 generated_result_dir。
            request["task_type"] = "summarize_table"
            request["output_file"] = str(generated / "summary.xlsx")
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            second = self.run_cli("task-run", "--request", str(request_path))
            self.assertEqual(second["status"], "RUNTIME_PASS")
            self.assertNotIn("generated_result_dir", second)
            self.assertTrue((generated / "summary.xlsx").is_file())
            self.assertEqual(len(list(parent.iterdir())), 1)
            del self.state_root
```

```python
    def test_auto_result_dir_rejects_amendment_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); request_path = root / "request.json"
            request_path.write_text(json.dumps({"task_id": "task-abc", "base_revision": 1, "amendments": [],
                                                "output_file": "<AUTO-RESULT-DIR>/x.xlsx"}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(CLI), "task-run", "--request", str(request_path), "--auto-result-dir", str(root)],
                                    cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "REQUEST_INVALID")
            request_path.write_text(json.dumps({"schema_version": "1.0", "task_type": "summarize_table", "input_file": "x",
                                                "output_file": "<AUTO-RESULT-DIR>/../escape.xlsx"}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(CLI), "task-run", "--request", str(request_path), "--auto-result-dir", str(root)],
                                    cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "REQUEST_INVALID")
            self.assertFalse((root / ".." / "escape.xlsx").exists())
```

```python
    def test_auto_result_dir_rejects_scenario_id_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); request_path = root / "request.json"
            request_path.write_text(json.dumps({"schema_version": "1.0", "task_type": "summarize_table", "input_file": "x",
                                                "output_file": "<AUTO-RESULT-DIR>/summary.xlsx"}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(CLI), "task-run", "--request", str(request_path),
                                     "--auto-result-dir", str(root), "--scenario-id", "..\\escape"],
                                    cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "REQUEST_INVALID")
            self.assertEqual(payload["error"]["code"], "INVALID_VALUE")
            # 未创建任何目录：root 下只有 request.json。
            self.assertEqual(len(list(root.iterdir())), 1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.integration.test_skill -v`
Expected: 新测试 FAIL（当前包装脚本直接把 `--auto-result-dir` 透传给 agent_cli → argparse 报 unknown argument，`run_cli` 断言 returncode==0 失败）。

- [ ] **Step 3: 实现包装脚本** — 整体替换 `skills/sheetpilot-excel-agent/scripts/sheetpilot_cli.py`：

```python
#!/usr/bin/env python3
"""Locate SheetPilot and delegate only to the Agent-facing Task API.

The wrapper also owns <AUTO-RESULT-DIR> substitution: it generates the result
directory exactly once per initial request and attaches generated_result_dir
to the JSON response so retries reuse it (spec 3.2 idempotency rules).
"""

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

AUTO_RESULT_PLACEHOLDER = "<AUTO-RESULT-DIR>"
SCENARIO_ID = re.compile(r"^[A-Za-z0-9_-]+$")


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


def _reject(message: str) -> None:
    print(json.dumps({"schema_version": "1.0", "status": "REQUEST_INVALID", "task_id": None,
                      "error": {"code": "INVALID_VALUE", "phase": "contract_validation", "message": message,
                                "retryable": False,
                                "recovery": {"action": "HUMAN_ACTION_REQUIRED", "retryable": False,
                                             "base_revision": None, "allowed_amendments": [], "suggested_patch": []}}},
                     ensure_ascii=False))


def _beijing_stamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%dT%H%M%S") + "+0800"


def _generate_result_dir(parent: str, scenario_id: str) -> Path:
    directory = Path(parent).expanduser().resolve()
    for _ in range(20):
        candidate = directory / f"{scenario_id}__{_beijing_stamp()}__run-{uuid.uuid4().hex[:6]}"
        # scenario_id 已由 SCENARIO_ID 正则约束（无路径分隔符），resolve() 检查是纵深防御。
        if candidate.resolve().parent != directory:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise SystemExit(1)


def _substitute_result_dir(request_path: str, parent: str, scenario_id: str) -> tuple[str, str, str | None] | None:
    """Return (effective_request_path, generated_dir, temp_path); None after printing a rejection.

    temp_path 是写入替换后请求的临时文件（无占位符时返回原路径、temp_path 为 None），
    由 main() 在 finally 中删除，不遗留 .substituted.json。
    """
    data = json.loads(Path(request_path).read_text(encoding="utf-8"))
    output = data.get("output_file", "")
    if AUTO_RESULT_PLACEHOLDER not in output:
        return request_path, "", None
    if "task_id" in data:
        _reject("Amendment 请求不得包含 <AUTO-RESULT-DIR> 占位符，请复用首次响应的 generated_result_dir。")
        return None
    if not SCENARIO_ID.fullmatch(scenario_id):
        _reject("scenario-id 只允许字母、数字、下划线和连字符。")
        return None
    remainder = output.split(AUTO_RESULT_PLACEHOLDER, 1)[1]
    filename = remainder.lstrip("/\\")
    if not filename or any(char in filename for char in "/\\:") or filename in {".", ".."}:
        _reject("输出文件名必须是结果目录内的单层文件名。")
        return None
    generated = _generate_result_dir(parent, scenario_id)
    data["output_file"] = str(generated / filename)
    handle = tempfile.NamedTemporaryFile(prefix="sheetpilot-request-", suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        handle.write(json.dumps(data, ensure_ascii=False))
    finally:
        handle.close()
    return handle.name, str(generated), handle.name


def _flag_value(argv: list[str], flag: str) -> str | None:
    if flag not in argv:
        return None
    index = argv.index(flag)
    return argv[index + 1] if index + 1 < len(argv) else None


def main() -> int:
    root = find_root()
    sys.path.insert(0, str(root / "src"))
    from sheetpilot.agent_cli import main as sheetpilot_main

    delegated = list(sys.argv[1:])
    generated: str | None = None
    temp_request: str | None = None
    parent = _flag_value(delegated, "--auto-result-dir")
    if "task-run" in delegated and parent:
        request_index = delegated.index("--request")
        if request_index + 1 >= len(delegated):
            _reject("task-run 必须携带 --request。")
            return 0
        scenario_id = _flag_value(delegated, "--scenario-id") or "sheetpilot"
        substituted = _substitute_result_dir(delegated[request_index + 1], parent, scenario_id)
        if substituted is None:
            return 0
        effective, generated, temp_request = substituted
        # 按参数索引删除 --auto-result-dir / --scenario-id 及紧随其后的值；按值过滤会误删同值参数。
        removal = [index for index, item in enumerate(delegated) if item in ("--auto-result-dir", "--scenario-id")]
        for index in reversed(removal):
            delegated.pop(index)          # 删除标志本身
            if index < len(delegated):
                delegated.pop(index)      # 删除紧随其后的值
        request_index = delegated.index("--request")
        delegated[request_index + 1] = effective
    try:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = sheetpilot_main(delegated)
        text = buffer.getvalue().strip()
        if exit_code == 0 and generated and text:
            payload = json.loads(text)
            payload["generated_result_dir"] = generated
            print(json.dumps(payload, ensure_ascii=False))
        elif text:
            print(text)
        return exit_code
    finally:
        if temp_request:
            Path(temp_request).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.integration.test_skill -v`
Expected: 11 tests PASS。注意 `test_skill_package_contains_only_lightweight_entrypoint` 仍通过（仍只有 3 个文件）。

- [ ] **Step 5: 提交**

```bash
git add skills/sheetpilot-excel-agent/scripts/sheetpilot_cli.py tests/integration/test_skill.py
git commit -m "feat: add idempotent --auto-result-dir substitution to the skill wrapper

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: SKILL.md 重写 + test_skill.py 文本断言更新

**Files:**
- Modify: `skills/sheetpilot-excel-agent/SKILL.md`
- Test: `tests/integration/test_skill.py`（38-42 行断言更新）

**Interfaces:**
- Consumes: Task 4 的 `--input/--sheet/--header-row`、Task 5 的 `--auto-result-dir`/`generated_result_dir`、Task 2 的 `field_inventory`。
- Produces: 新版 SKILL.md（目标 ≤50 行，无 PowerShell 片段、无四段禁令）。

- [ ] **Step 1: 更新文本断言为失败态** — 替换 `test_skill.py` 35-43 行 `test_skill_exposes_only_agent_facing_task_workflow`：

```python
    def test_skill_exposes_only_agent_facing_task_workflow(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("task-types", text); self.assertIn("task-run", text); self.assertIn("task-status", text)
        self.assertIn("field_inventory", text); self.assertIn("candidate_id", text)
        self.assertIn("<AUTO-RESULT-DIR>", text); self.assertIn("generated_result_dir", text)
        self.assertIn("HUMAN_ACTION_REQUIRED", text); self.assertIn("semantic_assessment", text)
        self.assertIn("error.code", text)          # 停止门按 error.code = INTERNAL_ERROR 判断
        self.assertIn("RETRY_ATTEMPT", text)       # 决策表保留该 action 并规定停止并报告
        self.assertNotIn("yyyyMMdd", text)
        self.assertNotIn("mvp-run --input", text)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.integration.test_skill.SkillWorkflowTest.test_skill_exposes_only_agent_facing_task_workflow -v`
Expected: FAIL（现 SKILL.md 无 field_inventory/generated_result_dir 等短语，且含 yyyyMMdd）。

- [ ] **Step 3: 重写 SKILL.md** — 全文替换为：

```markdown
---
name: sheetpilot-excel-agent
description: Use SheetPilot's Agent-facing Task API to produce auditable Excel summaries from .xlsx or .xlsm files. Use for filtered grouping, sum, average, row/non-empty counts, sorting, immutable acceptance, Runtime-managed execution, and publication evidence through task-types, task-run, and task-status.
---

# SheetPilot Excel Agent

把 SheetPilot Agent API 作为唯一 Excel 执行边界。Agent 只提交业务级 Task Request；Runtime 负责字段绑定、执行、验证和发布。

## 入口

从本 SKILL.md 的绝对路径取得 `<skill-root>`，只使用包装脚本的三个子命令：

```powershell
python "<skill-root>\scripts\sheetpilot_cli.py" task-types [--input <file> [--sheet <名称>] [--header-row <行号>]]
python "<skill-root>\scripts\sheetpilot_cli.py" task-run --request "<request.json>" [--auto-result-dir "<父目录>"] [--scenario-id "<ID>"]
python "<skill-root>\scripts\sheetpilot_cli.py" task-status --task-id "<task-id>"
```

不要搜索可执行文件或读取包装脚本源码。找不到 SheetPilot 根目录（`CONFIGURATION_REQUIRED`）时本次运行结束，向用户报告。

## 循环与决策表

请求不合规是正常路径，按 recovery 指令修订即可，不要读源码自行解释错误。

| 判断（JSON Pointer） | 允许的唯一下一步 |
|---|---|
| `status = RUNTIME_PASS` | `task-status` 复核：`state=RUNTIME_PASS` + `artifact_integrity=MATCHED` + `delivery_valid=true` 三者齐备才交付 |
| `status = NEEDS_BINDING` | 对照 `field_inventory` 做语义判断 → 只从 `allowed_amendments.constraints.candidate_ids` 中选 `candidate_id` → 提交 amendment。已有 Task 不得修改原请求的 field（改字段语义须 `CREATE_NEW_TASK` 重建） |
| `status = REQUEST_INVALID / CAPABILITY_UNSUPPORTED / EXECUTION_FAILED / VALIDATION_FAILED / PUBLICATION_FAILED / INPUT_CHANGED` | 读 `error.recovery.action`：`AMEND_REQUEST` → 只按 `allowed_amendments` 修改后重提；`RETRY_ATTEMPT` → 停止并报告（Runtime 未开放重试入口，原样重试会被 submission 去重返回原状态）；`CREATE_NEW_TASK` / `HUMAN_ACTION_REQUIRED` / `NONE` → 停止并报告 |
| `error.code = INTERNAL_ERROR`（任意错误 status 下） | 立即停止，只向用户报告 |

**停止门**：`status = CONFIGURATION_REQUIRED` 或任意响应 `error.code = INTERNAL_ERROR` 出现，或任意响应的 `recovery.action` 为 `HUMAN_ACTION_REQUIRED` / `NONE`（错误响应取 `error.recovery.action`，`NEEDS_BINDING` 取顶层 `recovery.action`）→ 立即停止。

## 请求与交付

- 首次请求的输出路径写 `<AUTO-RESULT-DIR>/<文件名>.xlsx`，并带 `--auto-result-dir`；`REQUEST_INVALID` 修复重提时复用响应中的 `generated_result_dir`，直接写真实路径，不再带占位符。
- 只从 `task-types` 返回的契约构造请求；一切工作簿读写经包装脚本完成。
- 字段清单（`field_inventory` 或 `task-types --input`）是 Runtime 读表的事实，语义判断由你完成；选择后仍只能通过 `candidate_id` 落地。

## 最终报告

报告 `task_id`、`attempt_id`、`request_revision`、最终输出路径、`runtime_status`、`artifact_integrity`、`delivery_valid`、`acceptance_hash`、`internal_plan_hash`，以及独立的 `semantic_assessment` 对象（`status` 取 `accepted` / `rejected` / `not_assessed`，附 `rationale` 与 `based_on_evidence_hash`）。Runtime 结论与你的语义判断分开报告。
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest tests.integration.test_skill -v`
Expected: 11 tests PASS

- [ ] **Step 5: 提交**

```bash
git add skills/sheetpilot-excel-agent/SKILL.md tests/integration/test_skill.py
git commit -m "refactor: collapse SKILL.md into loop + decision table + report contract

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 契约描述符 + evaluator + 文档同步

**Files:**
- Modify: `src/sheetpilot/task_api/contract.py`（59 行）
- Modify: `tests/agent_contract/evaluation/evaluator.py`（注释说明）
- Test: `tests/agent_contract/test_agent_evaluation.py`（新增回归测试）
- Modify: `docs/current/16-field-binding-and-request-revision-prototype-v1.md`、`docs/current/14-machine-recoverable-error-protocol-prototype-v1.md`、`docs/current/19-agent-facing-black-box-acceptance-protocol-v1.md`、`docs/superpowers/specs/2026-08-14-sheetpilot-excel-agent-optimization-design.md`、`CLAUDE.md`

**Interfaces:**
- Consumes: 无新代码依赖。
- Produces: `field_binding` 描述符 = `"exact_header_match_with_field_inventory"`；evaluator 规则对 `task-types --input` 明确放行。

- [ ] **Step 1: 写回归锁定测试** — `tests/agent_contract/test_agent_evaluation.py` 追加（`inspect_commands` 已在第 13 行导入）：

```python
    def test_task_types_with_input_is_not_source_access(self):
        audit = inspect_commands([{"command": "python skills\\sheetpilot-excel-agent\\scripts\\sheetpilot_cli.py task-types --input data\\01_simple_department_sales.xlsx --sheet 销售明细 --header-row 1"}])
        self.assertEqual(audit["source_access_attempts"], 0)
        self.assertEqual(audit["legacy_cli_calls"], 0)
        self.assertEqual(audit["allowed_cli_calls"], 1)
```

- [ ] **Step 2: 运行测试确认通过（锁定现有行为）**

Run: `python -m unittest tests.agent_contract.test_agent_evaluation -v`
Expected: PASS。evaluator.py 第 32-33 行已豁免 `task-types` 命令（`_is_source_access` 在源码读取模式之前返回 False），本测试为回归锁定。**若意外 FAIL**（`source_access_attempts == 1`，例如 `--input` 路径本身含 `src` 段被第 18 行命中），在 evaluator.py 第 18 行 `return True` 之前插入：

```python
    if re.search(r"\b(?:task-types|task-run|task-status)\b", lower):
        return False
```

- [ ] **Step 3: 改契约描述符** — contract.py 59 行：

```python
                "field_binding": "exact_header_match_with_field_inventory",
```

- [ ] **Step 4: evaluator 明确 `--input` 放行** — 在 evaluator.py 第 17-18 行（`src|schemas` 路径检查）上方加注释，落实 spec §4 的「明确」要求（无功能变更）：

```python
    # Path segments that only exist in Runtime source. Input workbooks passed to
    # sanctioned entry points (e.g. task-types --input <workbook>) live under
    # tests/agent_contract/data and never match this -- --input is not source access.
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m unittest tests.agent_contract.test_agent_evaluation -v`
Expected: 全 PASS

- [ ] **Step 6: 更新 doc 16** — `docs/current/16-*.md`：
  - §5 示例（84-99 行）替换为：

```json
{
  "id": "candidate-8f1472c1",
  "source_id": "source-001",
  "sheet": "清洗明细",
  "header_row_start": 1,
  "header_row_end": 1,
  "column": "G",
  "header": "销售额",
  "inferred_type": "number",
  "null_ratio": 0.02,
  "sample_values": [128.5, 300, 99.9],
  "neighbor_headers": ["数量", "单价"]
}
```

  - 候选事实约束一段（111-115 行）改为：「候选即字段清单条目；无评分、无 top-K。`sample_values` 最多 3 个非空值并做敏感值掩码，字符串最多 64 个字符。清单按 Sheet/列顺序稳定排序，上限 64 条 / 64 KB，超限截断并置 `truncated`。」
  - §6（119-135 行）：删除「语义相似匹配（非精确）会被输出到 binding_candidates，每个候选带 confidence…」整段，替换为：「无精确匹配时 Runtime 返回 `field_inventory`（绑定源全部表头的清单事实），语义判断由 Agent 完成；Runtime 不依据任何相似度选择列。`UNRESOLVED` Slot 的 `candidate_ids` 为来源内全部类型兼容清单 ID，且与 `recovery.allowed_amendments.constraints.candidate_ids` 完全一致。已有 Task 的 amendment 只接受 candidate_id；修改原请求 field 会改变冻结组件定义，一律拒绝并指引 `CREATE_NEW_TASK`。」
  - §7 示例（140-189 行）：`binding_candidates` 键整体替换为 `field_inventory`（取 §5 新条目形态的数组）；`recovery.action` 改为恒为 `PROVIDE_BINDING`；删除 `"suggested_patch": []` 之外的 confidence 相关字段。
  - 末尾新增一节「字段清单数据边界」：掩码三类模式、64 条/64 KB 上限、`INVENTORY_TOO_LARGE`、`truncated` 标记、`task-types --input` 请求前查询（含 `--header-row` 与 `header_candidates` 规则）。

- [ ] **Step 7: 更新 doc 14** — 两处修改：
  - §7 示例（169-225 行）：`binding_candidates` 改为 `field_inventory`，删除 candidate-2 的 `confidence: 0.82` / `semantic_header_match`，换成无评分的清单条目；文字部分「Agent 选择 Candidate ID，不重写 Sheet、列字母和 header_row」后补一句：「Runtime 不生成语义候选；字段语义由 Agent 对照 field_inventory 判断。」
  - 末尾新增一节「请求前查询（task-types --input）的参数修正协议」：

```markdown
## 请求前查询的参数修正

`task-types --input [--sheet <名称>] [--header-row <行号>]` 是纯只读查询，不创建 Task、无 task_id 与 base_revision。查询错误仍沿用本协议的修正 shape，但 allowed_amendments 的路径域为查询参数：

- `INPUT_NOT_FOUND`（文件不存在/不受支持）：`action = HUMAN_ACTION_REQUIRED`，`retryable = false`，`allowed_amendments = []`。
- `INVALID_VALUE`（--sheet 不存在或不可见）：`action = AMEND_REQUEST`，`retryable = true`，`allowed_amendments = [{"op": "replace", "path": "/query/sheet", "constraints": {"enum": <可见 Sheet 列表>}}]`。
- `INVALID_VALUE`（--header-row < 1）：同上，路径为 `/query/header_row`，`constraints = {"min": 1}`。
- `INVENTORY_TOO_LARGE`：`action = AMEND_REQUEST`，同时给出 `/query/sheet`（enum）与 `/query/header_row`（min=1）两个修正路径。

查询修正协议与 Task 修订协议共用错误 envelope；Agent 按 path 修改对应查询参数后重发 `task-types`，不涉及 Task 状态。
```

- [ ] **Step 8: 同步 spec §3.1 决策表** — `docs/superpowers/specs/2026-08-14-sheetpilot-excel-agent-optimization-design.md` 第 47/48/50 行三处与 Task 6 新 SKILL.md 决策表对齐（评审 P1-3/P2-1 的 spec 落点）：
  - 第 47 行：`RETRY_ATTEMPT` → 原样重试 改为 `RETRY_ATTEMPT` → 停止并报告（Runtime 未开放重试入口，原样重试会被 submission 去重返回原状态）。
  - 第 48 行：`status` `INTERNAL_ERROR` 改为 `error.code` `INTERNAL_ERROR`（任意错误 status 下）。
  - 第 50 行停止门：`status ∈ {INTERNAL_ERROR, CONFIGURATION_REQUIRED}` 改为 `status = CONFIGURATION_REQUIRED 或任意响应 error.code = INTERNAL_ERROR`。

- [ ] **Step 9: 更新 doc 19** — S2 验收（172-181 行）改为：「Runtime 返回 `NEEDS_BINDING` 与 `field_inventory`，不静默自动选择任何列；Agent 对照清单语义判断后只提交 `candidate_id`；Agent 不提交 Sheet、header row 或列字母；Acceptance hash 在修订前后不变。」并在 §6 允许子命令列表后补一行：「`task-types` 的 `--input/--sheet/--header-row` 为请求前只读查询参数，属允许调用。」

- [ ] **Step 10: 更新 CLAUDE.md** — 51 行替换为：「Field binding in `runtime.py` auto-binds **only** a unique exact header match; otherwise it returns `field_inventory` (all source headers with masked samples, neighbor headers, and hard caps) and lets the agent do the semantic judgment — amendments land only via `candidate_id`. See `docs/superpowers/specs/2026-08-14-sheetpilot-excel-agent-optimization-design.md`.」

- [ ] **Step 11: 全量回归**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: 全部 PASS（含 test_skill 11 个、test_task_api 16 个、unit 5+原有、agent_contract 原有+新增）。

- [ ] **Step 12: 提交**

```bash
git add src/sheetpilot/task_api/contract.py tests/agent_contract/evaluation/evaluator.py tests/agent_contract/test_agent_evaluation.py docs/current/16-field-binding-and-request-revision-prototype-v1.md docs/current/14-machine-recoverable-error-protocol-prototype-v1.md docs/current/19-agent-facing-black-box-acceptance-protocol-v1.md docs/superpowers/specs/2026-08-14-sheetpilot-excel-agent-optimization-design.md CLAUDE.md
git commit -m "docs: sync binding protocol docs with field-inventory design

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 黑盒场景更新（H2 翻转 + S8）+ Release Gate 重跑

**Files:**
- Modify: `tests/agent_contract/sheetpilot-agent-test-cases-v1.md`（H2、新增 S8）
- Modify: `tests/agent_contract/data/05_hard_ambiguous_headers.xlsx`（按 Step 2a 口径语义重建）

**Interfaces:**
- Consumes: Task 2/3/4/5/6 的全部行为。

- [ ] **Step 1: 探针检查现有 fixture**（只读，不修改任何文件）:

```powershell
python -c "from openpyxl import load_workbook; wb=load_workbook('tests/agent_contract/data/05_hard_ambiguous_headers.xlsx', data_only=True); [print('SHEET', n, '| headers:', [ws.cell(1, c).value for c in range(1, ws.max_column + 1)], '| rows2-5:', [[ws.cell(r, c).value for c in range(1, ws.max_column + 1)] for r in range(2, 6)]) for n in wb.sheetnames for ws in [wb[n]]]"
```

无论探针结果如何都执行 Step 2a 重建：H2 的正确答案由**业务口径约定**定义，不是由旧 fixture 的偶然样本决定。

- [ ] **Step 2a: 按业务口径重建 fixture** — H2 的业务语义固定为：两列同名「销售额」，左列口径为**未税**、右列为**含税**，约定 `含税 = 未税 × 1.13`。用普通可写 openpyxl（测试数据构造，不是 Runtime/Agent 行为，不涉及黑盒纪律）重建 `tests/agent_contract/data/05_hard_ambiguous_headers.xlsx`：

```python
from openpyxl import Workbook

workbook = Workbook()
sheet = workbook.active
sheet.title = "销售明细"
sheet.append(["城市", "销售额", "销售额"])   # 两列同名：左=未税，右=含税（含税=未税×1.13）
sheet.append(["北京", 100, 113])
sheet.append(["上海", 200, 226])
sheet.append(["北京", 50, 56.5])
sheet.append(["上海", 300, 339])
workbook.save("tests/agent_contract/data/05_hard_ambiguous_headers.xlsx")
workbook.close()
```

- [ ] **Step 2b: 计算并验证 H2 Oracle** — 把下面的只读重算脚本存为仓库根的 `_probe_h2.py`（不导入 SheetPilot 任何模块，用后即删）运行：Oracle 只认口径关系——对每个城市组断言 `含税 ≈ 未税 × 1.13`，成立后取**未税列**（每组合计较小者）为正确答案：

```python
from collections import defaultdict
from openpyxl import load_workbook

wb = load_workbook("tests/agent_contract/data/05_hard_ambiguous_headers.xlsx", data_only=True)
ws = wb["销售明细"]
columns = range(2, ws.max_column + 1)
by_column = {}
for column in columns:
    totals = defaultdict(float)
    for row in range(2, ws.max_row + 1):
        key = ws.cell(row, 1).value
        totals[key] += float(ws.cell(row, column).value)
    by_column[column] = totals
untaxed = min(columns, key=lambda c: sum(by_column[c].values()))
taxed = max(columns, key=lambda c: sum(by_column[c].values()))
for key in by_column[untaxed]:
    assert abs(by_column[taxed][key] - by_column[untaxed][key] * 1.13) < 0.01, "含税/未税口径不成立"
print("未税列（正确）:", dict(by_column[untaxed]))
print("含税列:", dict(by_column[taxed]))
```

Run: `python _probe_h2.py`，然后 `del _probe_h2.py`。
Expected: 断言通过；输出未税列合计 北京 150、上海 500——记入 Step 3 的 Oracle 节。

- [ ] **Step 3: 更新测试用例文档** — `sheetpilot-agent-test-cases-v1.md`：
  - H2 的 Agent Prompt 追加口径约定句：「销售额按未税口径统计（该表两列“销售额”左列为未税，右列为含税，约定 含税 = 未税 × 1.13）。」
  - H2 的「预期行为」改为：「两列都叫“销售额”，Runtime 必须返回 `NEEDS_BINDING` 与 `field_inventory`。Agent 对照清单样本值验证 ×1.13 口径关系，语义判断后只提交 `candidate_id` 修订，不读取源码、不直接查看列字母。Acceptance hash 在修订前后不变。最终输出与 Oracle 一致（未税列：北京 150、上海 500）。预期：`RUNTIME_PASS`。」并把 H2 从「困难失败用例」移入成功用例分组。
  - 新增 S8 用例：

```text
## S8：请求前字段清单查询（语义字段一次通过）

### Agent Prompt

使用 $sheetpilot-excel-agent 处理：

输入：D:\bitexcel\SheetPilot\tests\agent_contract\data\01_simple_department_sales.xlsx
测试场景：S8
输出：D:\bitexcel\SheetPilot\tests\agent_contract\results\<AUTO-RESULT-DIR>\department_sales_s8.xlsx

根据“销售明细”，按部门汇总销售净额，输出“部门”和“销售净额”，按销售净额降序写入新工作表“部门销售汇总”。请先通过字段清单确认工作簿中的真实字段名后再构造请求。

### Oracle

- 与 S1 相同数据源，字段实际名为“销售额”：华北 6,598；华南 5,233；西南 2,859；华东 2,765。
- 预期：`RUNTIME_PASS`；Agent 先调用 `task-types --input` 取得清单，第一版请求即用精确表头，happy path CLI 调用 ≤3 次。
```

- [ ] **Step 4: 更新 §5 当前版本预期** — 把「H2、H3、H4、H5 应正确停止或失败」改为「H3、H4、H5 应正确停止或失败；H2 应通过修订成功完成；S8 应一次通过」。

- [ ] **Step 5: 全量回归确认**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add tests/agent_contract/sheetpilot-agent-test-cases-v1.md tests/agent_contract/data
git commit -m "test: flip H2 to amendment-based success and add S8 pre-request inventory scenario

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Release Gate 重跑（人工/Harness）** — 按 doc 19 §13：S1-S3、M1-M4、H1-H5、S8 全部场景各 3 次全新 Agent run；S8 3/3、其余保持原门槛；Critical Violation 总数 0。任一失败按 doc 19 §14 失败分类定位到具体责任层修复后重跑受影响场景。这一步由 Harness 完成，不在本仓库自动化测试内。

---

## Self-Review 记录

- **Spec coverage**：§3.1→Task 6；§3.2→Task 4（--input）+ Task 5（--auto-result-dir 五规则：仅首次生成/替换先于校验/复用不二次生成/拒绝路径逃逸/Amendment 不生成）；§3.3→Task 1（掩码+上限）+ Task 2（field_inventory、授权闭合）+ Task 3（candidate_id 落地、改 field 拒绝）；§3.4 路径 1/2→Task 4/2/3；§3.5→Task 4（INPUT_NOT_FOUND/INVALID_VALUE/INVENTORY_TOO_LARGE）；§4→Task 7/8；§5→各任务测试 + Task 8；§6 风险 4（H2 fixture）→Task 8 Step 1-2b；§7→Task 8 Step 7。补充项：Amendment 执行在 spec 中被隐含依赖（§3.3/完成定义 6），已单列 Task 3。
- **Placeholder scan**：无 TBD/TODO；所有步骤含可运行代码与命令。
- **Type consistency**：`read_headers`/`cap_entries`/`build_inventory`/`detect_header_candidates` 在 Task 1 定义、Task 2/4 按同签名使用；`binding["inventory"]`/`binding["truncated"]` 在 Task 2 产生、Task 3 消费；`_revision_hashes`/`_query_error` 在各自 Task 内定义并被本 Task 其余步骤与后续 Task 的测试断言引用；`generated_result_dir` 字段名在 Task 5/6/8 一致；`field_inventory` 响应键在 Task 2/4/6/7 一致。

## 评审修订记录（用户评审 11 项，全部核实后落地）

- **P1-1 清单截断破坏绑定正确性** → Task 2：`_bind` 在完整 `full_entries` 上机械绑定；64 条/64KB 上限只作用于响应展示；隐藏合法候选时 `_create_and_run` 写 FAILED 终态并返回 `INVENTORY_TOO_LARGE`（`HUMAN_ACTION_REQUIRED`，无 retryable 矛盾）。新增 65 列两个集成测试。
- **P1-2 修订审计哈希** → Task 3：新增 `_revision_hashes(request, binding, n)` 返回 `(binding_hash, request_revision_hash)`；`request_revision_hash = stable_hash([n, request, snapshot])`、snapshot = source + slot→candidate；`_create_and_run` 的 revision-001 同一定义；测试读 `revisions/revision-00X.json` 断言修订前后两 hash 均变、acceptance_hash 不变。
- **P1-3 RETRY_ATTEMPT** → 采用「停止并报告」：runtime 无重试入口（重提会被 submission 去重返回原状态）。Task 6 决策表、spec §3.1 第 47 行、test_skill 断言同步。
- **P1-4 scenario_id 路径逃逸** → Task 5：`SCENARIO_ID = ^[A-Za-z0-9_-]+$` 校验 + `_generate_result_dir` 内 `resolve()` 父目录比对；新增 `test_auto_result_dir_rejects_scenario_id_escape`。
- **P1-5 核心测试预期错误** → Task 5 首测试重写：首次请求故意契约无效（`no_such_type`）取得 `generated_result_dir`，修正后复用真实路径 → `RUNTIME_PASS`，目录数恒为 1。
- **P1-6 表头探测误判数据行** → Task 1：改为 inspector/headers.py 同款评分公式 + `HEADER_SCORE_FLOOR=0.5`/`HEADER_SCORE_MARGIN=0.1`；歧义测试重写（`["城市","金额"]`/`["地区","金额"]` → candidates [1,2]）；新增数据行不得成为候选测试；Interfaces 行同步。
- **P1-7 查询错误 recovery 自相矛盾** → Task 4：新增 `_query_error(code, message, action, allowed)`；`/query/sheet`（enum=可见 Sheet）/`/query/header_row`（min=1）修正路径；`INPUT_NOT_FOUND` → `HUMAN_ACTION_REQUIRED`；doc 14 新增「请求前查询的参数修正协议」一节。
- **P2-1 INTERNAL_ERROR 判断字段** → Task 6 决策表与停止门、spec §3.1 第 48/50 行均改为 `error.code = INTERNAL_ERROR`；test_skill 断言 `error.code`。
- **P2-2 临时文件遗留 + 按值过滤参数** → Task 5：`tempfile.NamedTemporaryFile(prefix="sheetpilot-request-", delete=False)` + `finally` 删除；按索引删除 `--auto-result-dir`/`--scenario-id` 及其值。
- **P2-3 H2 fixture 不可判定** → Task 8：业务口径固定为未税/含税 `含税=未税×1.13`；fixture 重建（两列同名销售额，右列=左列×1.13）；Oracle 脚本先断言口径关系再取未税列（北京 150、上海 500）；H2 Prompt 追加口径约定句。
- **P2-4 执行文档问题** → 头部 sub-skill 引用改为「本执行环境未安装，执行时用等价流程」注记；Task 5 首个测试缺失的闭合围栏已补；test_skill 测试数统一为 11（Task 4 为 8、Task 5/6 为 11、Task 7 全量回归为 11）。
