#!/usr/bin/env python3
"""
结合标签和转写内容做快速分析
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter


def main():
    print("="*60)
    print("快速数据分析")
    print("="*60)

    # 读取标签
    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    print(f"\n标签数据: {len(df)} 条")

    # 1. repay_type 分布
    print("\n1. 还款类型分布:")
    print(df["repay_type"].value_counts(dropna=False).to_string())

    # 2. 通话时长统计
    print("\n2. 通话时长统计:")
    print(df["talk_duration"].describe())

    # 3. 座席分布
    print("\n3. 座席分布 (前10):")
    print(df["seats_name"].value_counts().head(10).to_string())

    # 读取已转写的文件
    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    # 4. 匹配标签和转写
    matched = 0
    labeled_transcripts = []
    for f in transcript_files:
        match_key = f.stem
        label_row = df[df["match_key"] == match_key]
        if len(label_row) > 0:
            matched += 1
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            row = label_row.iloc[0]
            labeled_transcripts.append({
                "match_key": match_key,
                "repay_type": row["repay_type"],
                "talk_duration": row["talk_duration"],
                "transcript": data["full_text"],
                "segments": len(data["transcript"])
            })

    print(f"成功匹配: {matched} 条")

    # 5. 按repay_type分组分析
    if labeled_transcripts:
        print("\n4. 按还款类型分析:")
        df_labeled = pd.DataFrame(labeled_transcripts)

        print("\n样本数分布:")
        print(df_labeled["repay_type"].value_counts(dropna=False).to_string())

        print("\n平均段数:")
        if "segments" in df_labeled.columns and "repay_type" in df_labeled.columns:
            print(df_labeled.groupby("repay_type")["segments"].mean().to_string())

        # 统计关键词
        print("\n5. 关键词统计 (前15):")
        all_text = " ".join([t["transcript"].lower() for t in labeled_transcripts])
        words = all_text.split()
        word_counts = Counter(words)

        # 过滤掉太短的词
        filtered = [(w, c) for w, c in word_counts.items() if len(w) > 2]
        filtered.sort(key=lambda x: -x[1])
        for w, c in filtered[:15]:
            print(f"  {w}: {c}")

        # 简单的印尼语关键词
        keywords = ["bayar", "nanti", "tidak", "uang", "hari", "minggu", "tanggal", "saya", "ibu", "bapak", "tolong", "ya", "tidak bisa"]
        print("\n6. 特定关键词统计:")
        for kw in keywords:
            cnt = sum(1 for t in labeled_transcripts if kw in t["transcript"].lower())
            print(f"  {kw}: {cnt}/{len(labeled_transcripts)}")

    # 总结
    print("\n" + "="*60)
    print("快速分析总结:")
    print("="*60)
    print(f"- 总标签数: {len(df)}")
    print(f"- 已转写: {len(transcript_files)}")
    print(f"- 成功匹配: {matched}")
    print(f"- 主要还款类型: {df['repay_type'].value_counts().idxmax()}")
    print(f"- 平均通话时长: {df['talk_duration'].mean():.1f}秒")

    # 保存分析结果
    analysis_file = Path("data/processed/quick_analysis_summary.json")
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_labels": len(df),
            "total_transcripts": len(transcript_files),
            "matched": matched,
            "repay_type_dist": df["repay_type"].value_counts(dropna=False).to_dict(),
            "talk_duration_stats": df["talk_duration"].describe().to_dict(),
            "top_seats": df["seats_name"].value_counts().head(10).to_dict(),
            "labeled_transcripts": labeled_transcripts[:20] if labeled_transcripts else []
        }, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果已保存: {analysis_file}")
    print("="*60)


if __name__ == "__main__":
    main()
