import json

# 定义脏数据的行号（基于1-indexed，A1是表头，所以数据从第2行开始）
# 从之前读取的内容来看：
# OD00017 (行18): 销售额为空 -> 原始数据 row[18]
# OD00055 (行56): 成本为空 -> 原始数据 row[56]
# OD00088 (行89): 销售额为空 -> 原始数据 row[89]
# OD00099 (行100): 配送时长为空 -> 原始数据 row[100]
# OD00149 (行150): 销售额为空 -> 原始数据 row[150]
# OD00156 (行157): 成本为空 -> 原始数据 row[157]
# OD00201 (行202): 配送时长为空 -> 原始数据 row[202]

dirty_rows = {18, 56, 89, 100, 150, 157, 202}

ops = []

# 表头已经在 A1:O1 设置好了
# 现在需要从第2行到第361行（共360条数据）填充数据
for i in range(2, 362):  # 2 to 361 inclusive
    original_row = i  # 原始数据中的行号
    
    # 判断是否是脏数据
    is_dirty = original_row in dirty_rows
    
    # 确定异常原因
    if original_row == 18:
        anomaly_reason = "销售额缺失"
    elif original_row == 56:
        anomaly_reason = "成本缺失"
    elif original_row == 89:
        anomaly_reason = "销售额缺失"
    elif original_row == 100:
        anomaly_reason = "配送时长缺失"
    elif original_row == 150:
        anomaly_reason = "销售额缺失"
    elif original_row == 157:
        anomaly_reason = "成本缺失"
    elif original_row == 202:
        anomaly_reason = "配送时长缺失"
    else:
        anomaly_reason = ""
    
    # 清洗状态
    clean_status = "异常" if is_dirty else "正常"
    
    # 原始行号
    ops.append({
        "command": "set",
        "path": f"/清洗明细/A{i}",
        "props": {"value": original_row - 1}  # 原始行号（去掉表头）
    })
    
    # 订单ID - 从原始数据引用
    ops.append({
        "command": "set",
        "path": f"/清洗明细/B{i}",
        "props": {"formula": f"原始数据!A{original_row}"}
    })
    
    # 日期
    ops.append({
        "command": "set",
        "path": f"/清洗明细/C{i}",
        "props": {"formula": f"原始数据!B{original_row}"}
    })
    
    # 城市
    ops.append({
        "command": "set",
        "path": f"/清洗明细/D{i}",
        "props": {"formula": f"原始数据!C{original_row}"}
    })
    
    # 渠道
    ops.append({
        "command": "set",
        "path": f"/清洗明细/E{i}",
        "props": {"formula": f"原始数据!D{original_row}"}
    })
    
    # 品类
    ops.append({
        "command": "set",
        "path": f"/清洗明细/F{i}",
        "props": {"formula": f"原始数据!E{original_row}"}
    })
    
    # 销售额 - 使用 IFERROR 处理空值
    ops.append({
        "command": "set",
        "path": f"/清洗明细/G{i}",
        "props": {"formula": f"IFERROR(原始数据!F{original_row}, 0)"}
    })
    
    # 成本 - 使用 IFERROR 处理空值
    ops.append({
        "command": "set",
        "path": f"/清洗明细/H{i}",
        "props": {"formula": f"IFERROR(原始数据!G{original_row}, 0)"}
    })
    
    # 配送时长 - 使用 IFERROR 处理空值
    ops.append({
        "command": "set",
        "path": f"/清洗明细/I{i}",
        "props": {"formula": f"IFERROR(原始数据!H{original_row}, 0)"}
    })
    
    # 是否退货
    ops.append({
        "command": "set",
        "path": f"/清洗明细/J{i}",
        "props": {"formula": f"原始数据!I{original_row}"}
    })
    
    # 评分
    ops.append({
        "command": "set",
        "path": f"/清洗明细/K{i}",
        "props": {"formula": f"原始数据!J{original_row}"}
    })
    
    # 清洗状态
    ops.append({
        "command": "set",
        "path": f"/清洗明细/L{i}",
        "props": {"value": clean_status}
    })
    
    # 异常原因
    ops.append({
        "command": "set",
        "path": f"/清洗明细/M{i}",
        "props": {"value": anomaly_reason}
    })
    
    # 利润率 = (销售额 - 成本) / 销售额，需要处理除零和空值
    ops.append({
        "command": "set",
        "path": f"/清洗明细/N{i}",
        "props": {"formula": f'IFERROR(IF(G{i}=0, 0, (G{i}-H{i})/G{i}), 0)'}
    })
    
    # 月份 - 从日期中提取月份
    ops.append({
        "command": "set",
        "path": f"/清洗明细/O{i}",
        "props": {"formula": f'MONTH(原始数据!B{original_row})'}
    })

# 分批输出，每批80个操作
batch_size = 80
for i in range(0, len(ops), batch_size):
    batch = ops[i:i+batch_size]
    print(json.dumps(batch))
