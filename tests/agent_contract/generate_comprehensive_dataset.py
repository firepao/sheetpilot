"""Generate realistic multi-sheet workbooks for the capability benchmark pack."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from random import Random

from openpyxl import Workbook


ROOT = Path(__file__).parent
DATA = ROOT / "data"


def write_sheet(wb: Workbook, name: str, headers: list[str], rows: list[list[object]]) -> None:
    ws = wb.create_sheet(name)
    ws.append(headers)
    for row in rows:
        ws.append(row)


def retail() -> None:
    wb = Workbook(); wb.remove(wb.active)
    products = [["SKU-001", "无线键盘", "办公外设", 129, 76], ["SKU-002", "人体工学鼠标", "办公外设", 89, 52], ["SKU-003", "显示器支架", "办公家具", 249, 120], ["SKU-004", "会议摄像头", "会议设备", 699, 410], ["SKU-005", "USB-C扩展坞", "办公外设", 329, 180]]
    orders = []
    for i in range(1, 61):
        sku = products[(i - 1) % len(products)]
        status = "已完成" if i % 11 else "已取消"
        orders.append([f"O-{i:04d}", date(2024, 7, 1) + timedelta(days=i % 31), ["华东", "华南", "华北"][i % 3], ["企业客户", "个人客户"][i % 2], sku[0], sku[1], sku[2], 1 + i % 4, sku[3] * (1 + i % 4), status, "否" if i % 13 else "是", f"C-{i % 19:03d}" if i % 9 else None])
    write_sheet(wb, "订单明细", ["订单号", "下单日期", "区域", "客户类型", "SKU", "商品名称", "品类", "数量", "订单金额", "订单状态", "是否退货", "客户编号"], orders)
    write_sheet(wb, "商品主数据", ["SKU", "商品名称", "品类", "标准售价", "标准成本"], products)
    write_sheet(wb, "渠道映射", ["区域", "负责人", "渠道等级"], [["华东", "李敏", "A"], ["华南", "周强", "B"], ["华北", "王芳", "A"]])
    wb.save(DATA / "B1_retail_operations.xlsx")


def finance() -> None:
    wb = Workbook(); wb.remove(wb.active)
    accounts = [["1001", "库存现金", "资产", 120000, 118000], ["1122", "应收账款", "资产", 870000, 842000], ["1405", "库存商品", "资产", 630000, 641000], ["2202", "应付账款", "负债", 420000, 433000], ["6001", "主营业务收入", "损益", 0, 1250000], ["6401", "主营业务成本", "损益", 0, 760000]]
    entries = [[f"V-{i:04d}", date(2024, 8, 1) + timedelta(days=i % 30), accounts[i % len(accounts)][0], accounts[i % len(accounts)][1], "借" if i % 2 else "贷", (i + 1) * 137, "已审核" if i % 17 else "待审核", f"凭证摘要{i % 6}"] for i in range(1, 81)]
    write_sheet(wb, "科目余额", ["科目编码", "科目名称", "科目类别", "期初余额", "期末余额"], accounts)
    write_sheet(wb, "凭证明细", ["凭证号", "记账日期", "科目编码", "科目名称", "借贷方向", "金额", "审核状态", "摘要"], entries)
    write_sheet(wb, "对账基准", ["科目编码", "系统余额", "银行/业务余额", "差异原因"], [[a[0], a[4], a[4] + (5000 if i == 1 else 0), "期末在途" if i == 1 else None] for i, a in enumerate(accounts)])
    wb.save(DATA / "B2_finance_close.xlsx")


def supply() -> None:
    wb = Workbook(); wb.remove(wb.active)
    suppliers = [["SUP-01", "华东电子", "芯片", "合格"], ["SUP-02", "南方精工", "结构件", "合格"], ["SUP-03", "北方包装", "包材", "观察"]]
    po = [[f"PO-{i:04d}", date(2024, 8, 1) + timedelta(days=i % 25), suppliers[i % 3][0], suppliers[i % 3][1], suppliers[i % 3][2], 100 + i % 70, 20 + i % 5, 0.92 if i % 9 else 0.75, "已收货" if i % 8 else "在途"] for i in range(1, 46)]
    stock = [[f"SKU-{i:03d}", ["芯片", "结构件", "包材"][i % 3], 30 + i % 80, 45 + i % 30, "正常" if i % 7 else "冻结"] for i in range(1, 31)]
    write_sheet(wb, "采购订单", ["采购单号", "下单日期", "供应商编码", "供应商名称", "物料类别", "采购数量", "含税单价", "质检合格率", "收货状态"], po)
    write_sheet(wb, "库存快照", ["SKU", "物料类别", "现有库存", "安全库存", "库存状态"], stock)
    write_sheet(wb, "供应商主数据", ["供应商编码", "供应商名称", "主供类别", "合作状态"], suppliers)
    wb.save(DATA / "B3_supply_chain.xlsx")


def workforce() -> None:
    wb = Workbook(); wb.remove(wb.active)
    rows = []
    for i in range(1, 71):
        dept = ["销售", "研发", "客服", "财务"][i % 4]
        rows.append([f"E-{i:04d}", f"员工{i:03d}", dept, ["正式", "试用", "离职"][i % 3 if i % 13 else 2], 7000 + i * 83, 168 + i % 24, 12 + i % 18, "优秀" if i % 5 == 0 else "良好" if i % 3 == 0 else "合格", f"P-{i % 9:02d}"])
    write_sheet(wb, "员工月度绩效", ["员工编号", "员工姓名", "部门", "在职状态", "实发工资", "标准工时", "实际工时", "绩效等级", "项目编号"], rows)
    write_sheet(wb, "部门目标", ["部门", "月度预算", "人数上限", "负责人"], [["销售", 520000, 30, "陈晨"], ["研发", 680000, 25, "刘洋"], ["客服", 310000, 20, "赵敏"], ["财务", 260000, 12, "孙磊"]])
    wb.save(DATA / "B4_workforce.xlsx")


def marketing() -> None:
    wb = Workbook(); wb.remove(wb.active)
    rows = []
    for i in range(1, 51):
        channel = ["搜索广告", "短视频", "社交媒体", "线下活动"][i % 4]
        rows.append([f"AD-{i:04d}", date(2024, 8, 1) + timedelta(days=i % 30), channel, 5000 + i * 127, 80000 + i * 931, 1500 + i * 37, 60 + i % 80, 12000 + i * 311, "启用" if i % 12 else "暂停"])
    write_sheet(wb, "投放明细", ["广告组", "投放日期", "渠道", "投放金额", "曝光量", "点击量", "转化量", "归因销售额", "状态"], rows)
    write_sheet(wb, "渠道目标", ["渠道", "月预算", "目标ROI", "负责人"], [["搜索广告", 180000, 4.5, "何静"], ["短视频", 220000, 5.0, "高峰"], ["社交媒体", 160000, 3.8, "林雪"], ["线下活动", 120000, 2.5, "吴迪"]])
    wb.save(DATA / "B5_marketing_funnel.xlsx")


def objects() -> None:
    wb = Workbook(); wb.remove(wb.active)
    write_sheet(wb, "运营看板", ["月份", "销售额", "订单数", "客单价"], [["2024-06", 820000, 420, 1952], ["2024-07", 910000, 468, 1944], ["2024-08", 1030000, 512, 2012]])
    ws = wb["运营看板"]; ws["E1"] = "同比增长"; ws["E2"] = "=B2/700000-1"; ws["E3"] = "=B3/B2-1"; ws["E4"] = "=B4/B3-1"
    ws["G1"] = "说明"; ws["G2"] = "公式和对象保真测试"; ws["A6"] = "可发布"; ws["B6"] = "是"
    wb.save(DATA / "B6_workbook_objects.xlsx")


def workbook_admin() -> None:
    wb = Workbook(); ws = wb.active; ws.title = "月度报表"
    ws.append(["部门", "本月销售额", "目标", "达成率"])
    for row in [["销售", 120000, 100000, "=B2/C2"], ["客服", 76000, 80000, "=B3/C3"], ["研发", 43000, 40000, "=B4/C4"]]: ws.append(row)
    ws.merge_cells("A6:D6"); ws["A6"] = "管理层月度报表"
    ws.freeze_panes = "A2"; ws.auto_filter.ref = "A1:D4"
    ws.column_dimensions["A"].width = 14; ws.column_dimensions["B"].width = 16; ws.column_dimensions["C"].width = 12; ws.column_dimensions["D"].width = 12
    ws.protection.sheet = False
    wb.create_sheet("模板"); wb.save(DATA / "B7_workbook_admin.xlsx")


def data_quality() -> None:
    wb = Workbook(); wb.remove(wb.active)
    rows = [["客户编号", "客户名称", "地区", "订单状态", "订单金额", "负责人"], ["C001", "华星", "华东", "有效", 1200, "李敏"], ["C001", "华星", "华东", "有效", 1200, "李敏"], ["C002", "远航", "华南", "待补", None, ""], ["C003", "新锐", "华北", "有效", 900, "王芳"], ["C004", "", "华东", "有效", 500, "赵强"]]
    ws = wb.create_sheet("客户订单"); [ws.append(r) for r in rows]
    wb.create_sheet("字段说明").append(["字段", "口径", "必填"]); wb["字段说明"].append(["订单金额", "含税金额", "是"]); wb["字段说明"].append(["负责人", "销售负责人", "否"])
    wb.save(DATA / "B8_data_quality.xlsx")


def publication() -> None:
    wb = Workbook(); wb.remove(wb.active)
    ws = wb.create_sheet("经营数据"); ws.append(["月份", "收入", "成本", "利润"])
    for i, row in enumerate([["2024-06", 820000, 510000], ["2024-07", 910000, 560000], ["2024-08", 1030000, 620000]], 2): ws.append([*row, f"=B{i}-C{i}"])
    wb.create_sheet("参数").append(["报告名称", "月度经营简报"])
    wb.save(DATA / "B9_report_publication.xlsx")


def maintenance() -> None:
    wb = Workbook(); wb.remove(wb.active)
    ws = wb.create_sheet("交付清单"); ws.append(["项目", "负责人", "状态", "链接"]); ws.append(["Q3经营复盘", "林雪", "待发布", "https://example.com/q3"]); ws.append(["库存专项", "周强", "已完成", "https://example.com/stock"])
    ws.merge_cells("A5:D5"); ws["A5"] = "交付附件"
    wb.create_sheet("说明").append(["版本", "v2.0"])
    wb.save(DATA / "B10_delivery_maintenance.xlsx")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for fn in (retail, finance, supply, workforce, marketing, objects, workbook_admin, data_quality, publication, maintenance): fn()


if __name__ == "__main__": main()
