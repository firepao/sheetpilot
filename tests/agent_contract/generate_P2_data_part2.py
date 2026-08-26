"""
测试数据集生成脚本 - P2阶段扩充 Part 2
生成 S7-S9, H1-H2, H4-H5 场景数据
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font

# 设置输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')


def create_workbook(sheet_name: str) -> Workbook:
    """创建新工作簿"""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    return wb


# ============= S7: 双维度单指标 =============
def generate_S7_two_dims():
    """S7: 双维度单指标场景"""
    wb = create_workbook("销售数据")
    ws = wb.active

    # 表头
    ws.append(["区域", "产品类别", "销售额"])

    # 3个区域 × 4个类别
    regions = ["华东", "华南", "华北"]
    categories = ["电子产品", "家居用品", "服装鞋帽", "食品饮料"]

    expected = {
        ("华东", "电子产品"): 85000,
        ("华东", "家居用品"): 62000,
        ("华东", "服装鞋帽"): 48000,
        ("华东", "食品饮料"): 35000,
        ("华南", "电子产品"): 72000,
        ("华南", "家居用品"): 58000,
        ("华南", "服装鞋帽"): 42000,
        ("华南", "食品饮料"): 28000,
        ("华北", "电子产品"): 68000,
        ("华北", "家居用品"): 52000,
        ("华北", "服装鞋帽"): 38000,
        ("华北", "食品饮料"): 22000,
    }

    for (region, category), target in expected.items():
        count = random.randint(10, 20)
        remaining = target
        for i in range(count):
            if i == count - 1:
                amount = remaining
            else:
                min_amt = 2000
                max_amt = min(8000, max(min_amt, remaining - (count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount
            ws.append([region, category, amount])

    output_path = Path(__file__).parent / "data" / "S7_two_dims.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S7: {output_path} (行数: {ws.max_row - 1}, 12个组合)")


# ============= S8: 单维度多指标 =============
def generate_S8_multi_metrics():
    """S8: 单维度多指标场景 - sum + count.rows + average"""
    wb = create_workbook("订单数据")
    ws = wb.active

    # 表头
    ws.append(["订单号", "城市", "订单金额", "客户ID"])

    cities_data = [
        ("北京", 120000, 45),
        ("上海", 98000, 38),
        ("深圳", 85000, 32),
        ("广州", 72000, 28),
        ("杭州", 58000, 22),
    ]

    order_id = 30001
    for city, total_amount, order_count in cities_data:
        remaining = total_amount
        for i in range(order_count):
            if i == order_count - 1:
                amount = remaining
            else:
                min_amt = 1500
                max_amt = min(4000, max(min_amt, remaining - (order_count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount
            customer_id = f"C{random.randint(1001, 9999)}"
            ws.append([f"O{order_id}", city, amount, customer_id])
            order_id += 1

    output_path = Path(__file__).parent / "data" / "S8_multi_metrics.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S8: {output_path} (行数: {ws.max_row - 1}, 5个城市)")


# ============= S9: 多条件AND过滤 =============
def generate_S9_multi_filter():
    """S9: 多条件AND过滤场景"""
    wb = create_workbook("产品销售")
    ws = wb.active

    # 表头
    ws.append(["产品ID", "产品名称", "销售额", "状态", "区域"])

    products = ["产品A", "产品B", "产品C", "产品D", "产品E"]
    statuses = ["正常", "停售"]
    regions = ["华东", "华南", "华北"]

    # 目标：状态=正常 AND 区域=华东
    target_products = {
        "产品A": 45000,
        "产品B": 38000,
        "产品C": 32000,
        "产品D": 28000,
        "产品E": 22000,
    }

    product_id = 10001
    for product in products:
        # 生成符合条件的记录（正常+华东）
        target = target_products[product]
        count = random.randint(8, 15)
        remaining = target
        for i in range(count):
            if i == count - 1:
                amount = remaining
            else:
                min_amt = 1500
                max_amt = min(4000, max(min_amt, remaining - (count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount
            ws.append([f"P{product_id}", product, amount, "正常", "华东"])
            product_id += 1

        # 生成不符合条件的记录（随机状态和区域组合，排除正常+华东）
        noise_count = random.randint(5, 12)
        for _ in range(noise_count):
            amount = random.randint(1000, 5000)
            status = random.choice(statuses)
            region = random.choice(regions)
            # 确保不是目标组合
            if status == "正常" and region == "华东":
                status = "停售"
            ws.append([f"P{product_id}", product, amount, status, region])
            product_id += 1

    output_path = Path(__file__).parent / "data" / "S9_multi_filter.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S9: {output_path} (行数: {ws.max_row - 1}, 符合条件总额: 165000)")


# ============= H1: 日期格式歧义 =============
def generate_H1_date_ambiguity():
    """H1: 日期格式歧义场景 - 混合格式"""
    wb = create_workbook("订单记录")
    ws = wb.active

    # 表头
    ws.append(["订单号", "订单日期", "客户", "金额", "月份"])

    # 2024年每月销售额（用于验证）
    monthly_targets = {
        1: 28000, 2: 32000, 3: 35000, 4: 38000, 5: 42000, 6: 45000,
        7: 48000, 8: 52000, 9: 55000, 10: 58000, 11: 62000, 12: 65000
    }

    order_id = 20001
    date_formats = [
        lambda y, m, d: f"{y}-{m:02d}-{d:02d}",  # 2024-01-15
        lambda y, m, d: f"{y}/{m:02d}/{d:02d}",  # 2024/01/15
        lambda y, m, d: f"{m:02d}/{d:02d}/{y}",  # 01/15/2024
        lambda y, m, d: f"{d:02d}/{m:02d}/{y}",  # 15/01/2024 (DD/MM/YYYY)
    ]

    for month, target in monthly_targets.items():
        count = random.randint(8, 15)
        remaining = target
        for i in range(count):
            day = random.randint(1, 28)  # 避免月末日期问题
            # 随机选择日期格式
            fmt = random.choice(date_formats)
            date_str = fmt(2024, month, day)

            if i == count - 1:
                amount = remaining
            else:
                min_amt = 1500
                max_amt = min(4000, max(min_amt, remaining - (count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount

            customer = f"客户{random.randint(1001, 1999)}"
            ws.append([f"O{order_id}", date_str, customer, amount, f"{month}月"])
            order_id += 1

    output_path = Path(__file__).parent / "data" / "H1_date_ambiguity.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 H1: {output_path} (行数: {ws.max_row - 1}, 12个月)")


# ============= H2: 字段名相似性 =============
def generate_H2_field_similarity():
    """H2: 多个工资字段并存，目标字段为实发工资。"""
    wb = create_workbook("销售记录")
    ws = wb.active
    ws.append(["员工编号", "部门", "基本工资", "实发工资", "应发工资", "工资", "绩效工资"])
    departments = ["销售部", "研发部", "财务部"]
    for index in range(1, 96):
        department = departments[(index - 1) % len(departments)]
        position_salary = random.randint(5000, 12000)
        base_salary = position_salary + random.randint(1000, 4000)
        performance_salary = random.randint(500, 5000)
        gross_salary = base_salary + performance_salary
        net_salary = gross_salary - random.randint(800, 2500)
        ws.append([
            f"E{index:04d}", department, base_salary, net_salary,
            gross_salary, position_salary, performance_salary,
        ])

    output_path = Path(__file__).parent / "data" / "H2_field_similarity.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 H2: {output_path} (行数: {ws.max_row - 1}, 5个工资字段)")


# ============= H4: 多条件复杂组合 =============
def generate_H4_complex_filter():
    """H4: 多条件复杂组合过滤场景"""
    wb = create_workbook("客户订单")
    ws = wb.active

    # 表头
    ws.append(["订单号", "客户类型", "区域", "订单金额", "支付状态", "订单状态"])

    # 目标条件：客户等级=VIP AND 订单金额>5000 AND 支付方式=在线支付
    target_by_region = {
        "华东": 125000,
        "华南": 98000,
        "华北": 82000,
    }

    order_id = 40001
    levels = ["普通", "VIP", "钻石"]
    payments = ["在线支付", "货到付款", "对公转账"]
    invoice = ["是", "否"]
    regions = ["华东", "华南", "华北"]

    for region, target in target_by_region.items():
        # 符合条件的记录
        count = random.randint(15, 25)
        remaining = target
        for i in range(count):
            if i == count - 1:
                amount = remaining
            else:
                min_amt = 5001
                max_amt = min(8000, max(min_amt, remaining - (count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount

            ws.append([f"O{order_id}", "企业", region, amount, "已支付", "已完成"])
            order_id += 1

        # 不符合条件的记录（随机组合）
        noise_count = random.randint(20, 35)
        for _ in range(noise_count):
            customer_type = random.choice(["企业", "个人"])
            payment_status = random.choice(["已支付", "未支付", "已退款"])
            order_status = random.choice(["已完成", "进行中", "已取消"])
            amount = random.randint(1000, 10000)
            if customer_type == "企业" and payment_status == "已支付" and order_status == "已完成" and amount > 5000:
                payment_status = "未支付"
            ws.append([f"O{order_id}", customer_type, region, amount, payment_status, order_status])
            order_id += 1

    output_path = Path(__file__).parent / "data" / "H4_complex_filter.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 H4: {output_path} (行数: {ws.max_row - 1}, 符合条件总额: 305000)")


# ============= H5: 嵌套分组场景 =============
def generate_H5_nested_group():
    """H5: 嵌套分组场景 - 三维度"""
    wb = create_workbook("销售数据")
    ws = wb.active

    # 表头
    ws.append(["年份", "季度", "月份", "销售额"])

    # 2023-2024两年数据
    quarterly_data = {
        (2023, "Q1", "1月"): 28000,
        (2023, "Q1", "2月"): 32000,
        (2023, "Q1", "3月"): 35000,
        (2023, "Q2", "4月"): 38000,
        (2023, "Q2", "5月"): 42000,
        (2023, "Q2", "6月"): 45000,
        (2024, "Q1", "1月"): 52000,
        (2024, "Q1", "2月"): 58000,
        (2024, "Q1", "3月"): 62000,
        (2024, "Q2", "4月"): 68000,
        (2024, "Q2", "5月"): 72000,
        (2024, "Q2", "6月"): 75000,
    }

    for (year, quarter, month), target in quarterly_data.items():
        count = random.randint(12, 20)
        remaining = target
        for i in range(count):
            if i == count - 1:
                amount = remaining
            else:
                min_amt = 1200
                max_amt = min(3500, max(min_amt, remaining - (count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount
            ws.append([year, quarter, month, amount])

    output_path = Path(__file__).parent / "data" / "H5_three_dims.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 H5: {output_path} (行数: {ws.max_row - 1}, 12个月份)")


if __name__ == "__main__":
    random.seed(20260825)
    print("开始生成P2阶段测试数据 Part 2...")
    generate_S7_two_dims()
    generate_S8_multi_metrics()
    generate_S9_multi_filter()
    generate_H1_date_ambiguity()
    generate_H2_field_similarity()
    generate_H4_complex_filter()
    generate_H5_nested_group()
    print("\n✓ S7-S9, H1-H2, H4-H5 数据生成完成！")
