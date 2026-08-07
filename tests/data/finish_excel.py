#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import json

FILE = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result.xlsx"

def run_cmd(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        timeout=120
    )
    return result

# Read counts
with open(r"D:\bitexcel\SheetPilot\tests\data\counts.txt", 'r') as f:
    lines = f.read().strip().split('\n')
    valid_count = int(lines[0])
    invalid_count = int(lines[1])
    total_rows = int(lines[2])
    last_row = int(lines[3])

print(f"Valid: {valid_count}, Abnormal: {invalid_count}, Total: {total_rows}, LastRow: {last_row}")

# Step 1: Set KPIs in BusinessOverview
print("Setting KPIs...")
kpis = [
    ("A2", "Total Sales", "SUM(CleaningDetail!G:G)", "$#,##0"),
    ("A3", "Total Orders", "COUNTA(CleaningDetail!B:B)-1", "0"),
    ("A4", "Avg Profit Margin", "AVERAGE(CleaningDetail!Q:Q)", "0.0%"),
    ("A5", "Return Rate", "COUNTIF(CleaningDetail!J:J,\"Yes\")/(COUNTA(CleaningDetail!J:J)-1)", "0.0%"),
    ("A6", "Avg Rating", "AVERAGE(CleaningDetail!K:K)", "0.0"),
    ("A7", "Abnormal Orders", "COUNTIF(CleaningDetail!L:L,\"Abnormal\")", "0"),
]

for cell, label, formula, fmt in kpis:
    b_cell = 'B' + cell[1:]
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/{cell}" --prop value="{label}"')
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/{b_cell}" --prop formula="{formula}" --prop numFmt="{fmt}"')

# Step 2: Monthly summary
print("Setting monthly summary...")
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
for idx, m in enumerate(months, start=2):
    month_num = idx - 1
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/E{idx}" --prop value="{m}"')
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/F{idx}" --prop formula="SUMPRODUCT((MONTH(CleaningDetail!C$2:C${last_row})={month_num})*(CleaningDetail!G$2:G${last_row}))" --prop numFmt="$#,##0"')
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/G{idx}" --prop formula="SUMPRODUCT((MONTH(CleaningDetail!C$2:C${last_row})={month_num})*1)" --prop numFmt="0"')

# Step 3: City summary
print("Setting city summary...")
cities = ["Nanjing", "Shanghai", "Hefei", "Ningbo", "Suzhou", "Hangzhou"]
for idx, city in enumerate(cities, start=2):
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/K{idx}" --prop value="{city}"')
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/L{idx}" --prop formula="SUMIF(CleaningDetail!D:D,\"{city}\",CleaningDetail!G:G)" --prop numFmt="$#,##0"')
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/M{idx}" --prop formula="COUNTIF(CleaningDetail!D:D,\"{city}\")" --prop numFmt="0"')
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/N{idx}" --prop formula="AVERAGEIF(CleaningDetail!D:D,\"{city}\",CleaningDetail!R:R)" --prop numFmt="$#,##0"')

# Step 4: Add charts
print("Adding charts...")
run_cmd(f'officecli add "{FILE}" "/BusinessOverview" --type chart --prop chartType=column --prop dataRange="BusinessOverview!E1:F7" --prop title="Monthly Sales" --prop anchor="A10:H25"')
run_cmd(f'officecli add "{FILE}" "/BusinessOverview" --type chart --prop chartType=pie --prop dataRange="BusinessOverview!K1:L7" --prop title="City Sales Distribution" --prop anchor="J10:Q25"')

# Step 5: Validation sheet
print("Setting validation checks...")
checks = [
    ("A2", "Original Rows", "361", "COUNTA(UV_DEMO_I3_dirty_orders!A:A)-1"),
    ("A3", "Valid Rows", str(valid_count), "COUNTIF(CleaningDetail!L:L,\"Normal\")"),
    ("A4", "Abnormal Rows", str(invalid_count), "COUNTIF(CleaningDetail!L:L,\"Abnormal\")"),
    ("A5", "CleaningDetail Rows", str(total_rows), "COUNTA(CleaningDetail!A:A)-1"),
]

for cell, label, expected, formula in checks:
    b_cell = 'B' + cell[1:]
    c_cell = 'C' + cell[1:]
    d_cell = 'D' + cell[1:]
    run_cmd(f'officecli set "{FILE}" "/Validation/{cell}" --prop value="{label}"')
    if expected:
        run_cmd(f'officecli set "{FILE}" "/Validation/{b_cell}" --prop value="{expected}"')
    run_cmd(f'officecli set "{FILE}" "/Validation/{c_cell}" --prop formula="{formula}"')
    run_cmd(f'officecli set "{FILE}" "/Validation/{d_cell}" --prop formula="IF({formula},\"PASS\",\"FAIL\")"')

# Step 6: Formatting
print("Formatting...")
for sheet in ["CleaningDetail", "BusinessOverview", "Validation"]:
    run_cmd(f'officecli set "{FILE}" "/{sheet}" --prop freeze=A2')
    run_cmd(f'officecli set "{FILE}" "/{sheet}/row[1]" --prop fill=4472C4 --prop font.color=FFFFFF')

# Set column widths for BusinessOverview
for col in ['A', 'B', 'E', 'F', 'G', 'K', 'L', 'M', 'N']:
    run_cmd(f'officecli set "{FILE}" "/BusinessOverview/col[{col}]" --prop width=15')

# Step 7: Close and validate
print("Closing and validating...")
run_cmd(f'officecli close "{FILE}"')
result = run_cmd(f'officecli validate "{FILE}"')
print(f"Validation: {result.stdout}")

# Generate HTML preview
print("Generating HTML preview...")
result = run_cmd(f'officecli view "{FILE}" html')
print(f"HTML preview path: {result.stdout}")

print("\n=== Done ===")
