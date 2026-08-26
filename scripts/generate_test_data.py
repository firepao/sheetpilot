"""
SheetPilot Agent Contract 测试数据生成器

生成真实业务场景的测试数据，包含：
- R1: 财务科目余额表（600行，借贷不平衡8条，空值12%）
- R2: 电商SKU库存（1500行，安全库存空值15%）
- R3: 人力薪资明细（800行，迟到扣款空值表示无迟到）
- R4: 客户订单流水（5000行，30%客户只下过1单）
- R5: 广告渠道投放（400行，含负ROI）
- R6: 物流配送记录（3000行，超时率18%）
- H3: 模糊字段选择（含销售额、销售金额含税、净销售收入）

使用方法：
    python scripts/generate_test_data.py --output tests/agent_contract/data
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from openpyxl import Workbook


def generate_r1_finance_ledger(output_path: Path) -> None:
    """R1: 财务科目余额表"""
    wb = Workbook()
    ws = wb.active
    ws.title = "科目余额表"

    # 表头
    ws.append(["科目编码", "科目名称", "一级科目", "科目类型", "借方金额", "贷方金额", "余额"])

    # 一级科目定义
    categories = {
        "资产": ["现金", "银行存款", "应收账款", "存货", "固定资产"],
        "负债": ["应付账款", "短期借款", "长期借款"],
        "权益": ["实收资本", "盈余公积"],
        "成本": ["主营业务成本", "管理费用"],
        "损益": ["主营业务收入", "投资收益"],
    }

    rows = []
    for category, accounts in categories.items():
        for account in accounts:
            for i in range(random.randint(10, 15)):
                code = f"{random.randint(1000, 9999)}"
                debit = round(random.uniform(1000, 50000), 2) if random.random() > 0.1 else 0
                credit = round(random.uniform(1000, 50000), 2) if random.random() > 0.1 else 0
                balance = debit - credit

                # 注入空值（12%）
                if random.random() < 0.12:
                    debit = None

                # 注入借贷不平衡（8条）
                if len(rows) < 8 and random.random() < 0.05:
                    balance = round(random.uniform(-1000, 1000), 2)

                rows.append([code, f"{account}{i+1}", account, category, debit, credit, balance])

    random.shuffle(rows)
    for row in rows[:600]:
        ws.append(row)

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (600 rows)")


def generate_r2_inventory_sku(output_path: Path) -> None:
    """R2: 电商SKU库存"""
    wb = Workbook()
    ws = wb.active
    ws.title = "SKU库存"

    ws.append(["SKU编码", "商品名称", "类目", "库存数量", "安全库存", "销售状态", "最后更新时间"])

    categories = ["服装", "电子产品", "食品", "图书", "家居", "美妆", "运动", "玩具"]
    statuses = ["在售", "下架", "清仓"]

    for i in range(1500):
        sku = f"SKU{str(i+1).zfill(6)}"
        category = random.choice(categories)
        name = f"{category}商品{i+1}"
        stock = random.randint(0, 500)
        safe_stock = random.randint(10, 100)
        status = random.choice(statuses)
        updated = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")

        # 注入安全库存空值（15%）
        if random.random() < 0.15:
            safe_stock = None

        ws.append([sku, name, category, stock, safe_stock, status, updated])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (1500 rows)")


def generate_h3_sales_multi_amount(output_path: Path) -> None:
    """H3: 模糊字段选择（三列金额：销售额、销售金额含税、净销售收入）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "销售明细"

    ws.append(["订单号", "区域", "销售额", "销售金额", "净销售收入", "退货金额", "订单日期"])

    regions = ["华北", "华东", "华南", "西南"]

    for i in range(200):
        order = f"ORD{str(i+1).zfill(6)}"
        region = random.choice(regions)
        base_amount = round(random.uniform(100, 5000), 2)
        tax_amount = round(base_amount * 1.13, 2)  # 含税 = 销售额 × 1.13
        refund = round(random.uniform(0, base_amount * 0.2), 2) if random.random() < 0.15 else 0
        net_amount = round(base_amount - refund, 2)  # 净销售收入 = 销售额 - 退货
        order_date = (datetime.now() - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d")

        ws.append([order, region, base_amount, tax_amount, net_amount, refund, order_date])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (200 rows, 3 amount columns)")


def generate_r3_hr_payroll(output_path: Path) -> None:
    """R3: 人力薪资明细（800行，迟到扣款空值表示无迟到）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "薪资明细"

    ws.append(["员工编号", "姓名", "部门", "职级", "基本工资", "绩效工资", "迟到扣款", "实发工资", "发放月份"])

    departments = ["研发", "产品", "运营", "销售", "市场", "财务", "人力", "行政"]
    levels = ["P5", "P6", "P7", "P8", "M1", "M2"]

    for i in range(804):  # 804行 = 67人 × 12个月
        emp_id = f"EMP{str(i % 67 + 1).zfill(4)}"
        name = f"员工{(i % 67) + 1}"
        dept = random.choice(departments)
        level = random.choice(levels)
        base_salary = random.randint(8000, 35000)
        performance = random.randint(0, 8000) if random.random() > 0.15 else 0
        late_deduction = random.randint(50, 500) if random.random() < 0.3 else None  # 30%有迟到，70%空值
        actual = base_salary + performance - (late_deduction if late_deduction else 0)
        month = f"2026-{str((i // 67) + 1).zfill(2)}"

        ws.append([emp_id, name, dept, level, base_salary, performance, late_deduction, actual, month])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (804 rows, 70% null in late_deduction)")


def generate_r4_customer_rfm(output_path: Path) -> None:
    """R4: 客户订单流水（6000行，用于RFM分析）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "订单流水"

    ws.append(["订单号", "客户编号", "客户名称", "订单金额", "订单日期", "订单状态"])

    statuses = ["已完成", "已取消", "退款中"]
    base_date = datetime(2026, 1, 1)

    # 300个客户，平均20单/客户
    customer_orders = {}
    for cid in range(1, 301):
        order_count = random.choices([1, 5, 20, 50], weights=[30, 30, 30, 10])[0]  # 30%只下过1单
        customer_orders[cid] = order_count

    order_id = 1
    for cid, order_count in customer_orders.items():
        for _ in range(order_count):
            order_no = f"ORD{str(order_id).zfill(8)}"
            customer_name = f"客户{cid}"
            amount = round(random.uniform(50, 5000), 2)
            days_ago = random.randint(1, 365)
            order_date = (base_date + timedelta(days=days_ago)).strftime("%Y-%m-%d")
            status = random.choices(statuses, weights=[85, 10, 5])[0]

            ws.append([order_no, f"C{str(cid).zfill(6)}", customer_name, amount, order_date, status])
            order_id += 1

            if order_id > 6000:
                break
        if order_id > 6000:
            break

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (6000 rows, 300 customers)")


def generate_r5_ad_roi(output_path: Path) -> None:
    """R5: 广告渠道投放（400行，含负ROI）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "广告投放"

    ws.append(["广告组ID", "渠道", "投放日期", "曝光量", "点击量", "消费金额", "转化金额", "ROI"])

    channels = ["百度搜索", "抖音信息流", "微信朋友圈", "小红书", "知乎", "B站"]

    for i in range(400):
        ad_id = f"AD{str(i+1).zfill(6)}"
        channel = random.choice(channels)
        ad_date = (datetime(2026, 1, 1) + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d")
        impressions = random.randint(1000, 100000)
        clicks = int(impressions * random.uniform(0.01, 0.05))
        cost = round(random.uniform(500, 20000), 2)

        # 20%广告ROI < 1.5，10%甚至是负ROI
        if random.random() < 0.1:
            revenue = round(cost * random.uniform(0.3, 0.9), 2)  # 负ROI
        elif random.random() < 0.2:
            revenue = round(cost * random.uniform(1.0, 1.4), 2)  # 低ROI
        else:
            revenue = round(cost * random.uniform(1.5, 5.0), 2)  # 高ROI

        roi = round(revenue / cost if cost > 0 else 0, 2)

        ws.append([ad_id, channel, ad_date, impressions, clicks, cost, revenue, roi])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (400 rows, 10% negative ROI)")


def generate_r6_logistics_timeout(output_path: Path) -> None:
    """R6: 物流配送记录（3000行，超时率18%）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "配送记录"

    ws.append(["运单号", "配送区域", "发货时间", "签收时间", "承诺时效(小时)", "实际时效(小时)", "是否超时"])

    regions = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]

    for i in range(3000):
        tracking = f"TRK{str(i+1).zfill(8)}"
        region = random.choice(regions)
        ship_time = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))
        promised = random.choice([24, 48, 72])

        # 18%超时
        if random.random() < 0.18:
            actual = promised + random.randint(1, 48)
            is_timeout = "是"
        else:
            actual = random.randint(int(promised * 0.5), promised)
            is_timeout = "否"

        receive_time = ship_time + timedelta(hours=actual)

        ws.append([
            tracking,
            region,
            ship_time.strftime("%Y-%m-%d %H:%M:%S"),
            receive_time.strftime("%Y-%m-%d %H:%M:%S"),
            promised,
            actual,
            is_timeout
        ])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (3000 rows, 18% timeout)")


def generate_all_datasets(output_dir: Path) -> None:
    """生成所有测试数据集"""
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating test datasets...")
    print("=" * 60)

    generate_r1_finance_ledger(output_dir / "R1_finance_ledger.xlsx")
    generate_r2_inventory_sku(output_dir / "R2_inventory_sku.xlsx")
    generate_r3_hr_payroll(output_dir / "R3_hr_payroll.xlsx")
    generate_r4_customer_rfm(output_dir / "R4_customer_rfm.xlsx")
    generate_r5_ad_roi(output_dir / "R5_ad_roi.xlsx")
    generate_r6_logistics_timeout(output_dir / "R6_logistics_timeout.xlsx")
    generate_h3_sales_multi_amount(output_dir / "H3_sales_multi_amount.xlsx")

    print("=" * 60)
    print("[OK] All datasets generated successfully!")
    print(f"\nOutput directory: {output_dir.resolve()}")
    print("\nNext steps:")
    print("1. Manually verify Oracle values by opening files in Excel")
    print("2. Update oracle_params in scenario JSON files")
    print("3. Run: python -m tests.agent_contract.runner --scenario-dir tests/agent_contract/scenarios")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        output = Path(sys.argv[1])
    else:
        output = Path(__file__).resolve().parents[1] / "tests/agent_contract/data"

    generate_all_datasets(output)
