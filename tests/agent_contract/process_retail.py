"""
处理 07_complex_retail_operations.xlsx：
- 读取"门店订单明细"工作表
- 过滤：审核状态="通过" 且 是否取消="否"
- 按区域、产品品类分组
- 计算：净销售收入(sum)、交易数量(行数)、客户编号非空数量、平均订单金额(avg)、毛利合计(sum)
- 按净销售收入降序
- 写入新工作表"区域品类经营汇总"
- 保留原工作簿所有工作表、公式和图表
"""
from pathlib import Path

import openpyxl
import os
from copy import copy

ROOT = Path(__file__).resolve().parent
input_path = ROOT / "data" / "07_complex_retail_operations.xlsx"
result_dir = ROOT / "results"
output_dir = None

# 查找生成的结果目录
for d in os.listdir(result_dir):
    if d.startswith("sheetpilot__"):
        output_dir = os.path.join(result_dir, d)
        break

if not output_dir:
    # 创建新的结果目录
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%dT%H%M%S+0800")
    output_dir = os.path.join(result_dir, f"sheetpilot__{ts}__run-direct")
    os.makedirs(output_dir, exist_ok=True)

output_path = os.path.join(output_dir, "retail_regional_category_summary.xlsx")

# 加载工作簿（保留公式，不用于读取数据）
wb = openpyxl.load_workbook(input_path)
# 用 data_only=True 读取数据
wb_data = openpyxl.load_workbook(input_path, data_only=True)

ws = wb_data['门店订单明细']
headers = [cell.value for cell in ws[1]]

# 列索引映射
col_map = {h: idx for idx, h in enumerate(headers)}  # 0-based

# 过滤并收集数据
filtered_rows = []
for row in ws.iter_rows(min_row=2, values_only=True):
    audit_status = row[col_map['审核状态']]
    is_cancel = row[col_map['是否取消']]
    if audit_status == '通过' and is_cancel == '否':
        filtered_rows.append(row)

print(f"过滤后记录数: {len(filtered_rows)}")

# 按区域、产品品类分组
from collections import defaultdict

groups = defaultdict(list)
for row in filtered_rows:
    region = row[col_map['区域']]
    category = row[col_map['产品品类']]
    groups[(region, category)].append(row)

# 计算指标
summary_data = []
for (region, category), rows in groups.items():
    net_sales_sum = sum(row[col_map['净销售额']] or 0 for row in rows)
    transaction_count = len(rows)
    customer_nonempty = sum(1 for row in rows if row[col_map['客户编号']] is not None)
    avg_order = net_sales_sum / transaction_count if transaction_count > 0 else 0
    gross_profit_sum = sum(row[col_map['毛利']] or 0 for row in rows)
    
    summary_data.append({
        '区域': region,
        '产品品类': category,
        '净销售收入': round(net_sales_sum, 2),
        '交易数量': transaction_count,
        '客户编号非空数量': customer_nonempty,
        '平均订单金额': round(avg_order, 2),
        '毛利合计': round(gross_profit_sum, 2)
    })

# 按净销售收入降序
summary_data.sort(key=lambda x: x['净销售收入'], reverse=True)

print(f"分组数: {len(summary_data)}")
print("前5行:")
for d in summary_data[:5]:
    print(f"  {d['区域']:8s} | {d['产品品类']:10s} | 净销售收入={d['净销售收入']:8.2f} | 交易数量={d['交易数量']:4d} | 客户编号={d['客户编号非空数量']:4d} | 平均订单金额={d['平均订单金额']:8.2f} | 毛利合计={d['毛利合计']:8.2f}")

# ===== 写入原工作簿 =====
# 加载完整工作簿（保留公式和图表）
wb_out = openpyxl.load_workbook(input_path)

# 创建新工作表
ws_out = wb_out.create_sheet(title="区域品类经营汇总")

# 写入表头
summary_headers = ['区域', '产品品类', '净销售收入', '交易数量', '客户编号非空数量', '平均订单金额', '毛利合计']
for col_idx, header in enumerate(summary_headers, 1):
    cell = ws_out.cell(row=1, column=col_idx, value=header)
    cell.font = openpyxl.styles.Font(bold=True)
    cell.fill = openpyxl.styles.PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
    cell.alignment = openpyxl.styles.Alignment(horizontal='center')

# 写入数据
for row_idx, item in enumerate(summary_data, 2):
    ws_out.cell(row=row_idx, column=1, value=item['区域'])
    ws_out.cell(row=row_idx, column=2, value=item['产品品类'])
    ws_out.cell(row=row_idx, column=3, value=item['净销售收入'])
    ws_out.cell(row=row_idx, column=4, value=item['交易数量'])
    ws_out.cell(row=row_idx, column=5, value=item['客户编号非空数量'])
    ws_out.cell(row=row_idx, column=6, value=item['平均订单金额'])
    ws_out.cell(row=row_idx, column=7, value=item['毛利合计'])

# 设置列宽
col_widths = [12, 14, 16, 12, 20, 16, 12]
for i, w in enumerate(col_widths, 1):
    ws_out.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

# 保存
wb_out.save(output_path)
print(f"\n输出文件已保存: {output_path}")

# 校验输出文件
wb_check = openpyxl.load_workbook(output_path)
print(f"输出工作表列表: {wb_check.sheetnames}")
ws_check = wb_check['区域品类经营汇总']
print(f"区域品类经营汇总 行数: {ws_check.max_row - 1} (含表头{ws_check.max_row})")
check_headers = [cell.value for cell in ws_check[1]]
print(f"表头: {check_headers}")
