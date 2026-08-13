import subprocess
import json
import sys

file_path = r"D:\bitexcel\SheetPilot\tests\data\cleaning_batch.jsonl"
xlsx_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result1.xlsx"

with open(file_path, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

total_lines = len(lines)
print(f"Total batches: {total_lines}")

for i, line in enumerate(lines, 1):
    line = line.strip()
    if not line:
        continue
    
    try:
        # Execute batch command
        result = subprocess.run(
            ['officecli', 'batch', xlsx_path],
            input=line,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"Batch {i}/{total_lines} FAILED: {result.stderr}")
        else:
            # Count successes from output
            output = result.stdout
            if 'succeeded' in output:
                print(f"Batch {i}/{total_lines} OK")
            else:
                print(f"Batch {i}/{total_lines} completed (check output)")
                
    except subprocess.TimeoutExpired:
        print(f"Batch {i}/{total_lines} TIMEOUT")
    except Exception as e:
        print(f"Batch {i}/{total_lines} ERROR: {e}")

print("All batches processed!")
