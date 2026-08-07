import json
import subprocess

xlsx_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result1.xlsx"

# 经营总览 KPI 指标
ops = [
    {"command":"set","path":"/经营总览/A3","props":{"value":"KPI指标","bold":True}},
    {"command":"set","path":"/经营总览/B3","props":{"value":"数值","bold":True}},
    {"command":"set","path":"/经营总览/A4","props":{"value":"总订单数"}},
    {"command":"set","path":"/经营总览/B4","props":{"formula":"COUNTA(清洗明细!B2:B361)"}},
    {"command":"set","path":"/经营总览/A5","props":{"value":"有效订单数"}},
    {"command":"set","path":"/经营总览/B5","props":{"formula":"COUNTIF(清洗明细!L2:L361,\"正常\")"}},
    {"command":"set","path":"/经营总览/A6","props":{"value":"异常订单数"}},
    {"command":"set","path":"/经营总览/B6","props":{"formula":"COUNTIF(清洗明细!L2:L361,\"异常\")"}},
    {"command":"set","path":"/经营总览/A7","props":{"value":"总销售额"}},
    {"command":"set","path":"/经营总览/B7","props":{"formula":"SUM(清洗明细!G2:G361)","numFmt":"$#,##0"}},
    {"command":"set","path":"/经营总览/A8","props":{"value":"总成本"}},
    {"command":"set","path":"/经营总览/B8","props":{"formula":"SUM(清洗明细!H2:H361)","numFmt":"$#,##0"}},
    {"command":"set","path":"/经营总览/A9","props":{"value":"总利润"}},
    {"command":"set","path":"/经营总览/B9","props":{"formula":"B7-B8","numFmt":"$#,##0"}},
    {"command":"set","path":"/经营总览/A10","props":{"value":"平均利润率"}},
    {"command":"set","path":"/经营总览/B10","props":{"formula":"IF(B7=0,0,B9/B7)","numFmt":"0.0%"}}
]

batch_json = json.dumps(ops)
print(batch_json)

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
    print(f"SUCCESS: {result.stdout}")
