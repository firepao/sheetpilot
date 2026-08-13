#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import subprocess

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

# Get original data
print("Getting original data...")
result = run_cmd(f'officecli view "{FILE}" text')
lines = result.stdout.strip().split('\n') if result.stdout else []

# Parse data rows from UV_DEMO_I3_dirty_orders sheet
data_rows = []
for line in lines:
    if '[/UV_DEMO_I3_dirty_orders/row[' in line and '=== Sheet:' not in line:
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

# Generate batch operations for CleaningDetail sheet
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
                issues.append("Cost>Sales")
        except:
            pass
    
    if delivery:
        try:
            d = float(delivery)
            if d > 120:
                issues.append("Long delivery")
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

last_row = len(data_rows) + 1

# Add formulas for profit margin and profit
for row_idx in range(2, last_row + 1):
    batch_ops.extend([
        {"command": "set", "path": f"/CleaningDetail/Q{row_idx}", "props": {"formula": f"IFERROR((G{row_idx}-H{row_idx})/G{row_idx},0)", "numFmt": "0.0%"}},
        {"command": "set", "path": f"/CleaningDetail/R{row_idx}", "props": {"formula": f"G{row_idx}-H{row_idx}", "numFmt": "$#,##0"}},
    ])

print(f"Generated {len(batch_ops)} operations")

# Execute batches
batch_size = 50
for i in range(0, len(batch_ops), batch_size):
    chunk = batch_ops[i:i+batch_size]
    temp_file = r"D:\bitexcel\SheetPilot\tests\data\temp_batch.json"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(chunk, f, ensure_ascii=False)
    print(f"Executing batch {i//batch_size + 1}...")
    result = run_cmd(f'officecli batch "{FILE}" < "{temp_file}"')
    if result.returncode != 0:
        print(f"Batch failed: {result.stderr}")

print(f"\nValid: {valid_count}, Abnormal: {invalid_count}")

# Save counts for later use
with open(r"D:\bitexcel\SheetPilot\tests\data\counts.txt", 'w') as f:
    f.write(f"{valid_count}\n{invalid_count}\n{len(data_rows)}\n{last_row}")

print("Done generating batch operations")
