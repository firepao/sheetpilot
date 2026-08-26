"""
SheetPilot 测试数据集生成器 V2 - 真实业务场景

基于SpreadsheetBench/FINCH/Alpha Excel学术基准的发现，生成真实复杂度测试数据：
- R3: 人力薪资计算（800行，空值语义NULL vs 0）
- R4: 客户RFM分析（5000行，30%客户仅1单）
- R5: 广告渠道ROI（400行，含负ROI）
- R6: 物流配送超时（3000行，超时率18%）

使用方法：
    python scripts/generate_real_scenarios.py --output tests/agent_contract/data
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from openpyxl import Workbook


def generate_r3_hr_payroll(output_path: Path) -> None:
    """R3: 人力薪资计算 - 800行，迟到扣款空值表示无迟到"""
    wb = Workbook()
    ws = wb.active
    ws.title = "薪资明细"

    ws.append(["员工编号", "姓名", "部门", "基本工资", "绩效奖金", "迟到扣款", "社保个人", "个税", "月份"])

    departments = ["技术部", "销售部", "市场部", "财务部", "人力资源"]
    months = [f"2025-{str(m).zfill(2)}" for m in range(1, 13)]

    for emp_id in range(1, 68):  # 67名员工 × 12个月 = 804行
        name = f"员工{str(emp_id).zfill(3)}"
        dept = random.choice(departments)
        base = random.choice([8000, 10000, 12000, 15000, 18000, 20000])

        for month in months:
            bonus = round(random.uniform(0, base * 0.3), 2) if random.random() > 0.2 else 0
            # 迟到扣款：空值表示无迟到（语义重点）
            late_deduction = round(random.uniform(50, 500), 2) if random.random() < 0.25 else None
            social = round(base * 0.105, 2)  # 社保10.5%
            tax = round((base + bonus - (late_deduction or 0) - social - 5000) * 0.1, 2) if (base + bonus - social) > 5000 else 0

            ws.append([f"EMP{str(emp_id).zfill(3)}", name, dept, base, bonus, late_deduction, social, tax, month])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (804 rows, NULL semantics test)")


def generate_r4_customer_rfm(output_path: Path) -> None:
    """R4: 客户RFM分析 - 5000行，30%客户只下过1单"""
    wb = Workbook()
    ws = wb.active
    ws.title = "订单流水"

    ws.append(["订单号", "客户编号", "订单日期", "订单金额", "订单状态"])

    # 生成客户池：500个客户，其中150个（30%）只下1单
    num_customers = 500
    one_time_customers = 150

    customer_orders = {}
    for cid in range(1, num_customers + 1):
        if cid <= one_time_customers:
            customer_orders[cid] = 1  # 30%客户只下1单
        else:
            customer_orders[cid] = random.randint(2, 30)  # 其他客户2-30单

    order_id = 1
    today = datetime.now()

    for cid, order_count in customer_orders.items():
        for _ in range(order_count):
            days_ago = random.randint(0, 730)  # 过去2年内
            order_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            amount = round(random.uniform(50, 5000), 2)
            status = random.choice(["已完成"] * 85 + ["已取消"] * 10 + ["退货"] * 5)

            ws.append([f"ORD{str(order_id).zfill(6)}", f"C{str(cid).zfill(4)}", order_date, amount, status])
            order_id += 1

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} ({order_id - 1} rows, 30% one-time customers)")


def generate_r5_ad_roi(output_path: Path) -> None:
    """R5: 广告渠道ROI - 400行，含负ROI"""
    wb = Workbook()
    ws = wb.active
    ws.title = "广告投放"

    ws.append(["日期", "渠道", "曝光量", "点击量", "转化量", "投放成本", "销售收入"])

    channels = ["百度SEM", "头条信息流", "抖音短视频", "微信朋友圈", "小红书种草", "知乎内容", "B站UP主", "淘宝直通车"]
    start_date = datetime(2025, 7, 1)

    for day in range(50):  # 50天
        current_date = (start_date + timedelta(days=day)).strftime("%Y-%m-%d")

        for channel in channels:
            impressions = random.randint(10000, 500000)
            clicks = round(impressions * random.uniform(0.005, 0.03))  # CTR 0.5%-3%
            conversions = round(clicks * random.uniform(0.01, 0.08))  # CVR 1%-8%
            cost = round(random.uniform(500, 5000), 2)

            # 收入：正常ROI 0.5-3.0，但10%概率负ROI（成本>收入）
            if random.random() < 0.1:
                revenue = round(cost * random.uniform(0.3, 0.9), 2)  # 负ROI
            else:
                revenue = round(cost * random.uniform(1.2, 4.0), 2)  # 正ROI

            ws.append([current_date, channel, impressions, clicks, conversions, cost, revenue])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (400 rows, ~10% negative ROI)")


def generate_r6_logistics_timeout(output_path: Path) -> None:
    """R6: 物流配送超时 - 3000行，超时率18%"""
    wb = Workbook()
    ws = wb.active
    ws.title = "配送记录"

    ws.append(["运单号", "配送类型", "发货时间", "承诺时效(小时)", "实际签收时间", "收货城市"])

    types = ["同城", "省内", "跨省"]
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安", "南京", "重庆"]
    sla_hours = {"同城": 24, "省内": 48, "跨省": 72}

    start_date = datetime(2025, 6, 1)

    for i in range(3000):
        waybill = f"WB{str(i + 1).zfill(6)}"
        delivery_type = random.choice(types)
        ship_time = start_date + timedelta(hours=random.randint(0, 60 * 24))
        sla = sla_hours[delivery_type]

        # 18%超时：实际时效 > 承诺时效
        if random.random() < 0.18:
            actual_hours = round(sla * random.uniform(1.1, 2.5), 1)  # 超时10%-150%
        else:
            actual_hours = round(sla * random.uniform(0.3, 0.95), 1)  # 正常30%-95%

        sign_time = ship_time + timedelta(hours=actual_hours)
        city = random.choice(cities)

        ws.append([
            waybill,
            delivery_type,
            ship_time.strftime("%Y-%m-%d %H:%M"),
            sla,
            sign_time.strftime("%Y-%m-%d %H:%M"),
            city
        ])

    wb.save(output_path)
    wb.close()
    print(f"[OK] Generated: {output_path} (3000 rows, 18% timeout rate)")


def generate_all_real_scenarios(output_dir: Path) -> None:
    """生成所有真实场景数据集"""
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating real business scenario datasets...")
    print("=" * 60)

    generate_r3_hr_payroll(output_dir / "R3_hr_payroll.xlsx")
    generate_r4_customer_rfm(output_dir / "R4_customer_rfm.xlsx")
    generate_r5_ad_roi(output_dir / "R5_ad_roi.xlsx")
    generate_r6_logistics_timeout(output_dir / "R6_logistics_timeout.xlsx")

    print("=" * 60)
    print("[OK] All real scenario datasets generated!")
    print(f"\nOutput directory: {output_dir.resolve()}")
    print("\nNext steps:")
    print("1. Open files in Excel and manually calculate Oracle values")
    print("2. Create scenario JSON files in tests/agent_contract/scenarios/")
    print("3. Update oracle_params with verified expected values")
    print("4. Test with: python -m tests.agent_contract.runner --scenario R3")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        output = Path(sys.argv[1])
    else:
        output = Path(__file__).resolve().parents[1] / "tests/agent_contract/data"

    generate_all_real_scenarios(output)
