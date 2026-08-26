from __future__ import annotations


CATEGORY_OPERATIONS = {
    "workbook_sheet": """workbook.inspect workbook.list_sheets workbook.validate_structure sheet.inspect sheet.create sheet.delete sheet.rename sheet.copy sheet.set_visibility""".split(),
    "cell_range_structure": """cell.read cell.write cell.clear range.read range.write range.write_table range.append_rows range.copy range.clear range.merge range.unmerge rows.insert rows.delete columns.insert columns.delete""".split(),
    "formula": """formula.read formula.write formula.fill formula.copy formula.inspect_dependencies formula.find_errors""".split(),
    "style_layout": """style.apply style.copy style.apply_table_default number_format.apply column.set_width row.set_height freeze_panes.set auto_filter.set protection.set""".split(),
    "table": """table.read table.select table.filter table.group table.aggregate table.sort table.join table.concat table.pivot table.melt table.deduplicate table.fill_missing table.rename_fields table.describe table.value_counts table.count table.unique""".split(),
    "excel_object": """excel_table.create chart.create chart.add_series chart.set_categories chart.inspect validation.create conditional_format.create named_range.create comment.create hyperlink.create image.insert""".split(),
}

PHASE_TWO = frozenset({"table.join", "table.concat", "table.pivot", "table.melt", "table.rename_fields"})
PHASE_THREE = frozenset({
    "formula.inspect_dependencies", "formula.find_errors", "chart.add_series", "chart.set_categories", "chart.inspect",
    "validation.create", "conditional_format.create", "named_range.create", "comment.create", "image.insert",
})
ALL_OPERATIONS = tuple(op for operations in CATEGORY_OPERATIONS.values() for op in operations)
PHASE_ONE = frozenset(ALL_OPERATIONS) - PHASE_TWO - PHASE_THREE


def migration_inventory(registered: set[str]) -> dict:
    def phase(operations):
        return {"defined": len(operations), "implemented": sum(op in registered for op in operations), "missing": sorted(set(operations) - registered)}
    return {
        "defined_total": len(ALL_OPERATIONS),
        "phase_1": phase(PHASE_ONE),
        "phase_2": phase(PHASE_TWO),
        "phase_3": phase(PHASE_THREE),
    }
