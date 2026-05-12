#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 ClickHouse 数据仓库拉取催收通话记录，导出为 CSV。

Usage:
    python scripts/fetcher/fetch_leads.py                                    # 默认参数
    python scripts/fetcher/fetch_leads.py --start-date 2026-05-01            # 指定起始日期
    python scripts/fetcher/fetch_leads.py --start-date 2026-03-15 --end-date 2026-03-31
    python scripts/fetcher/fetch_leads.py --min-duration 30 --max-duration 90
    python scripts/fetcher/fetch_leads.py --chat-groups H2 S0                # 仅拉取指定催收阶段
    python scripts/fetcher/fetch_leads.py --dry-run                          # 仅打印 SQL，不执行
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

FETCHER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FETCHER_DIR))

from lib.http_client import get_http_proxies

PROJECT_ROOT = FETCHER_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_config() -> dict:
    config_path = FETCHER_DIR / "config.json"
    if not config_path.exists():
        print(f"[ERROR] 配置文件不存在: {config_path}")
        print(f"        请复制 config.example.json → config.json 并填写实际配置")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)


def load_sql_template(name: str = "alpha_leads") -> str:
    sql_path = FETCHER_DIR / "sql" / f"{name}.sql"
    if not sql_path.exists():
        # 兼容旧文件名
        old_path = FETCHER_DIR / "sql" / "催收语音是否有效.sql"
        if old_path.exists():
            sql_path = old_path
        else:
            print(f"[ERROR] SQL 文件不存在: {sql_path}")
            sys.exit(1)
    return sql_path.read_text(encoding="utf-8")


def apply_params(sql: str, args: argparse.Namespace) -> str:
    """注入 CLI 参数到 SQL 模板占位符。"""
    sql = sql.replace(
        "date(call_time) >= '2026-04-01'",
        f"date(call_time) >= '{args.start_date}'",
    )
    if args.end_date:
        sql += f"\nand date(call_time) <= '{args.end_date}'"

    sql = sql.replace(
        f"talk_duration between 20 and 60",
        f"talk_duration between {args.min_duration} and {args.max_duration}",
    )

    if args.chat_groups:
        group_ids = []
        gid_map = {"H2": 92, "H1": 93, "S0": 94}
        for g in args.chat_groups:
            if g in gid_map:
                group_ids.append(str(gid_map[g]))
        if group_ids:
            sql = sql.replace(
                "where rk = 1",
                f"where rk = 1\nand a.group_id in ({','.join(group_ids)})",
            )

    return sql


def fetch_via_http(config: dict, sql: str) -> pd.DataFrame:
    """通过 ClickHouse HTTP 接口执行查询（自适应代理）。"""
    base_url = f"http://{config['host']}:{config['port']}/"
    auth = (config["user"], config["password"])
    test_url = f"{base_url}?query=SELECT+1&database={config['database']}"

    proxies = get_http_proxies(test_url, auth=auth, timeout=5.0)

    params = {
        "database": config["database"],
        "query": sql,
        "default_format": "JSONCompact",
    }

    timeout = (
        config.get("connect_timeout", 30),
        config.get("send_receive_timeout", 60),
    )

    s = requests.Session()
    s.trust_env = (proxies.get("http") is not None)  # 代理模式信任环境, 直连模式不信任
    resp = s.get(base_url, params=params, auth=auth, timeout=timeout,
                 proxies=proxies)
    resp.raise_for_status()

    data = resp.json()
    columns = [c["name"] for c in data["meta"]]
    rows = data["data"]
    return pd.DataFrame(rows, columns=columns)


def main():
    parser = argparse.ArgumentParser(description="从 ClickHouse 拉取催收通话记录")
    parser.add_argument("--start-date", default="2026-05-01",
                        help="通话起始日期 (default: 2026-05-01)")
    parser.add_argument("--end-date", default=None,
                        help="通话结束日期 (default: 无限制)")
    parser.add_argument("--min-duration", type=int, default=20,
                        help="最小时长/秒 (default: 20)")
    parser.add_argument("--max-duration", type=int, default=60,
                        help="最大时长/秒 (default: 60)")
    parser.add_argument("--chat-groups", nargs="*", choices=["H2", "H1", "S0"],
                        help="限定催收阶段 (default: 全部)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅打印 SQL，不执行")
    parser.add_argument("--output", default=None,
                        help="输出 CSV 路径 (default: data/raw/leads/fetched_leads_<timestamp>.csv)")
    args = parser.parse_args()

    config = load_config()

    # 加载 SQL
    sql = load_sql_template("alpha_leads")
    sql = apply_params(sql, args)

    if args.dry_run:
        print("=" * 60)
        print("[DRY RUN] 以下是将执行的 SQL:")
        print("=" * 60)
        print(sql)
        return

    # 执行查询
    print(f"[INFO] 连接 ClickHouse: {config['host']}:{config['port']}/{config['database']} ...")
    print("[INFO] 执行查询...")
    try:
        df = fetch_via_http(config, sql)
    except Exception as e:
        print(f"[ERROR] 查询执行失败: {e}")
        sys.exit(1)

    print(f"[INFO] 获取到 {len(df)} 条记录")

    if df.empty:
        print("[WARN] 查询结果为空，请检查日期范围和筛选条件")
        return

    # 保存
    output = args.output
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = str(DATA_DIR / f"fetched_leads_{timestamp}.csv")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"[INFO] 已保存到: {output}")

    # 简要统计
    if "chat_group" in df.columns:
        print(f"\n  催收阶段分布:\n{df['chat_group'].value_counts().to_string()}")
    if "talk_duration" in df.columns:
        print(f"\n  通话时长: min={df['talk_duration'].min()}s  max={df['talk_duration'].max()}s  avg={df['talk_duration'].mean():.1f}s")


if __name__ == "__main__":
    main()
