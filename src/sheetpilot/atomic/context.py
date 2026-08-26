"""ExecutionContext: 统一的执行上下文，传递给所有 Capability handler。

替代原来把 OpenPyxlEngine、results 字典和零散参数分别传递的方式。
所有 handler 统一签名：handler(ctx: ExecutionContext, params: dict, results: dict)
"""
from __future__ import annotations

from typing import Any

from ..workbook.tables import (
    TableData,
    aggregate,
    filter_rows,
    read_table,
    select_columns,
    sort_rows,
    deduplicate,
    fill_missing,
    value_counts,
    describe,
)


class ExecutionContext:
    """原子/分子 Capability handler 的统一执行上下文。

    engine:  OpenPyxlEngine，提供工作簿操作
    results: 上游步骤的 id → 输出结果映射
    """

    def __init__(self, engine: Any, results: dict[str, Any]) -> None:
        self.engine = engine
        self.results = results

    # ------------------------------------------------------------------
    # 引用解析
    # ------------------------------------------------------------------

    def get(self, ref: Any) -> Any:
        """解析步骤输出引用。

        支持两种形式：
        - {"$ref": "step_id"}  → 从 results 取上游输出
        - 其他值               → 直接返回
        """
        if isinstance(ref, dict) and "$ref" in ref:
            key = ref["$ref"]
            if key not in self.results:
                raise KeyError(f"步骤引用 '{key}' 不存在于当前结果集")
            return self.results[key]
        return ref

    # ------------------------------------------------------------------
    # 表格操作（原子）
    # ------------------------------------------------------------------

    def read_table(self, sheet: str, header_row: int, columns: dict[str, str]) -> TableData:
        return read_table(self.engine, sheet, header_row, columns)

    def filter_rows(self, table: TableData, conditions: dict) -> TableData:
        return filter_rows(table, conditions)

    def aggregate(self, table: TableData, group_by: list[str], metrics: list[dict]) -> TableData:
        return aggregate(table, group_by, metrics)

    def select_columns(self, table: TableData, fields: list[dict]) -> TableData:
        return select_columns(table, fields)

    def sort_rows(self, table: TableData, keys: list[dict]) -> TableData:
        return sort_rows(table, keys)

    def deduplicate(self, table: TableData, keys=None, keep="first") -> TableData:
        return deduplicate(table, keys, keep)

    def fill_missing(self, table: TableData, fields=None, value="") -> TableData:
        return fill_missing(table, fields, value)

    def value_counts(self, table: TableData, field: str, as_count="数量") -> TableData:
        return value_counts(table, field, as_count)

    def describe(self, table: TableData, fields=None) -> TableData:
        return describe(table, fields)

    # ------------------------------------------------------------------
    # 工作簿操作（原子）
    # ------------------------------------------------------------------

    def sheet_names(self) -> list[str]:
        return self.engine.sheet_names()

    def create_sheet(self, name: str) -> None:
        self.engine.create_sheet(name)

    def worksheet(self, name: str) -> Any:
        return self.engine.worksheet(name)

    def read_cell(self, sheet: str, row: int, column: int) -> Any:
        return self.engine.read_cell(sheet, row, column)

    def write_cell(self, sheet: str, row: int, column: int, value: Any) -> None:
        self.engine.write_cell(sheet, row, column, value)
