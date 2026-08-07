import json
import subprocess

xlsx_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result1.xlsx"

# 异常检查 sheet 内容
ops = [
    {"command":"set","path":"/异常检查/A1","props":{"value":"数据一致性检查","bold":True,"font.size":14}},
    {"command":"set","path":"/异常检查/A3","props":{"value":"检查项","bold":True}},
    {"command":"set","path":"/异常检查/B3","props":{"value":"预期值","bold":True}},
    {"command":"set","path":"/异常检查/C3","props":{"value":"实际值","bold":True}},
    {"command":"set","path":"/异常检查/D3","props":{"value":"状态","bold":True}},
    
    # 原始行数检查
    {"command":"set","path":"/异常检查/A4","props":{"value":"原始数据行数"}},
    {"command":"set","path":"/异常检查/B4","props":{"formula":"COUNTA(原始数据!A2:A361)"}},
    {"command":"set","path":"/异常检查/C4","props":{"formula":"COUNTA(清洗明细!A2:A361)"}},
    {"command":"set","path":"/异常检查/D4","props":{"formula":"IF(B4=C4,\"通过\",\"不通过\")"}},
    
    # 有效行数检查
    {"command":"set","path":"/异常检查/A5","props":{"value":"有效订单数"}},
    {"command":"set","path":"/异常检查/B5","props":{"formula":"COUNTIF(清洗明细!L2:L361,\"正常\")"}},
    {"command":"set","path":"/异常检查/C5","props":{"formula":"B5"}},
    {"command":"set","path":"/异常检查/D5","props":{"formula":"\"通过\""}},
    
    # 异常行数检查
    {"command":"set","path":"/异常检查/A6","props":{"value":"异常订单数"}},
    {"command":"set","path":"/异常检查/B6","props":{"formula":"COUNTIF(清洗明细!L2:L361,\"异常\")"}},
    {"command":"set","path":"/异常检查/C6","props":{"formula":"B6"}},
    {"command":"set","path":"/异常检查/D6","props":{"formula":"\"通过\""}},
    
    # 总销售额一致性检查
    {"command":"set","path":"/异常检查/A7","props":{"value":"清洗明细总销售额"}},
    {"command":"set","path":"/异常检查/B7","props":{"formula":"SUM(清洗明细!G2:G361)","numFmt":"$#,##0"}},
    {"command":"set","path":"/异常检查/C7","props":{"formula":"经营总览!B7","numFmt":"$#,##0"}},
    {"command":"set","path":"/异常检查/D7","props":{"formula":"IF(ROUND(B7,2)=ROUND(C7,2),\"通过\",\"不通过\")"}},
    
    # 总成本一致性检查
    {"command":"set","path":"/异常检查/A8","props":{"value":"清洗明细总成本"}},
    {"command":"set","path":"/异常检查/B8","props":{"formula":"SUM(清洗明细!H2:H361)","numFmt":"$#,##0"}},
    {"command":"set","path":"/异常检查/C8","props":{"formula":"经营总览!B8","numFmt":"$#,##0"}},
    {"command":"set","path":"/异常检查/D8","props":{"formula":"IF(ROUND(B8,2)=ROUND(C8,2),\"通过\",\"不通过\")"}}
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
    print("SUCCESS: Check sheet added")
