#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 CSV 中的 record_url 字段批量下载催收通话音频。

Usage:
    python scripts/fetcher/download_audio.py                                   # 默认读取最新 CSV
    python scripts/fetcher/download_audio.py --csv data/fetched_leads_xxx.csv  # 指定 CSV
    python scripts/fetcher/download_audio.py --start 0 --end 100               # 只下载前100条
    python scripts/fetcher/download_audio.py --rate-limit 3 --retry 5          # 3秒间隔, 最多重试5次
    python scripts/fetcher/download_audio.py --dry-run                         # 仅检查，不下载
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

FETCHER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FETCHER_DIR))

from lib.http_client import get_http_proxies

PROJECT_ROOT = FETCHER_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "voice_recordings"


def check_existing(csv_path: Path) -> Path:
    """如果没有指定 CSV，找最新的 fetched_leads_*.csv。"""
    if csv_path:
        p = Path(csv_path)
        if not p.exists():
            print(f"[ERROR] CSV 文件不存在: {p}")
            sys.exit(1)
        return p

    candidates = sorted(DATA_DIR.glob("fetched_leads_*.csv"), reverse=True)
    if not candidates:
        print("[ERROR] 未找到 fetched_leads_*.csv，请先运行 fetch_leads.py")
        sys.exit(1)
    print(f"[INFO] 自动选择最新 CSV: {candidates[0]}")
    return candidates[0]


def file_healthy(path: Path, min_bytes: int = 1024) -> bool:
    """检查已下载文件是否健康（存在且大于最小字节数）。"""
    return path.exists() and path.stat().st_size >= min_bytes


def download_one(url: str, dest: Path, proxies: dict, timeout: int = 30) -> bool:
    """下载单个文件，成功返回 True。"""
    s = requests.Session()
    s.trust_env = (proxies.get("http") is not None)
    resp = s.get(url, timeout=timeout, proxies=proxies)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return True


def main():
    parser = argparse.ArgumentParser(description="批量下载催收通话音频")
    parser.add_argument("--csv", default=None,
                        help="CSV 文件路径 (default: 自动选择最新的 fetched_leads_*.csv)")
    parser.add_argument("--start", type=int, default=0,
                        help="起始行号 (default: 0)")
    parser.add_argument("--end", type=int, default=None,
                        help="结束行号 (default: 全部)")
    parser.add_argument("--rate-limit", type=float, default=5.0,
                        help="下载间隔/秒 (default: 5)")
    parser.add_argument("--retry", type=int, default=3,
                        help="失败重试次数 (default: 3)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="单文件下载超时/秒 (default: 30)")
    parser.add_argument("--min-bytes", type=int, default=1024,
                        help="已存在文件的最小字节数，低于此值重新下载 (default: 1024)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅检查状态，不实际下载")
    args = parser.parse_args()

    csv_path = check_existing(args.csv)
    df = pd.read_csv(csv_path)

    if "record_url" not in df.columns or "match_key" not in df.columns:
        print("[ERROR] CSV 缺少 record_url 或 match_key 字段")
        sys.exit(1)

    total = len(df)
    end = min(args.end or total, total)
    subset = df.iloc[args.start:end]

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # 自适应代理检测（用第一条记录的 domain 做连通性测试）
    first_url = subset.iloc[0]["record_url"]
    test_host = first_url.split("/")[2] if "//" in first_url else first_url
    test_url = f"http://{test_host}/"
    proxies = get_http_proxies(test_url, timeout=5.0)

    print(f"[INFO] 总计 {total} 条记录，处理范围 [{args.start}:{end}]，共 {len(subset)} 条")
    if args.dry_run:
        print("[DRY RUN] 预览模式，不实际下载\n")

    success = 0
    skipped = 0
    failed = 0

    for idx, row in subset.iterrows():
        match_key = row["match_key"]
        url = row["record_url"]
        dest = AUDIO_DIR / f"{match_key}.mp3"

        if file_healthy(dest, args.min_bytes):
            skipped += 1
            continue

        if args.dry_run:
            print(f"  [{idx}] {match_key} — 待下载 ({dest.stat().st_size if dest.exists() else 0} bytes)")
            continue

        # 重试下载
        ok = False
        for attempt in range(1, args.retry + 1):
            try:
                download_one(url, dest, proxies, args.timeout)
                size_kb = dest.stat().st_size / 1024
                print(f"  [{idx}] {match_key} — OK ({size_kb:.0f} KB)")
                ok = True
                success += 1
                break
            except Exception as e:
                if attempt < args.retry:
                    time.sleep(1)
                else:
                    print(f"  [{idx}] {match_key} — FAILED: {e}")
                    failed += 1

        time.sleep(args.rate_limit)

    print(f"\n[INFO] 完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")
    if failed:
        print("[WARN] 有失败记录，可重新运行脚本重试（已成功的会自动跳过）")


if __name__ == "__main__":
    main()
