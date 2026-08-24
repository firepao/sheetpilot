"""
测试数据集生成脚本 - P2阶段扩充 Part 3
生成 M1-M8 场景数据（中等复杂度）
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
    # 设置表头字体为粗体
    for cell in ws[1]:
        cell.font = Font(bold=True)
    return wb


# ============= M1: 电商订单分析 =============
def generate_M1_ecommerce():
    """M1: 电商订单分析 - 多维度+多过滤+多指标"""
    wb = create_workbook("订单明细")
    ws = wb.active

    # 表头
    ws.append(["订单号", "商品类目", "城市", "订单金额", "订单状态", "支付方式", "客户ID"])

    categories = ["数码", "服装", "食品", "家居", "美妆"]
    cities = ["北京", "上海", "深圳", "广州", "杭州", "成都"]
    statuses = ["已完成", "已取消", "退货"]
    payments = ["支付宝", "微信", "银行卡"]

    # 目标：订单状态=已完成 AND 支付方式=支付宝
    target_by_category_city = {
        ("数码", "北京"): 85000,
        ("数码", "上海"): 78000,
        ("数码", "深圳"): 72000,
        ("服装", "北京"): 62000,
        ("服装", "上海"): 58000,
        ("服装", "深圳"): 52000,
        ("食品", "北京"): 48000,
        ("食品", "上海"): 42000,
        ("家居", "北京"): 38000,
        ("美妆", "上海"): 32000,
    }

    order_id = 100001
    customer_id_base = 50001

    for (category, city), target in target_by_category_city.items():
        # 符合条件的订单
        count = random.randint(15, 25)
        remaining = target
        for i in range(count):
            if i == count - 1:
                amount = remaining
            else:
                min_amt = 2000
                max_amt = min(5000, max(min_amt, remaining - (count - i - 1) * min_amt))
                amount = random.randint(min_amt, max_amt)
                remaining -= amount
            ws.append([f"O{order_id}", category, city, amount, "已完成", "支付宝", f"C{customer_id_base + i}"])
            order_id += 1

        # 噪声订单（不符合条件）
        noise_count = random.randint(8, 15)
        for _ in range(noise_count):
            amount = random.randint(500, 8000)
            status = random.choice(statuses)
            payment = random.choice(payments)
            # 确保不是目标组合
            if status == "已完成" and payment == "支付宝":
                status = random.choice(["已取消", "退货"])
            ws.append([f"O{order_id}", category, city, amount, status, payment, f"C{random.randint(50001, 59999)}"])
            order_id += 1

    output_path = Path(__file__).parent / "data" / "M1_ecommerce_orders.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M1: {output_path} (行数: {ws.max_row - 1}, 10个类目城市组合)")


# ============= M2: 员工绩效考核 =============
def generate_M2_performance():
    """M2: 员工绩效考核 - 多指标汇总+排序"""
    wb = create_workbook("绩效数据")
    ws = wb.active

    # 表头
    ws.append(["员工ID", "姓名", "部门", "销售额", "客户数", "投诉次数", "考勤天数"])

    departments = ["销售一部", "销售二部", "销售三部", "销售四部"]

    dept_targets = {
        "销售一部": (450000, 180, 8, 22),
        "销售二部": (380000, 150, 12, 22),
        "销售三部": (320000, 128, 15, 21),
        "销售四部": (280000, 110, 18, 21),
    }

    emp_id = 10001
    for dept, (sales_target, customer_target, complaint_total, attendance_avg) in dept_targets.items():
        emp_count = random.randint(15, 25)

        # 生成员工数据
        sales_list = []
        customer_list = []
        for i in range(emp_count):
            # 销售额分配
            if i == emp_count - 1:
                sales = sales_target - sum(sales_list)
            else:
                min_sales = 10000
                max_sales = min(30000, max(min_sales, (sales_target - sum(sales_list)) // (emp_count - i)))
                sales = random.randint(min_sales, max_sales)
            sales_list.append(sales)

            # 客户数分配
            if i == emp_count - 1:
                customers = customer_target - sum(customer_list)
            else:
                min_cust = 3
                max_cust = min(15, max(min_cust, (customer_target - sum(customer_list)) // (emp_count - i)))
                customers = random.randint(min_cust, max_cust)
            customer_list.append(customers)

            complaints = random.randint(0, 3)
            attendance = random.randint(20, 22)

            name = f"员工{emp_id}"
            ws.append([emp_id, name, dept, sales, customers, complaints, attendance])
            emp_id += 1

    output_path = Path(__file__).parent / "data" / "M2_employee_performance.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M2: {output_path} (行数: {ws.max_row - 1}, 4个部门)")


# ============= M3: 库存周转分析 =============
def generate_M3_inventory():
    """M3: 库存周转分析 - 多维度+计算字段"""
    wb = create_workbook("库存数据")
    ws = wb.active

    # 表头
    ws.append(["SKU编号", "产品名称", "仓库", "期初库存", "入库数量", "出库数量", "期末库存", "库存状态"])

    warehouses = ["华东仓", "华南仓", "华北仓"]
    products = [
        ("手机壳", 50), ("充电器", 40), ("数据线", 35), ("耳机", 30),
        ("保护膜", 25), ("支架", 20), ("清洁套装", 15)
    ]

    sku_id = 200001
    for warehouse in warehouses:
        for product, base_stock in products:
            beginning = random.randint(base_stock * 20, base_stock * 30)
            inbound = random.randint(base_stock * 10, base_stock * 15)
            outbound = random.randint(base_stock * 12, base_stock * 18)
            ending = beginning + inbound - outbound

            # 库存状态判断
            if ending < base_stock * 10:
                status = "预警"
            elif ending > base_stock * 35:
                status = "积压"
            else:
                status = "正常"

            ws.append([f"SKU{sku_id}", product, warehouse, beginning, inbound, outbound, ending, status])
            sku_id += 1

    output_path = Path(__file__).parent / "data" / "M3_inventory_turnover.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M3: {output_path} (行数: {ws.max_row - 1}, 21个SKU)")


# ============= M4: 营销渠道ROI =============
def generate_M4_marketing():
    """M4: 营销渠道ROI - 多指标计算+排序"""
    wb = create_workbook("渠道数据")
    ws = wb.active

    # 表头
    ws.append(["渠道名称", "投放日期", "投放金额", "曝光量", "点击量", "转化量", "销售额"])

    channels = ["百度搜索", "抖音信息流", "微信朋友圈", "知乎广告", "小红书"]

    # 生成30天数据
    base_date = datetime(2024, 7, 1)

    for day in range(30):
        current_date = base_date + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d")

        for channel in channels:
            # 不同渠道有不同的ROI特征
            if channel == "百度搜索":
                cost = random.randint(8000, 15000)
                impressions = random.randint(150000, 300000)
                clicks = random.randint(3000, 6000)
                conversions = random.randint(150, 300)
                revenue = conversions * random.randint(280, 450)
            elif channel == "抖音信息流":
                cost = random.randint(12000, 20000)
                impressions = random.randint(500000, 1000000)
                clicks = random.randint(8000, 15000)
                conversions = random.randint(200, 400)
                revenue = conversions * random.randint(250, 380)
            elif channel == "微信朋友圈":
                cost = random.randint(10000, 18000)
                impressions = random.randint(300000, 600000)
                clicks = random.randint(5000, 10000)
                conversions = random.randint(180, 350)
                revenue = conversions * random.randint(300, 480)
            elif channel == "知乎广告":
                cost = random.randint(6000, 12000)
                impressions = random.randint(100000, 200000)
                clicks = random.randint(2000, 4000)
                conversions = random.randint(100, 200)
                revenue = conversions * random.randint(350, 550)
            else:  # 小红书
                cost = random.randint(8000, 16000)
                impressions = random.randint(200000, 400000)
                clicks = random.randint(4000, 8000)
                conversions = random.randint(150, 300)
                revenue = conversions * random.randint(320, 500)

            ws.append([channel, date_str, cost, impressions, clicks, conversions, revenue])

    output_path = Path(__file__).parent / "data" / "M4_marketing_roi.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M4: {output_path} (行数: {ws.max_row - 1}, 30天×5渠道)")


# ============= M5: 课程学员统计 =============
def generate_M5_courses():
    """M5: 课程学员统计 - 多维度分组"""
    wb = create_workbook("学员数据")
    ws = wb.active

    # 表头
    ws.append(["学员ID", "姓名", "课程名称", "课程类型", "学习时长(小时)", "完成度(%)", "考试成绩", "付费金额"])

    courses = [
        ("Python基础", "编程", 399),
        ("数据分析实战", "数据", 599),
        ("机器学习入门", "AI", 899),
        ("前端开发", "编程", 499),
        ("产品经理", "产品", 699),
        ("UI设计", "设计", 799),
    ]

    student_id = 300001
    for course_name, course_type, price in courses:
        student_count = random.randint(80, 150)

        for _ in range(student_count):
            study_hours = random.randint(10, 200)
            completion = random.randint(30, 100)
            score = random.randint(50, 100) if completion > 80 else random.randint(0, 85)
            paid = price if random.random() > 0.15 else 0  # 85%付费率

            name = f"学员{student_id}"
            ws.append([student_id, name, course_name, course_type, study_hours, completion, score, paid])
            student_id += 1

    output_path = Path(__file__).parent / "data" / "M5_course_statistics.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M5: {output_path} (行数: {ws.max_row - 1}, 6门课程)")


# ============= M6: 供应商采购分析 =============
def generate_M6_suppliers():
    """M6: 供应商采购分析 - 多指标评估"""
    wb = create_workbook("采购记录")
    ws = wb.active

    # 表头
    ws.append(["采购单号", "供应商", "物料名称", "采购数量", "单价", "总金额", "交货天数", "合格率(%)", "采购日期"])

    suppliers = ["供应商A", "供应商B", "供应商C", "供应商D", "供应商E"]
    materials = [
        ("钢材", 1200, 1500),
        ("铝材", 800, 1000),
        ("塑料", 300, 500),
        ("电子元件", 50, 100),
        ("包装材料", 150, 250),
    ]

    po_id = 400001
    base_date = datetime(2024, 1, 1)

    for month in range(6):  # 6个月数据
        for supplier in suppliers:
            purchase_count = random.randint(8, 15)

            for _ in range(purchase_count):
                material, min_qty, max_qty = random.choice(materials)
                quantity = random.randint(min_qty, max_qty)

                # 不同供应商有不同的价格和质量特征
                if supplier == "供应商A":
                    unit_price = random.randint(80, 120)
                    delivery_days = random.randint(3, 7)
                    qualified_rate = random.randint(92, 98)
                elif supplier == "供应商B":
                    unit_price = random.randint(75, 110)
                    delivery_days = random.randint(5, 10)
                    qualified_rate = random.randint(88, 95)
                elif supplier == "供应商C":
                    unit_price = random.randint(70, 105)
                    delivery_days = random.randint(7, 14)
                    qualified_rate = random.randint(85, 93)
                elif supplier == "供应商D":
                    unit_price = random.randint(85, 125)
                    delivery_days = random.randint(2, 5)
                    qualified_rate = random.randint(94, 99)
                else:  # 供应商E
                    unit_price = random.randint(65, 100)
                    delivery_days = random.randint(10, 20)
                    qualified_rate = random.randint(80, 90)

                total_amount = quantity * unit_price
                date_offset = random.randint(month * 30, (month + 1) * 30 - 1)
                purchase_date = (base_date + timedelta(days=date_offset)).strftime("%Y-%m-%d")

                ws.append([f"PO{po_id}", supplier, material, quantity, unit_price, total_amount,
                          delivery_days, qualified_rate, purchase_date])
                po_id += 1

    output_path = Path(__file__).parent / "data" / "M6_supplier_analysis.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M6: {output_path} (行数: {ws.max_row - 1}, 5个供应商)")


# ============= M7: 客户投诉分析 =============
def generate_M7_complaints():
    """M7: 客户投诉分析 - 多维度统计"""
    wb = create_workbook("投诉记录")
    ws = wb.active

    # 表头
    ws.append(["投诉单号", "客户姓名", "投诉类型", "产品类别", "严重程度", "处理状态", "响应时长(小时)", "满意度", "登记日期"])

    complaint_types = ["产品质量", "物流配送", "售后服务", "价格问题", "虚假宣传"]
    product_cats = ["数码", "家电", "服装", "食品", "家居"]
    severities = ["低", "中", "高"]
    statuses = ["已解决", "处理中", "已关闭"]
    satisfactions = [1, 2, 3, 4, 5]

    complaint_id = 500001
    base_date = datetime(2024, 1, 1)

    for month in range(6):
        complaint_count = random.randint(50, 100)

        for _ in range(complaint_count):
            complaint_type = random.choice(complaint_types)
            product = random.choice(product_cats)
            severity = random.choice(severities)
            status = random.choice(statuses)

            # 响应时长根据严重程度不同
            if severity == "高":
                response_hours = random.randint(1, 8)
            elif severity == "中":
                response_hours = random.randint(4, 24)
            else:
                response_hours = random.randint(12, 48)

            # 满意度根据状态不同
            if status == "已解决":
                satisfaction = random.choice([3, 4, 5])
            elif status == "处理中":
                satisfaction = random.choice([2, 3, 4])
            else:
                satisfaction = random.choice([1, 2, 3])

            date_offset = random.randint(month * 30, (month + 1) * 30 - 1)
            complaint_date = (base_date + timedelta(days=date_offset)).strftime("%Y-%m-%d")

            customer_name = f"客户{random.randint(10001, 19999)}"

            ws.append([f"CP{complaint_id}", customer_name, complaint_type, product, severity,
                      status, response_hours, satisfaction, complaint_date])
            complaint_id += 1

    output_path = Path(__file__).parent / "data" / "M7_complaint_analysis.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M7: {output_path} (行数: {ws.max_row - 1}, 6个月数据)")


# ============= M8: 项目工时统计 =============
def generate_M8_project_hours():
    """M8: 项目工时统计 - 多维度汇总"""
    wb = create_workbook("工时记录")
    ws = wb.active

    # 表头
    ws.append(["工时ID", "员工姓名", "项目名称", "任务类型", "工作日期", "工时(小时)", "是否加班", "工作内容"])

    projects = ["项目A", "项目B", "项目C", "项目D"]
    task_types = ["需求分析", "设计", "开发", "测试", "部署"]
    employees = [f"员工{i}" for i in range(1, 21)]

    timesheet_id = 600001
    base_date = datetime(2024, 7, 1)

    for day in range(30):
        current_date = base_date + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d")

        # 每天每个员工提交工时
        for emp in employees:
            project = random.choice(projects)
            task_type = random.choice(task_types)
            hours = random.choice([6, 7, 8, 9, 10])
            overtime = "是" if hours >= 9 else "否"
            content = f"{task_type}相关工作"

            ws.append([timesheet_id, emp, project, task_type, date_str, hours, overtime, content])
            timesheet_id += 1

    output_path = Path(__file__).parent / "data" / "M8_project_hours.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"✓ 生成 M8: {output_path} (行数: {ws.max_row - 1}, 30天×20人)")


if __name__ == "__main__":
    print("开始生成P2阶段测试数据 Part 3 (M系列)...")
    generate_M1_ecommerce()
    generate_M2_performance()
    generate_M3_inventory()
    generate_M4_marketing()
    generate_M5_courses()
    generate_M6_suppliers()
    generate_M7_complaints()
    generate_M8_project_hours()
    print("\n✓ M1-M8 数据生成完成！")
