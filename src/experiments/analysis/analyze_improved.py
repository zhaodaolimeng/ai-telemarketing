#!/usr/bin/env python3
"""
改进版分析：加入沟通失败类别
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter


def main():
    print("="*70)
    print("改进版深度分析")
    print("="*70)
    print("\n说明：未标注repay_type = 沟通失败（24小时内未还款）")

    # 读取标签
    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    print(f"\n总标签数: {len(df)}")

    # 定义类别
    df["result"] = df["repay_type"].apply(
        lambda x: "success_repay" if x == "repay"
        else ("success_extend" if x == "extend"
        else "failed")
    )

    print("\n1. 完整分类统计:")
    result_dist = df["result"].value_counts()
    print(result_dist.to_string())

    # 读取已转写
    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写: {len(transcript_files)}")

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
                "result": row["result"],
                "talk_duration": row["talk_duration"],
                "seats_name": row["seats_name"],
                "full_text": data["full_text"],
                "segments": len(data["transcript"])
            })

    print(f"成功匹配: {len(matched)}")

    if matched:
        df_matched = pd.DataFrame(matched)

        print("\n2. 匹配样本的结果分布:")
        print(df_matched["result"].value_counts().to_string())

        # 按结果分组
        success_repay = [m for m in matched if m["result"] == "success_repay"]
        success_extend = [m for m in matched if m["result"] == "success_extend"]
        failed = [m for m in matched if m["result"] == "failed"]

        print(f"\n   - 成功还款: {len(success_repay)}")
        print(f"   - 成功延期: {len(success_extend)}")
        print(f"   - 沟通失败: {len(failed)}")

        # 关键词分析
        print("\n3. 关键词对比分析:")

        def extract_keywords(samples):
            if not samples:
                return {}
            all_text = " ".join([s["full_text"].lower() for s in samples])
            words = [w.strip(",.?!") for w in all_text.split() if len(w) > 2]
            return dict(Counter(words).most_common(15))

        kw_repay = extract_keywords(success_repay)
        kw_extend = extract_keywords(success_extend)
        kw_failed = extract_keywords(failed)

        # 显示对比
        print(f"\n   [成功还款] 高频词:")
        for w, c in list(kw_repay.items())[:10]:
            print(f"     {w}: {c}")

        print(f"\n   [沟通失败] 高频词:")
        for w, c in list(kw_failed.items())[:10]:
            print(f"     {w}: {c}")

        # 找出有区分度的词
        print("\n4. 有区分度的关键词对比:")
        all_words = set(kw_repay.keys()).union(set(kw_failed.keys()))
        diff_words = []
        for w in all_words:
            cnt_repay = kw_repay.get(w, 0)
            cnt_failed = kw_failed.get(w, 0)
            total = cnt_repay + cnt_failed
            if total > 3:
                ratio_repay = cnt_repay / len(success_repay) if success_repay else 0
                ratio_failed = cnt_failed / len(failed) if failed else 0
                diff = ratio_repay - ratio_failed
                if abs(diff) > 0.2:
                    diff_words.append((w, diff, cnt_repay, cnt_failed))

        diff_words.sort(key=lambda x: -abs(x[1]))
        for w, diff, rc, fc in diff_words[:10]:
            direction = "还款类" if diff > 0 else "失败类"
            print(f"   {w}: {direction} (还款:{rc}, 失败:{fc})")

        # 样本展示
        print("\n5. 样本展示:")
        if success_repay:
            print(f"\n   [成功还款示例]:")
            text = success_repay[0]["full_text"][:250]
            print(f"   {text}...")

        if failed:
            print(f"\n   [沟通失败示例]:")
            text = failed[0]["full_text"][:250]
            print(f"   {text}...")

        # 保存结果
        analysis_file = Path("data/processed/improved_analysis.json")
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_dist": result_dist.to_dict(),
                "matched_samples": matched,
                "keywords_repay": kw_repay,
                "keywords_extend": kw_extend,
                "keywords_failed": kw_failed
            }, f, ensure_ascii=False, indent=2)

        print(f"\n分析结果已保存: {analysis_file}")

    print("\n" + "="*70)
    print("分析完成！")
    print("="*70)


if __name__ == "__main__":
    main()
