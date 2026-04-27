#!/usr/bin/env python3
"""
分析所有已转写的文件
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter


def main():
    print("="*70)
    print("全面数据分析")
    print("="*70)

    # 读取标签
    label_file = Path("data/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    print(f"\n标签数据: {len(df)} 条")

    # 读取已转写文件
    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"已转写文件: {len(transcript_files)}")

    # 匹配
    matched = []
    for f in transcript_files:
        match_key = f.stem
        label_row = df[df["match_key"] == match_key]
        if len(label_row) > 0:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            row = label_row.iloc[0]
            matched.append({
                "match_key": match_key,
                "repay_type": row["repay_type"],
                "talk_duration": row["talk_duration"],
                "seats_name": row["seats_name"],
                "full_text": data["full_text"],
                "segments": len(data["transcript"]),
                "has_speakers": "transcript_with_speakers" in data
            })

    print(f"成功匹配: {len(matched)} 条")

    if matched:
        print("\n" + "="*70)
        print("详细分析")
        print("="*70)

        df_matched = pd.DataFrame(matched)

        # 按还款类型统计
        print("\n1. 还款类型分布:")
        print(df_matched["repay_type"].value_counts(dropna=False).to_string())

        # 关键词分析
        print("\n2. 按类别分析的关键词:")
        repay_samples = [m for m in matched if m["repay_type"] == "repay"]
        extend_samples = [m for m in matched if m["repay_type"] == "extend"]

        print(f"\n   Repay样本: {len(repay_samples)}")
        print(f"   Extend样本: {len(extend_samples)}")

        # 提取高频词
        def get_top_words(samples, n=20):
            all_text = " ".join([s["full_text"].lower() for s in samples])
            words = [w.strip(",.?!") for w in all_text.split() if len(w) > 2]
            return Counter(words).most_common(n)

        if repay_samples:
            print("\n   Repay高频词:")
            for w, c in get_top_words(repay_samples, 10):
                print(f"     {w}: {c}")

        if extend_samples:
            print("\n   Extend高频词:")
            for w, c in get_top_words(extend_samples, 10):
                print(f"     {w}: {c}")

        # 展示部分样本
        print("\n3. 样本对话展示 (前2个):")
        for i, sample in enumerate(matched[:2]):
            print(f"\n   [{i+1}] {sample['match_key']} | {sample['repay_type']}")
            text = sample["full_text"][:200] if len(sample["full_text"]) > 200 else sample["full_text"]
            print(f"   {text}...")

        # 保存分析结果
        print("\n4. 保存分析结果...")
        analysis_file = Path("data/processed/analysis_results.json")
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_labels": len(df),
                "total_transcripts": len(transcript_files),
                "matched_count": len(matched),
                "repay_type_dist": df_matched["repay_type"].value_counts(dropna=False).to_dict(),
                "matched_samples": matched
            }, f, ensure_ascii=False, indent=2)

        print(f"   已保存到: {analysis_file}")

    print("\n" + "="*70)
    print("分析完成！")
    print("="*70)


if __name__ == "__main__":
    main()
