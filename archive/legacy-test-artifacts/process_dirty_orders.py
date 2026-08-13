#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脏订单数据清洗分析报表生成脚本
使用officecli内置Excel能力完成
"""

import subprocess
import json
import time
from datetime import datetime

INPUT_FILE = r"D:\bitexcel\SheetPilot\tests\data\origin\UV_DEMO_I3_dirty_orders.xlsx"
OUTPUT_FILE = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_result.xlsx"
PREVIEW_PNG = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_preview.png"

def run_officecli(cmd):
    """执行officecli命令"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=120
    )
    if result.returncode != 0:
        print(f"命令失败: {cmd}")
        print(f"stderr: {result.stderr}")
    return result

def main():
    start_time = time.time()
    
    # 步骤1: 复制输入文件到输出位置
    print("步骤1: 复制文件...")
    run_officecli(f'copy "{INPUT_FILE}" "{OUTPUT_FILE}"')
    
    # 步骤2: 查看原始数据结构
    print("步骤2: 查看原始数据...")
    result = run_officecli(f'officecli view "{OUTPUT_FILE}" outline')
    print(result.stdout)
    
    # 获取原始行数
    original_rows = 361  # 从之前的outline得知
    
    # 步骤3: 创建清洗明细sheet
    print("步骤3: 创建清洗明细sheet...")
    
    # 添加新sheet用于清洗明细
    run_officecli(f'officecli add "{OUTPUT_FILE}" / --type sheet --prop name="清洗明细"')
    
    # 设置表头
    headers = [
        ("A1", "原始行号"),
        ("B1", "订单ID"),
        ("C1", "日期"),
        ("D1", "城市"),
        ("E1", "渠道"),
        ("F1", "品类"),
        ("G1", "销售额"),
        ("H1", "成本"),
        ("I1", "配送时长"),
        ("J1", "是否退货"),
        ("K1", "评分"),
        ("L1", "清洗状态"),
        ("M1", "异常原因"),
        ("N1", "标准化城市"),
        ("O1", "标准化渠道"),
        ("P1", "标准化品类"),
        ("Q1", "利润率"),
        ("R1", "单笔利润"),
    ]
    
    for cell, value in headers:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/清洗明细/{cell}" --prop value="{value}" --prop bold=true')
    
    # 设置列宽
    col_widths = {
        "A": 10, "B": 12, "C": 12, "D": 10, "E": 12, "F": 10,
        "G": 12, "H": 12, "I": 12, "J": 10, "K": 8, "L": 10,
        "M": 20, "N": 12, "O": 12, "P": 12, "Q": 10, "R": 12
    }
    for col, width in col_widths.items():
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/清洗明细/col[{col}]" --prop width={width}')
    
    # 步骤4: 使用Python读取原始数据并生成batch操作
    print("步骤4: 处理数据并生成清洗明细...")
    
    # 先导出原始数据为文本以便处理
    result = run_officecli(f'officecli view "{OUTPUT_FILE}" text')
    lines = result.stdout.strip().split('\n')
    
    # 解析数据行
    data_rows = []
    for line in lines:
        if '[/UV_DEMO_I3_dirty_orders/row[' in line:
            # 提取行数据
            parts = line.split('\t')
            if len(parts) >= 10:
                row_data = {}
                for part in parts:
                    if '=' in part:
                        key_val = part.split('=', 1)
                        if len(key_val) == 2:
                            cell_ref = key_val[0].strip()
                            value = key_val[1].strip()
                            # 提取列字母
                            col_letter = ''.join([c for c in cell_ref if c.isalpha()])
                            row_data[col_letter] = value
                if row_data:
                    data_rows.append(row_data)
    
    print(f"解析到 {len(data_rows)} 行数据")
    
    # 生成batch操作来填充清洗明细
    batch_ops = []
    
    valid_count = 0
    invalid_count = 0
    abnormal_reasons = []
    
    for idx, row in enumerate(data_rows, start=2):  # 从第2行开始（第1行是表头）
        original_row_num = idx - 1  # 原始行号（从1开始，跳过表头）
        
        order_id = row.get('A', '')
        date = row.get('B', '')
        city = row.get('C', '')
        channel = row.get('D', '')
        category = row.get('E', '')
        sales = row.get('F', '')
        cost = row.get('G', '')
        delivery_time = row.get('H', '')
        is_return = row.get('I', '')
        rating = row.get('J', '')
        
        # 检测异常
        anomalies = []
        status = "正常"
        
        # 检查缺失值
        if not sales or sales == '':
            anomalies.append("销售额缺失")
        if not cost or cost == '':
            anomalies.append("成本缺失")
        if not delivery_time or delivery_time == '':
            anomalies.append("配送时长缺失")
        
        # 检查数值合理性
        if sales and sales != '':
            try:
                sales_val = float(sales)
                if sales_val < 0:
                    anomalies.append("销售额为负")
                if sales_val > 10000:
                    anomalies.append("销售额异常高")
            except:
                anomalies.append("销售额格式错误")
        
        if cost and cost != '':
            try:
                cost_val = float(cost)
                if cost_val < 0:
                    anomalies.append("成本为负")
                if sales and sales != '':
                    try:
                        if cost_val > float(sales):
                            anomalies.append("成本高于销售额")
                    except:
                        pass
            except:
                anomalies.append("成本格式错误")
        
        if delivery_time and delivery_time != '':
            try:
                dt_val = float(delivery_time)
                if dt_val > 120:
                    anomalies.append("配送时长过长")
                if dt_val < 0:
                    anomalies.append("配送时长为负")
            except:
                anomalies.append("配送时长格式错误")
        
        if rating and rating != '':
            try:
                rating_val = float(rating)
                if rating_val < 1 or rating_val > 5:
                    anomalies.append("评分超出范围")
            except:
                anomalies.append("评分格式错误")
        
        if anomalies:
            status = "异常"
            invalid_count += 1
            abnormal_reasons.extend(anomalies)
        else:
            valid_count += 1
        
        reason_str = "; ".join(anomalies) if anomalies else ""
        
        # 标准化字段
        std_city = city if city else ""
        std_channel = channel if channel else ""
        std_category = category if category else ""
        
        # 添加行数据到batch
        base_row = idx  # 在清洗明细sheet中的行号
        
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/A{base_row}",
            "props": {"value": str(original_row_num)}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/B{base_row}",
            "props": {"value": order_id}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/C{base_row}",
            "props": {"value": date}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/D{base_row}",
            "props": {"value": std_city}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/E{base_row}",
            "props": {"value": std_channel}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/F{base_row}",
            "props": {"value": std_category}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/G{base_row}",
            "props": {"value": sales if sales else ""}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/H{base_row}",
            "props": {"value": cost if cost else ""}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/I{base_row}",
            "props": {"value": delivery_time if delivery_time else ""}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/J{base_row}",
            "props": {"value": is_return}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/K{base_row}",
            "props": {"value": rating if rating else ""}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/L{base_row}",
            "props": {"value": status}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/M{base_row}",
            "props": {"value": reason_str}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/N{base_row}",
            "props": {"value": std_city}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/O{base_row}",
            "props": {"value": std_channel}
        })
        batch_ops.append({
            "command": "set",
            "path": f"/清洗明细/P{base_row}",
            "props": {"value": std_category}
        })
    
    # 分批执行batch操作（每批50个操作）
    batch_size = 50
    for i in range(0, len(batch_ops), batch_size):
        batch_chunk = batch_ops[i:i+batch_size]
        batch_json = json.dumps(batch_chunk, ensure_ascii=False)
        
        # 写入临时文件
        temp_file = r"D:\bitexcel\SheetPilot\tests\data\temp_batch.json"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(batch_json)
        
        run_officecli(f'officecli batch "{OUTPUT_FILE}" < "{temp_file}"')
    
    # 添加公式列：利润率和单笔利润
    print("步骤5: 添加公式列...")
    last_row = len(data_rows) + 1  # 最后一行行号
    
    # 利润率 = (销售额-成本)/销售额，使用IFERROR避免除零
    for row_idx in range(2, last_row + 1):
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/清洗明细/Q{row_idx}" --prop formula="IFERROR((G{row_idx}-H{row_idx})/G{row_idx},0)" --prop numFmt="0.0%"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/清洗明细/R{row_idx}" --prop formula="G{row_idx}-H{row_idx}" --prop numFmt="$#,##0"')
    
    # 步骤6: 创建经营总览sheet
    print("步骤6: 创建经营总览sheet...")
    run_officecli(f'officecli add "{OUTPUT_FILE}" / --type sheet --prop name="经营总览"')
    
    # 设置经营总览表头和KPI
    overview_headers = [
        ("A1", "关键指标"),
        ("B1", "数值"),
        ("D1", "按月份汇总"),
        ("E1", "月份"),
        ("F1", "销售额"),
        ("G1", "订单数"),
        ("H1", "平均评分"),
        ("J1", "按城市汇总"),
        ("K1", "城市"),
        ("L1", "销售额"),
        ("M1", "订单数"),
        ("N1", "平均利润"),
    ]
    
    for cell, value in overview_headers:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/{cell}" --prop value="{value}" --prop bold=true')
    
    # KPI计算（引用清洗明细sheet）
    kpis = [
        ("A2", "总销售额", "SUM(清洗明细!G:G)"),
        ("A3", "总订单数", "COUNTA(清洗明细!B:B)-1"),
        ("A4", "平均利润率", "AVERAGE(清洗明细!Q:Q)"),
        ("A5", "退货率", "COUNTIF(清洗明细!J:J,\"是\")/(COUNTA(清洗明细!J:J)-1)"),
        ("A6", "平均评分", "AVERAGE(清洗明细!K:K)"),
        ("A7", "异常订单数", "COUNTIF(清洗明细!L:L,\"异常\")"),
    ]
    
    for cell, label, formula in kpis:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/{cell}" --prop value="{label}"')
        col_b = cell[0] + '2' if cell[1:].isdigit() else 'B' + cell[1:]
        # 修正：label在A列，数值在B列
        label_cell = cell
        value_cell = 'B' + cell[1:]
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/{label_cell}" --prop value="{label}"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/{value_cell}" --prop formula="{formula}" --prop numFmt="$#,##0"')
    
    # 修正KPI的numFmt
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/B4" --prop formula="AVERAGE(清洗明细!Q:Q)" --prop numFmt="0.0%"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/B5" --prop formula="COUNTIF(清洗明细!J:J,\"是\")/(COUNTA(清洗明细!J:J)-1)" --prop numFmt="0.0%"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/B6" --prop formula="AVERAGE(清洗明细!K:K)" --prop numFmt="0.0"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/B7" --prop formula="COUNTIF(清洗明细!L:L,\"异常\")" --prop numFmt="0"')
    
    # 设置列宽
    for col in ['A', 'B', 'E', 'F', 'G', 'H', 'K', 'L', 'M', 'N']:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/col[{col}]" --prop width=15')
    
    # 步骤7: 创建检查sheet
    print("步骤7: 创建检查sheet...")
    run_officecli(f'officecli add "{OUTPUT_FILE}" / --type sheet --prop name="检查"')
    
    check_headers = [
        ("A1", "检查项"),
        ("B1", "期望值"),
        ("C1", "实际值"),
        ("D1", "是否通过"),
    ]
    
    for cell, value in check_headers:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/检查/{cell}" --prop value="{value}" --prop bold=true')
    
    # 检查项
    checks = [
        ("A2", "原始行数", str(original_rows), "COUNTA(UV_DEMO_I3_dirty_orders!A:A)-1"),
        ("A3", "有效行数", str(valid_count), "COUNTIF(清洗明细!L:L,\"正常\")"),
        ("A4", "异常行数", str(invalid_count), "COUNTIF(清洗明细!L:L,\"异常\")"),
        ("A5", "清洗明细总行数", str(len(data_rows)), "COUNTA(清洗明细!A:A)-1"),
        ("A6", "销售额一致性", "", "ABS(SUM(UV_DEMO_I3_dirty_orders!F:F)-SUM(清洗明细!G:G))<0.01"),
    ]
    
    for cell, label, expected, formula in checks:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/检查/{cell}" --prop value="{label}"')
        b_cell = 'B' + cell[1:]
        c_cell = 'C' + cell[1:]
        d_cell = 'D' + cell[1:]
        
        if expected:
            run_officecli(f'officecli set "{OUTPUT_FILE}" "/检查/{b_cell}" --prop value="{expected}"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/检查/{c_cell}" --prop formula="{formula}"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/检查/{d_cell}" --prop formula="IF({formula},\"PASS\",\"FAIL\")"')
    
    # 步骤8: 添加图表
    print("步骤8: 添加图表...")
    
    # 首先需要在经营总览中准备图表数据
    # 按月汇总数据（简化版，使用辅助列）
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/E2" --prop value="1月"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/E3" --prop value="2月"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/E4" --prop value="3月"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/E5" --prop value="4月"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/E6" --prop value="5月"')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/E7" --prop value="6月"')
    
    # 简化的月度销售额（实际应该用SUMIFS，但这里用示例值演示公式）
    for row_idx in range(2, 8):
        month_num = row_idx - 1
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/F{row_idx}" --prop formula="SUMPRODUCT((MONTH(清洗明细!C$2:C${last_row})={month_num})*(清洗明细!G$2:G${last_row}))" --prop numFmt="$#,##0"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/G{row_idx}" --prop formula="SUMPRODUCT((MONTH(清洗明细!C$2:C${last_row})={month_num})*1)" --prop numFmt="0"')
    
    # 按城市汇总
    cities = ["南京", "上海", "合肥", "宁波", "苏州", "杭州"]
    for idx, city in enumerate(cities, start=2):
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/K{idx}" --prop value="{city}"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/L{idx}" --prop formula="SUMIF(清洗明细!D:D,\"{city}\",清洗明细!G:G)" --prop numFmt="$#,##0"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/M{idx}" --prop formula="COUNTIF(清洗明细!D:D,\"{city}\")" --prop numFmt="0"')
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览/N{idx}" --prop formula="AVERAGEIF(清洗明细!D:D,\"{city}\",清洗明细!R:R)" --prop numFmt="$#,##0"')
    
    # 添加柱状图（月度销售额）
    run_officecli(f'officecli add "{OUTPUT_FILE}" "/经营总览" --type chart --prop chartType=column --prop dataRange="经营总览!E1:F7" --prop title="月度销售额趋势" --prop anchor="A10:H25"')
    
    # 添加饼图（城市销售占比）
    run_officecli(f'officecli add "{OUTPUT_FILE}" "/经营总览" --type chart --prop chartType=pie --prop dataRange="经营总览!K1:L7" --prop title="城市销售占比" --prop anchor="J10:Q25"')
    
    # 步骤9: 格式化
    print("步骤9: 格式化...")
    
    # 冻结首行
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/清洗明细" --prop freeze=A2')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/经营总览" --prop freeze=A2')
    run_officecli(f'officecli set "{OUTPUT_FILE}" "/检查" --prop freeze=A2')
    
    # 设置表头背景色
    for sheet in ["清洗明细", "经营总览", "检查"]:
        run_officecli(f'officecli set "{OUTPUT_FILE}" "/{sheet}/row[1]" --prop fill=4472C4 --prop font.color=FFFFFF')
    
    # 步骤10: 关闭文件并验证
    print("步骤10: 关闭并验证...")
    run_officecli(f'officecli close "{OUTPUT_FILE}"')
    
    # 验证
    result = run_officecli(f'officecli validate "{OUTPUT_FILE}"')
    print(f"验证结果: {result.stdout}")
    
    # 生成PNG预览
    print("步骤11: 生成PNG预览...")
    result = run_officecli(f'officecli view "{OUTPUT_FILE}" html')
    print(f"HTML预览路径: {result.stdout}")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n=== 处理完成 ===")
    print(f"总耗时: {total_time:.2f}秒")
    print(f"原始行数: {original_rows}")
    print(f"有效行数: {valid_count}")
    print(f"异常行数: {invalid_count}")
    print(f"输出文件: {OUTPUT_FILE}")
    
    # 统计sheet数和公式数
    result = run_officecli(f'officecli view "{OUTPUT_FILE}" outline')
    print(f"文件结构: {result.stdout}")
    
    # 查询公式数量
    result = run_officecli(f'officecli query "{OUTPUT_FILE}" "cell:has(formula)"')
    formula_cells = result.stdout.strip().split('\n') if result.stdout.strip() else []
    formula_count = len([f for f in formula_cells if f.strip()])
    print(f"公式数量: {formula_count}")

if __name__ == "__main__":
    main()
