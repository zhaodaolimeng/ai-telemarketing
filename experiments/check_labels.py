#!/usr/bin/env python3
"""
检查标签文件内容
"""
import pandas as pd
from pathlib import Path

label_file = Path("data/label-chat-sample.xlsx")
df = pd.read_excel(label_file)

print("="*80)
print("标签文件列名:")
print(df.columns.tolist())

print("\n" + "="*80)
print("前10行数据:")
print(df.head(10).to_string())

print("\n" + "="*80)
print("seats_name字段唯一值:")
print(df["seats_name"].value_counts().to_string())

print("\n" + "="*80)
print("repay_type字段唯一值:")
print(df["repay_type"].value_counts(dropna=False).to_string())

print("\n" + "="*80)
print("有seats_name值的前20条:")
non_empty = df[df["seats_name"].notna()]
print(non_empty[["match_key", "seats_name", "repay_type"]].head(20).to_string())
