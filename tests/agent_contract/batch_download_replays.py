#!/usr/bin/env python3
"""
批量下载Agent replay文件

用法:
    python batch_download_replays.py replay_links.txt -o replays/

    或者直接传递链接:
    python batch_download_replays.py https://... https://... -o replays/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)


def extract_scenario_id(replay_data: dict, url: str) -> str:
    """从replay数据或URL中提取scenario_id（已消毒，防止路径遍历）"""
    raw_id = None

    # 方法1: 从replay中的scenario字段
    if "scenario" in replay_data:
        scenario = replay_data["scenario"]
        if isinstance(scenario, dict) and "id" in scenario:
            raw_id = scenario["id"]

    # 方法2: 从URL路径中提取
    if not raw_id:
        path_parts = urlparse(url).path.split("/")
        for part in path_parts:
            # 匹配 S1, M3, H2, R1 等格式
            if re.match(r'^[SMHR]\d+$', part):
                raw_id = part
                break

    # 方法3: 从messages中的用户输入推断
    if not raw_id:
        messages = replay_data.get("messages", [])
        for msg in messages:
            content = str(msg.get("content", ""))
            # 查找场景ID提及
            match = re.search(r'\b([SMHR]\d+)\b', content)
            if match:
                raw_id = match.group(1)
                break

    # 安全验证：只允许标准场景ID格式
    if raw_id and re.match(r'^[SMHR]\d+$', raw_id):
        return raw_id

    # 如果提取失败或不符合格式，返回安全的默认值
    return "unknown"


def download_replay(url: str, output_dir: Path, timeout: int = 30) -> dict:
    """下载单个replay（带大小限制，防止资源耗尽）"""
    result = {"url": url, "success": False}

    # 最大响应大小：100MB
    MAX_RESPONSE_SIZE = 100 * 1024 * 1024

    try:
        print(f"Downloading: {url}")
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # 检查Content-Length头
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_RESPONSE_SIZE:
            result["error"] = f"Response too large: {content_length} bytes (max {MAX_RESPONSE_SIZE})"
            print(f"  ✗ Error: Response exceeds size limit")
            return result

        # 分块读取并检查大小
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_RESPONSE_SIZE:
                result["error"] = f"Response exceeded {MAX_RESPONSE_SIZE} bytes"
                print(f"  ✗ Error: Response too large")
                return result

        # 解析JSON
        try:
            replay_data = json.loads(content.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            result["error"] = f"Invalid JSON or encoding: {e}"
            print(f"  ✗ Error: Invalid response format")
            return result

        # 提取scenario_id（已消毒）
        scenario_id = extract_scenario_id(replay_data, url)

        # 创建场景目录
        scenario_dir = output_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # 保存replay.json
        replay_file = scenario_dir / "replay.json"
        replay_file.write_text(
            json.dumps(replay_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        result.update({
            "success": True,
            "scenario_id": scenario_id,
            "output_path": str(replay_file),
            "size_bytes": len(content),
        })

        print(f"  ✓ Saved to {replay_file}")

    except requests.RequestException as e:
        result["error"] = f"Download failed: {e}"
        print(f"  ✗ Error: {e}")
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        print(f"  ✗ Error: {e}")

    return result


def load_links_from_file(file_path: Path) -> list[str]:
    """从文件加载链接列表"""
    content = file_path.read_text(encoding="utf-8")
    # 每行一个链接，忽略空行和注释
    links = []
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and line.startswith("http"):
            links.append(line)
    return links


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量下载Agent replay文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从文件读取链接
  python batch_download_replays.py replay_links.txt -o replays/

  # 直接传递链接
  python batch_download_replays.py https://... https://... -o replays/

  # 设置超时时间
  python batch_download_replays.py links.txt -o replays/ --timeout 60
"""
    )

    parser.add_argument(
        "inputs",
        nargs="+",
        help="replay链接URL或包含链接的文件路径"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        required=True,
        help="输出目录"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="下载超时时间（秒），默认30"
    )

    args = parser.parse_args()

    # 解析输入
    links = []
    for input_str in args.inputs:
        if input_str.startswith("http"):
            # 直接的URL
            links.append(input_str)
        else:
            # 文件路径
            file_path = Path(input_str)
            if file_path.is_file():
                links.extend(load_links_from_file(file_path))
            else:
                print(f"Warning: {input_str} is not a valid file or URL, skipping")

    if not links:
        print("Error: No valid links found")
        return 1

    print(f"Found {len(links)} replay links to download\n")

    # 创建输出目录
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 下载所有replay
    results = []
    for i, link in enumerate(links, 1):
        print(f"[{i}/{len(links)}]")
        result = download_replay(link, args.output_dir, args.timeout)
        results.append(result)
        print()

    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count

    # 保存下载报告
    report = {
        "total": len(results),
        "success": success_count,
        "failed": failed_count,
        "details": results,
    }

    report_file = args.output_dir / "download_report.json"
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 打印汇总
    print("=" * 60)
    print(f"Download Summary:")
    print(f"  Total:   {len(results)}")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {failed_count}")
    print(f"\nReport saved to: {report_file}")
    print("=" * 60)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
