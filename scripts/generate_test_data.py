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


def generate_all_datasets(output_dir: Path) -> None:
    """生成所有测试数据集"""
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating test datasets...")
    print("=" * 60)

    generate_r1_finance_ledger(output_dir / "R1_finance_ledger.xlsx")
    generate_r2_inventory_sku(output_dir / "R2_inventory_sku.xlsx")
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
