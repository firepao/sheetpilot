"""
测试数据集生成脚本 - P2阶段扩充
生成 S2-S9, H1-H2, H4-H5, M1-M8 场景数据
"""
from __future__ import annotations

import random
import sys
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


# ============= S2: 单维度单指标 =============
def generate_S2_single_dim_metric():
    """S2: 最简单场景 - 单维度单指标无过滤"""
    wb = create_workbook("销售数据")
    ws = wb.active

    # 表头
    ws.append(["区域", "销售额"])

    # 5个产品，每个产品多条记录
    products = ["华东", "华南", "华北", "华中"]
    expected = {
        "华东": 115000,
        "华南": 98000,
        "华北": 82000,
        "华中": 65000,
    }

    for product in products:
        target = expected[product]
        # 每个产品生成10-15条记录
        count = random.randint(10, 15)
        remaining = target
        for i in range(count):
            if i == count - 1:
                amount = remaining
            else:
                amount = random.randint(1000, min(3000, remaining - (count - i - 1) * 1000))
                remaining -= amount
            ws.append([product, amount])

    output_path = Path(__file__).parent / "data" / "S2_single_dim_metric.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S2: {output_path} (行数: {ws.max_row - 1})")


# ============= S3: count.rows 基础 =============
def generate_S3_count_rows():
    """S3: 基础计数场景 - count.rows"""
    wb = create_workbook("订单数据")
    ws = wb.active

    # 表头
    ws.append(["订单号", "城市", "金额"])

    # 8个城市，订单数量不同
    cities = {
        "北京": 85, "上海": 72, "深圳": 58, "广州": 42,
        "杭州": 28, "成都": 18, "武汉": 12, "西安": 5
    }

    order_id = 1000
    for city, count in cities.items():
        for _ in range(count):
            amount = random.randint(100, 5000)
            ws.append([f"ORD{order_id}", city, amount])
            order_id += 1

    output_path = Path(__file__).parent / "data" / "S3_count_rows.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S3: {output_path} (行数: {ws.max_row - 1}, 总订单: 320)")


# ============= S4: count.non_empty 基础 =============
def generate_S4_count_non_empty():
    """S4: 基础非空计数场景 - count.non_empty"""
    wb = create_workbook("用户数据")
    ws = wb.active

    # 表头
    ws.append(["用户ID", "注册渠道", "邮箱"])

    # 10个省份，邮箱填充率不同
    provinces_data = [
        ("官网", 110, 170), ("APP", 95, 147), ("小程序", 80, 120),
    ]

    customer_id = 10001
    for province, email_count, total_count in provinces_data:
        # 有邮箱的客户
        for _ in range(email_count):
            email = f"user{customer_id}@example.com"
            ws.append([f"U{customer_id}", province, email])
            customer_id += 1
        # 无邮箱的客户
        for _ in range(total_count - email_count):
            ws.append([f"U{customer_id}", province, None])
            customer_id += 1

    output_path = Path(__file__).parent / "data" / "S4_count_non_empty.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S4: {output_path} (行数: {ws.max_row - 1}, 有邮箱: 285)")


# ============= S5: average 基础 =============
def generate_S5_average():
    """S5: 基础平均值场景 - average函数"""
    wb = create_workbook("成绩单")
    ws = wb.active

    # 表头
    ws.append(["班级", "学生姓名", "数学成绩"])

    # 6个班级，每班30人，平均分不同
    classes_avg = [
        ("高三1班", 85.5), ("高三2班", 83.2), ("高三3班", 81.8),
        ("高三4班", 79.5), ("高三5班", 77.3), ("高三6班", 75.8)
    ]

    student_id = 2024001
    for class_name, target_avg in classes_avg:
        scores = []
        for i in range(30):
            if i < 29:
                score = random.randint(int(target_avg - 15), int(target_avg + 15))
            else:
                # 最后一个成绩用于调整平均值
                current_sum = sum(scores)
                score = int(target_avg * 30 - current_sum)
                score = max(0, min(100, score))  # 确保在0-100范围内
            scores.append(score)
            ws.append([class_name, f"学生{student_id}", score])
            student_id += 1

    output_path = Path(__file__).parent / "data" / "S5_average.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S5: {output_path} (行数: {ws.max_row - 1}, 6个班级)")


# ============= S6: 单条件过滤 =============
def generate_S6_single_filter():
    """S6: 基础单条件过滤场景 - eq操作符"""
    wb = create_workbook("订单数据")
    ws = wb.active

    # 表头
    ws.append(["订单号", "产品名称", "订单金额", "支付状态"])

    # 8个产品，已支付和未支付混合
    products_paid = {
        "产品A": 65000, "产品B": 52000, "产品C": 48000, "产品D": 38000,
        "产品E": 28000, "产品F": 22000, "产品G": 18000, "产品H": 9000
    }

    order_id = 5000
    for product, paid_amount in products_paid.items():
        # 已支付订单
        paid_count = random.randint(8, 15)
        remaining = paid_amount
        for i in range(paid_count):
            if i == paid_count - 1:
                amount = remaining
            else:
                min_amount = 1000
                max_amount = min(6000, max(min_amount, remaining - (paid_count - i - 1) * min_amount))
                amount = random.randint(min_amount, max_amount)
                remaining -= amount
            ws.append([f"O{order_id}", product, amount, "已支付"])
            order_id += 1

        # 未支付订单（金额随机，不计入expected）
        unpaid_count = random.randint(3, 8)
        for _ in range(unpaid_count):
            amount = random.randint(1000, 6000)
            ws.append([f"O{order_id}", product, amount, "未支付"])
            order_id += 1

    output_path = Path(__file__).parent / "data" / "S6_single_filter.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 S6: {output_path} (行数: {ws.max_row - 1}, 已支付总额: 280000)")


if __name__ == "__main__":
    random.seed(20260825)
    print("开始生成P2阶段测试数据...")
    generate_S2_single_dim_metric()
    generate_S3_count_rows()
    generate_S4_count_non_empty()
    generate_S5_average()
    generate_S6_single_filter()
    print("\n✓ S2-S6 数据生成完成！")
