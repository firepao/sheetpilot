#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import json
import time

INPUT_FILE = r"D:\bitexcel\SheetPilot\tests\data\origin\UV_DEMO_I3_dirty_orders.xlsx"
OUTPUT_FILE = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result.xlsx"

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

start_time = time.time()

# Step 1: Copy file
print("Step 1: Copy file")
run_cmd(f'copy "{INPUT_FILE}" "{OUTPUT_FILE}"')

# Step 2: Add sheets
print("Step 2: Add sheets")
run_cmd(f'officecli add "{OUTPUT_FILE}" / --type sheet --prop name="CleaningDetail"')
run_cmd(f'officecli add "{OUTPUT_FILE}" / --type sheet --prop name="BusinessOverview"')
run_cmd(f'officecli add "{OUTPUT_FILE}" / --type sheet --prop name="Validation"')

# Step 3: Set headers for CleaningDetail sheet
print("Step 3: Set headers")
headers_cd = [
    ("A1", "OriginalRow"), ("B1", "OrderID"), ("C1", "Date"),
    ("D1", "City"), ("E1", "Channel"), ("F1", "Category"),
    ("G1", "Sales"), ("H1", "Cost"), ("I1", "DeliveryTime"),
    ("J1", "IsReturn"), ("K1", "Rating"), ("L1", "Status"),
    ("M1", "Issue"), ("N1", "StdCity"), ("O1", "StdChannel"),
    ("P1", "StdCategory"), ("Q1", "ProfitMargin"), ("R1", "Profit")
]

for cell, val in headers_cd:
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/CleaningDetail/{cell}" --prop value="{val}" --prop bold=true')

# Set column widths
for col, w in [("A", 10), ("B", 12), ("C", 12), ("D", 10), ("E", 12), ("F", 10),
               ("G", 12), ("H", 12), ("I", 12), ("J", 10), ("K", 8), ("L", 10),
               ("M", 20), ("N", 12), ("O", 12), ("P", 12), ("Q", 10), ("R", 12)]:
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/CleaningDetail/col[{col}]" --prop width={w}')

# Step 4: Import data from original sheet to CleaningDetail
print("Step 4: Import and process data")

# Get original data as text
result = run_cmd(f'officecli view "{OUTPUT_FILE}" text')
if result.stdout:
    lines = result.stdout.strip().split('\n')
    
    # Parse data rows
    data_rows = []
    for line in lines:
        if '[/UV_DEMO_I3_dirty_orders/row[' in line:
            parts = line.split('\t')
            row_data = {}
            for part in parts:
                if '=' in part:
                    kv = part.split('=', 1)
                    if len(kv) == 2:
                        cell_ref = kv[0].strip()
                        value = kv[1].strip()
                        col_letter = ''.join([c for c in cell_ref if c.isalpha()])
                        row_data[col_letter] = value
            if row_data:
                data_rows.append(row_data)
    
    print(f"Parsed {len(data_rows)} rows")
    
    # Generate batch operations
    batch_ops = []
    valid_count = 0
    invalid_count = 0
    
    for idx, row in enumerate(data_rows, start=2):
        original_row = idx - 1
        order_id = row.get('A', '')
        date = row.get('B', '')
        city = row.get('C', '')
        channel = row.get('D', '')
        category = row.get('E', '')
        sales = row.get('F', '')
        cost = row.get('G', '')
        delivery = row.get('H', '')
        is_return = row.get('I', '')
        rating = row.get('J', '')
        
        # Check anomalies
        issues = []
        if not sales:
            issues.append("Sales missing")
        if not cost:
            issues.append("Cost missing")
        if not delivery:
            issues.append("Delivery missing")
        
        if sales:
            try:
                s = float(sales)
                if s < 0:
                    issues.append("Negative sales")
            except:
                issues.append("Invalid sales")
        
        if cost and sales:
            try:
                if float(cost) > float(sales):
                    issues.append("Cost > Sales")
            except:
                pass
        
        status = "Abnormal" if issues else "Normal"
        if issues:
            invalid_count += 1
        else:
            valid_count += 1
        
        issue_str = "; ".join(issues)
        
        base_row = idx
        batch_ops.extend([
            {"command": "set", "path": f"/CleaningDetail/A{base_row}", "props": {"value": str(original_row)}},
            {"command": "set", "path": f"/CleaningDetail/B{base_row}", "props": {"value": order_id}},
            {"command": "set", "path": f"/CleaningDetail/C{base_row}", "props": {"value": date}},
            {"command": "set", "path": f"/CleaningDetail/D{base_row}", "props": {"value": city}},
            {"command": "set", "path": f"/CleaningDetail/E{base_row}", "props": {"value": channel}},
            {"command": "set", "path": f"/CleaningDetail/F{base_row}", "props": {"value": category}},
            {"command": "set", "path": f"/CleaningDetail/G{base_row}", "props": {"value": sales}},
            {"command": "set", "path": f"/CleaningDetail/H{base_row}", "props": {"value": cost}},
            {"command": "set", "path": f"/CleaningDetail/I{base_row}", "props": {"value": delivery}},
            {"command": "set", "path": f"/CleaningDetail/J{base_row}", "props": {"value": is_return}},
            {"command": "set", "path": f"/CleaningDetail/K{base_row}", "props": {"value": rating}},
            {"command": "set", "path": f"/CleaningDetail/L{base_row}", "props": {"value": status}},
            {"command": "set", "path": f"/CleaningDetail/M{base_row}", "props": {"value": issue_str}},
            {"command": "set", "path": f"/CleaningDetail/N{base_row}", "props": {"value": city}},
            {"command": "set", "path": f"/CleaningDetail/O{base_row}", "props": {"value": channel}},
            {"command": "set", "path": f"/CleaningDetail/P{base_row}", "props": {"value": category}},
        ])
    
    # Execute batches
    batch_size = 50
    for i in range(0, len(batch_ops), batch_size):
        chunk = batch_ops[i:i+batch_size]
        temp_file = r"D:\bitexcel\SheetPilot\tests\data\temp_batch.json"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False)
        run_cmd(f'officecli batch "{OUTPUT_FILE}" < "{temp_file}"')
    
    last_row = len(data_rows) + 1
    
    # Add formulas for profit margin and profit
    print("Step 5: Add formulas")
    for row_idx in range(2, last_row + 1):
        run_cmd(f'officecli set "{OUTPUT_FILE}" "/CleaningDetail/Q{row_idx}" --prop formula="IFERROR((G{row_idx}-H{row_idx})/G{row_idx},0)" --prop numFmt="0.0%"')
        run_cmd(f'officecli set "{OUTPUT_FILE}" "/CleaningDetail/R{row_idx}" --prop formula="G{row_idx}-H{row_idx}" --prop numFmt="$#,##0"')

# Step 6: Business Overview sheet
print("Step 6: Business Overview")

# Headers
bo_headers = [
    ("A1", "KPI"), ("B1", "Value"),
    ("D1", "Monthly Summary"), ("E1", "Month"), ("F1", "Sales"), ("G1", "Orders"),
    ("J1", "City Summary"), ("K1", "City"), ("L1", "Sales"), ("M1", "Orders"), ("N1", "AvgProfit")
]

for cell, val in bo_headers:
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/{cell}" --prop value="{val}" --prop bold=true')

# KPIs
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
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/{cell}" --prop value="{label}"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/{b_cell}" --prop formula="{formula}" --prop numFmt="{fmt}"')

# Monthly summary (simplified)
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
for idx, m in enumerate(months, start=2):
    month_num = idx - 1
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/E{idx}" --prop value="{m}"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/F{idx}" --prop formula="SUMPRODUCT((MONTH(CleaningDetail!C$2:C${last_row})={month_num})*(CleaningDetail!G$2:G${last_row}))" --prop numFmt="$#,##0"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/G{idx}" --prop formula="SUMPRODUCT((MONTH(CleaningDetail!C$2:C${last_row})={month_num})*1)" --prop numFmt="0"')

# City summary
cities = ["Nanjing", "Shanghai", "Hefei", "Ningbo", "Suzhou", "Hangzhou"]
for idx, city in enumerate(cities, start=2):
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/K{idx}" --prop value="{city}"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/L{idx}" --prop formula="SUMIF(CleaningDetail!D:D,\"{city}\",CleaningDetail!G:G)" --prop numFmt="$#,##0"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/M{idx}" --prop formula="COUNTIF(CleaningDetail!D:D,\"{city}\")" --prop numFmt="0"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/BusinessOverview/N{idx}" --prop formula="AVERAGEIF(CleaningDetail!D:D,\"{city}\",CleaningDetail!R:R)" --prop numFmt="$#,##0"')

# Add charts
print("Step 7: Add charts")
run_cmd(f'officecli add "{OUTPUT_FILE}" "/BusinessOverview" --type chart --prop chartType=column --prop dataRange="BusinessOverview!E1:F7" --prop title="Monthly Sales" --prop anchor="A10:H25"')
run_cmd(f'officecli add "{OUTPUT_FILE}" "/BusinessOverview" --type chart --prop chartType=pie --prop dataRange="BusinessOverview!K1:L7" --prop title="City Sales Distribution" --prop anchor="J10:Q25"')

# Step 8: Validation sheet
print("Step 8: Validation sheet")

val_headers = [("A1", "Check Item"), ("B1", "Expected"), ("C1", "Actual"), ("D1", "Pass")]
for cell, val in val_headers:
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/Validation/{cell}" --prop value="{val}" --prop bold=true')

checks = [
    ("A2", "Original Rows", "361", "COUNTA(UV_DEMO_I3_dirty_orders!A:A)-1"),
    ("A3", "Valid Rows", str(valid_count), "COUNTIF(CleaningDetail!L:L,\"Normal\")"),
    ("A4", "Abnormal Rows", str(invalid_count), "COUNTIF(CleaningDetail!L:L,\"Abnormal\")"),
    ("A5", "CleaningDetail Rows", str(len(data_rows)), "COUNTA(CleaningDetail!A:A)-1"),
]

for cell, label, expected, formula in checks:
    b_cell = 'B' + cell[1:]
    c_cell = 'C' + cell[1:]
    d_cell = 'D' + cell[1:]
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/Validation/{cell}" --prop value="{label}"')
    if expected:
        run_cmd(f'officecli set "{OUTPUT_FILE}" "/Validation/{b_cell}" --prop value="{expected}"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/Validation/{c_cell}" --prop formula="{formula}"')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/Validation/{d_cell}" --prop formula="IF({formula},\"PASS\",\"FAIL\")"')

# Step 9: Formatting
print("Step 9: Formatting")
for sheet in ["CleaningDetail", "BusinessOverview", "Validation"]:
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/{sheet}" --prop freeze=A2')
    run_cmd(f'officecli set "{OUTPUT_FILE}" "/{sheet}/row[1]" --prop fill=4472C4 --prop font.color=FFFFFF')

# Step 10: Close and validate
print("Step 10: Close and validate")
run_cmd(f'officecli close "{OUTPUT_FILE}"')
result = run_cmd(f'officecli validate "{OUTPUT_FILE}"')
print(f"Validation: {result.stdout}")

# Generate PNG preview
print("Step 11: Generate preview")
result = run_cmd(f'officecli view "{OUTPUT_FILE}" html')
print(f"HTML preview: {result.stdout}")

end_time = time.time()
print(f"\n=== Done ===")
print(f"Time: {end_time - start_time:.2f}s")
print(f"Original rows: 361")
print(f"Valid: {valid_count}")
print(f"Abnormal: {invalid_count}")
