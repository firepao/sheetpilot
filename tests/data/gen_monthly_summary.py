import json
import subprocess

xlsx_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result1.xlsx"

# 按月份汇总
ops = [
    {"command":"set","path":"/经营总览/D3","props":{"value":"按月汇总","bold":True}},
    {"command":"set","path":"/经营总览/E3","props":{"value":"订单数","bold":True}},
    {"command":"set","path":"/经营总览/F3","props":{"value":"销售额","bold":True}},
    {"command":"set","path":"/经营总览/G3","props":{"value":"利润","bold":True}},
]

# 添加1-12月的汇总行
for month in range(1, 13):
    row = 4 + month - 1
    ops.append({"command":"set","path":f"/经营总览/D{row}","props":{"value":f"{month}月"}})
    ops.append({"command":"set","path":f"/经营总览/E{row}","props":{"formula":f'COUNTIF(清洗明细!O2:O361,{month})'}})
    ops.append({"command":"set","path":f"/经营总览/F{row}","props":{"formula":f'SUMIF(清洗明细!O2:O361,{month},清洗明细!G2:G361)',"numFmt":"$#,##0"}})
    ops.append({"command":"set","path":f"/经营总览/G{row}","props":{"formula":f'SUMIF(清洗明细!O2:O361,{month},清洗明细!G2:G361)-SUMIF(清洗明细!O2:O361,{month},清洗明细!H2:H361)',"numFmt":"$#,##0"}})

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
    print("SUCCESS: Monthly summary added")
