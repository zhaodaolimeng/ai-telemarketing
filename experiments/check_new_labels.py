#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查更新后的标签文件，查看talk group字段
"""
import pandas as pd
from pathlib import Path

label_file = Path("data/label-chat-sample.xlsx")
df = pd.read_excel(label_file)

print("="*80)
print("列名")
print("="*80)
print(df.columns.tolist())

print("\n" + "="*80)
print("前30行数据")
print("="*80)
print(df.head(30).to_string())

print("\n" + "="*80)
print("检查是否有talk group或类似字段")
print("="*80)
for col in df.columns:
    if "talk" in col.lower() or "group" in col.lower() or "tg" in col.lower():
        print(f"\n找到字段: {col}")
        print(f"唯一值: {df[col].value_counts().to_string()}")

print("\n" + "="*80)
print("所有字段的前5个唯一值")
print("="*80)
for col in df.columns:
    unique_vals = df[col].dropna().unique()[:5]
    print(f"\n{col}: {unique_vals}")

print("\n" + "="*80)
print("检查包含H1/H2/S0/M0/M1/M2的值")
print("="*80)
patterns = ["H1", "H2", "S0", "M0", "M1", "M2", "h1", "h2", "s0", "m0", "m1", "m2"]
for col in df.columns:
    for p in patterns:
        matches = df[df[col].astype(str).str.contains(p, na=False)]
        if len(matches) > 0:
            print(f"\n字段 '{col}' 包含 '{p}': {len(matches)} 条")
            print(matches[["match_key", col, "repay_type"]].head(10).to_string())
