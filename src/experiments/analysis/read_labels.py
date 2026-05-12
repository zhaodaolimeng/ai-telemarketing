#!/usr/bin/env python3
"""
读取标签文件并显示
"""
import pandas as pd
from pathlib import Path
import json


def main():
    print("="*60)
    print("读取标签文件")
    print("="*60)

    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    if not label_file.exists():
        print(f"文件不存在: {label_file}")
        return

    print(f"\n读取: {label_file}")
    df = pd.read_excel(label_file)

    print(f"\n总行数: {len(df)}")
    print(f"列名: {list(df.columns)}")

    # 显示前10行
    print("\n前10行数据:")
    print(df.head(10).to_string())

    # 统计各列分布
    print("\n各列统计:")
    for col in df.columns:
        if df[col].dtype == "object":
            print(f"\n{col}:")
            counts = df[col].value_counts()
            print(counts.head(10).to_string())
        else:
            print(f"\n{col}: 数值型")
            print(df[col].describe())

    # 保存为csv方便查看
    csv_file = Path("data/raw/leads/label-chat-sample.csv")
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    print(f"\n已保存为CSV: {csv_file}")

    # 检查已转写的文件匹配
    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    # 尝试匹配文件名
    if len(df) > 0 and len(transcript_files) > 0:
        # 找文件名相关列
        file_cols = [c for c in df.columns if "file" in str(c).lower() or "nama" in str(c).lower()]
        if file_cols:
            file_col = file_cols[0]
            print(f"\n使用列: {file_col}")
            label_files = set(df[file_col].dropna().astype(str))
            transcribed_stems = set([f.stem for f in transcript_files])

            matched = label_files & transcribed_stems
            print(f"匹配的文件数: {len(matched)}")
            print(f"示例匹配: {list(matched)[:3]}")

    print("\n" + "="*60)
    print("完成！")
    print("="*60)


if __name__ == "__main__":
    main()
