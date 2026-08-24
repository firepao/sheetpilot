"""
为现有测试数据注入真实脏度

根据调研报告，真实Excel数据的常见问题：
- 空值率：10-15%
- 格式不一致：日期格式、数字格式、大小写
- 异常状态：15-20%非正常状态
- 重复记录：2-5%

使用方法：
    python scripts/inject_dirty_data.py --input tests/agent_contract/data/01_simple_department_sales.xlsx
    python scripts/inject_dirty_data.py --batch tests/agent_contract/data
"""
from __future__ import annotations

import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook


def inject_dirty_to_file(input_path: Path, backup: bool = True) -> dict[str, int]:
    """为单个文件注入脏数据"""

    if backup:
        backup_path = input_path.with_suffix('.xlsx.backup')
        shutil.copy2(input_path, backup_path)
        print(f"[Backup] {backup_path}")

    wb = load_workbook(input_path)
    ws = wb.active

    stats = {
        "total_rows": ws.max_row - 1,  # 减去表头
        "null_injected": 0,
        "format_changed": 0,
        "duplicate_added": 0,
        "status_changed": 0,
    }

    # 获取列索引
    headers = [cell.value for cell in ws[1]]

    # 找出数值列、日期列、状态列
    numeric_cols = []
    date_cols = []
    status_cols = []

    for idx, header in enumerate(headers, start=1):
        if header and any(keyword in str(header).lower() for keyword in ['金额', '数量', '价格', '销售', '成本', '收入']):
            numeric_cols.append(idx)
        if header and any(keyword in str(header).lower() for keyword in ['日期', '时间', 'date', 'time']):
            date_cols.append(idx)
        if header and any(keyword in str(header).lower() for keyword in ['状态', 'status', '是否', '审核']):
            status_cols.append(idx)

    rows = list(ws.iter_rows(min_row=2, max_row=ws.max_row))

    # 1. 注入空值（10-15%）
    target_nulls = int(stats["total_rows"] * random.uniform(0.10, 0.15))
    for _ in range(target_nulls):
        if not rows:
            break
        row = random.choice(rows)
        # 选择非关键列注入空值（避免破坏主键、外键）
        non_key_cols = [col for col in numeric_cols if col > 2]  # 假设前2列是关键列
        if non_key_cols:
            col = random.choice(non_key_cols)
            if row[col - 1].value is not None:
                row[col - 1].value = None
                stats["null_injected"] += 1

    # 2. 注入格式不一致（日期/数字格式，5-10%）
    if date_cols:
        target_format = int(stats["total_rows"] * random.uniform(0.05, 0.10))
        for _ in range(target_format):
            if not rows:
                break
            row = random.choice(rows)
            col = random.choice(date_cols)
            cell = row[col - 1]
            if cell.value and isinstance(cell.value, datetime):
                # 随机改为文本格式或不同日期格式
                formats = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"]
                cell.value = cell.value.strftime(random.choice(formats))
                stats["format_changed"] += 1

    # 3. 注入异常状态（15-20%）
    if status_cols:
        target_status = int(stats["total_rows"] * random.uniform(0.15, 0.20))
        for _ in range(target_status):
            if not rows:
                break
            row = random.choice(rows)
            col = random.choice(status_cols)
            cell = row[col - 1]
            # 改为异常状态
            abnormal_statuses = ["已取消", "退款中", "异常", "待审核", "驳回"]
            if cell.value and str(cell.value) not in abnormal_statuses:
                cell.value = random.choice(abnormal_statuses)
                stats["status_changed"] += 1

    # 4. 注入重复记录（2-5%）
    target_duplicates = int(stats["total_rows"] * random.uniform(0.02, 0.05))
    for _ in range(target_duplicates):
        if not rows:
            break
        original_row = random.choice(rows)
        # 复制整行，但改变第一列（避免主键冲突）
        new_row = []
        for idx, cell in enumerate(original_row):
            if idx == 0:  # 第一列，改变ID
                new_val = f"{cell.value}_DUP{random.randint(1000, 9999)}" if cell.value else f"DUP{random.randint(1000, 9999)}"
                new_row.append(new_val)
            else:
                new_row.append(cell.value)
        ws.append(new_row)
        stats["duplicate_added"] += 1

    wb.save(input_path)
    wb.close()

    return stats


def inject_batch(data_dir: Path) -> None:
    """批量处理目录下的所有01-09测试文件"""
    files = sorted(data_dir.glob("0*.xlsx"))

    if not files:
        print(f"[WARN] No 0*.xlsx files found in {data_dir}")
        return

    print(f"Found {len(files)} files to process")
    print("=" * 60)

    total_stats = {
        "null_injected": 0,
        "format_changed": 0,
        "duplicate_added": 0,
        "status_changed": 0,
    }

    for file_path in files:
        print(f"\n[Processing] {file_path.name}")
        stats = inject_dirty_to_file(file_path, backup=True)

        print(f"  Total rows: {stats['total_rows']}")
        print(f"  Null injected: {stats['null_injected']} ({stats['null_injected']/stats['total_rows']*100:.1f}%)")
        print(f"  Format changed: {stats['format_changed']} ({stats['format_changed']/stats['total_rows']*100:.1f}%)")
        print(f"  Status changed: {stats['status_changed']} ({stats['status_changed']/stats['total_rows']*100:.1f}%)")
        print(f"  Duplicate added: {stats['duplicate_added']} ({stats['duplicate_added']/stats['total_rows']*100:.1f}%)")

        for key in total_stats:
            total_stats[key] += stats[key]

    print("\n" + "=" * 60)
    print("[Summary]")
    for key, value in total_stats.items():
        print(f"  {key}: {value}")

    print("\n[OK] Dirty data injection completed!")
    print("Backup files saved as *.xlsx.backup")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--batch":
            data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "tests/agent_contract/data"
            inject_batch(data_dir)
        else:
            input_file = Path(sys.argv[1])
            stats = inject_dirty_to_file(input_file)
            print(f"[OK] Dirty data injected to {input_file}")
            for key, value in stats.items():
                print(f"  {key}: {value}")
    else:
        print("Usage:")
        print("  python scripts/inject_dirty_data.py --batch [data_dir]")
        print("  python scripts/inject_dirty_data.py <file.xlsx>")
