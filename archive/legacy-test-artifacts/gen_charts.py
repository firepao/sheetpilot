import json
import subprocess

xlsx_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result1.xlsx"

# 添加第一个图表：按月销售额柱状图
# 数据范围是 D4:D15（月份）和 F4:F15（销售额）
ops = [
    {
        "command": "add",
        "parent": "/经营总览",
        "type": "chart",
        "props": {
            "chartType": "column",
            "anchor": "I3:L18",
            "title": "月度销售额趋势",
            "dataRange": "经营总览!D4:F15"
        }
    }
]

batch_json = json.dumps(ops)

# 执行 batch 命令
result = subprocess.run(
    ['officecli', 'batch', xlsx_path],
    input=batch_json,
    capture_output=True,
    text=True,
    timeout=60
)

if result.returncode != 0:
    print(f"ERROR: {result.stderr}")
else:
    print("SUCCESS: Chart 1 added")
