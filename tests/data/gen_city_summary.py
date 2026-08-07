import json
import subprocess

xlsx_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result1.xlsx"

# 首先添加按城市汇总的数据
city_ops = [
    {"command":"set","path":"/经营总览/D17","props":{"value":"按城市汇总","bold":True}},
    {"command":"set","path":"/经营总览/E17","props":{"value":"城市","bold":True}},
    {"command":"set","path":"/经营总览/F17","props":{"value":"订单数","bold":True}},
    {"command":"set","path":"/经营总览/G17","props":{"value":"销售额","bold":True}},
]

# 添加各个城市的汇总（南京、上海、合肥、宁波、苏州、杭州）
cities = ["南京", "上海", "合肥", "宁波", "苏州", "杭州"]
for i, city in enumerate(cities):
    row = 18 + i
    ops_append = [
        {"command":"set","path":f"/经营总览/E{row}","props":{"value":city}},
        {"command":"set","path":f"/经营总览/F{row}","props":{"formula":f'COUNTIF(清洗明细!D2:D361,"{city}")'}},
        {"command":"set","path":f"/经营总览/G{row}","props":{"formula":f'SUMIF(清洗明细!D2:D361,"{city}",清洗明细!G2:G361)',"numFmt":"$#,##0"}}
    ]
    city_ops.extend(ops_append)

batch_json = json.dumps(city_ops)

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
    print("SUCCESS: City summary added")

# 现在添加第二个图表 - 按城市销售额柱状图
chart_ops = [
    {
        "command": "add",
        "parent": "/经营总览",
        "type": "chart",
        "props": {
            "chartType": "column",
            "anchor": "I19:L34",
            "title": "各城市销售额对比",
            "dataRange": "经营总览!E18:G23"
        }
    }
]

chart_json = json.dumps(chart_ops)
result2 = subprocess.run(
    ['officecli', 'batch', xlsx_path],
    input=chart_json,
    capture_output=True,
    text=True,
    timeout=60
)

if result2.returncode != 0:
    print(f"Chart 2 ERROR: {result2.stderr}")
else:
    print("SUCCESS: Chart 2 added")
