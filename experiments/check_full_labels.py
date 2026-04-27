#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查完整的标签文件内容
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
print("前20行数据")
print("="*80)
print(df.head(20).to_string())

print("\n" + "="*80)
print("seats_name字段唯一值及计数")
print("="*80)
print(df["seats_name"].value_counts().to_string())

print("\n" + "="*80)
print("检查是否有包含H1/H2/S0的值")
print("="*80)
h_patterns = ["H1", "H2", "S0", "M0", "M1", "M2"]
for p in h_patterns:
    matches = df[df["seats_name"].astype(str).str.contains(p, na=False)]
    print(f"\n包含 '{p}': {len(matches)} 条")
    if len(matches) > 0:
        print(matches[["match_key", "seats_name", "repay_type"]].head(10).to_string())

print("\n" + "="*80)
print("检查cases.csv里的status字段")
print("="*80)
cases = pd.read_csv("data/cases.csv")
print("\nstatus字段唯一值:")
print(cases["status"].value_counts().to_string())
print("\ncases.csv前10行:")
print(cases.head(10).to_string())

# 合并检查
print("\n" + "="*80)
print("合并label和cases检查")
print("="*80)
merged = df.merge(cases, left_on="match_key", right_on="case_id", how="left")
print(f"\n合并后有status的: {merged['status'].notna().sum()} 条")
print("\nstatus分布:")
print(merged["status"].value_counts().to_string())
print("\n按status分组的成功率:")
for s in merged["status"].dropna().unique():
    subset = merged[merged["status"] == s]
    success = subset["repay_type"].notna().sum()
    total = len(subset)
    print(f"  {s}: {success}/{total} ({success/total*100:.1f}%)")
