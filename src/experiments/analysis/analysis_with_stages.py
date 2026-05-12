#!/usr/bin/env python3
"""
按催收环节分组的深度分析（含语音信箱过滤）
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter, defaultdict


def is_voicemail(text):
    """检测是否为语音信箱自动回复"""
    text = text.lower()
    vm_keywords = [
        "tinggalkan pesan", "bunyi bip", "voice mail", "voicemail",
        "tidak dapat dihubungi", "selamat tinggalkan", "pesan suara",
        "setelah bunyi", "silakan tinggalkan"
    ]
    for kw in vm_keywords:
        if kw in text:
            return True
    # 如果对话非常短（只有1-2轮）且包含典型自动回复特征
    return False


def extract_stage(seats_name):
    """从seats_name提取催收环节"""
    if pd.isna(seats_name):
        return "unknown"
    seats_str = str(seats_name)
    if "H2" in seats_str:
        return "H2"
    elif "H1" in seats_str:
        return "H1"
    elif "S0" in seats_str:
        return "S0"
    else:
        return "other"


def main():
    print("="*80)
    print("按催收环节分组分析（含语音信箱过滤）")
    print("="*80)

    # 读取标签
    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )
    df["stage"] = df["seats_name"].apply(extract_stage)

    print(f"\n总样本数: {len(df)}")
    print("\n各环节分布:")
    print(df["stage"].value_counts().to_string())

    # 读取已转写
    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写: {len(transcript_files)}")

    # 匹配并过滤
    matched = []
    voicemail_count = 0

    for f in transcript_files:
        match_key = f.stem
        label_row = df[df["match_key"] == match_key]
        if len(label_row) > 0:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            row = label_row.iloc[0]

            # 检查是否为语音信箱
            if is_voicemail(data["full_text"]):
                voicemail_count += 1
                continue

            matched.append({
                "match_key": match_key,
                "result": row["result"],
                "stage": row["stage"],
                "seats_name": row["seats_name"],
                "full_text": data["full_text"],
                "transcript": data["transcript"]
            })

    print(f"成功匹配: {len(matched)}")
    print(f"过滤语音信箱: {voicemail_count}")

    # 按环节分组
    stages = defaultdict(list)
    for m in matched:
        stages[m["stage"]].append(m)

    print("\n" + "="*80)
    print("1. 各环节样本统计")
    print("="*80)

    for stage in ["H2", "H1", "S0", "other", "unknown"]:
        samples = stages.get(stage, [])
        if samples:
            success = [s for s in samples if s["result"] == "success"]
            failed = [s for s in samples if s["result"] == "failed"]
            print(f"\n【{stage}环节】")
            print(f"  总样本: {len(samples)}")
            print(f"  成功: {len(success)}, 失败: {len(failed)}")
            if len(samples) > 0:
                print(f"  成功率: {len(success)/len(samples)*100:.1f}%")

    # 各环节分别分析
    for stage in ["H2", "H1", "S0"]:
        samples = stages.get(stage, [])
        if not samples:
            continue

        success = [s for s in samples if s["result"] == "success"]
        failed = [s for s in samples if s["result"] == "failed"]

        if not success or not failed:
            continue

        print("\n" + "="*80)
        print(f"2. {stage}环节深度对比分析")
        print("="*80)

        # 关键词分析
        def get_keywords(samples):
            all_text = " ".join([s["full_text"].lower() for s in samples])
            words = [w.strip(",.?!") for w in all_text.split() if len(w) > 2]
            return Counter(words)

        kw_success = get_keywords(success)
        kw_failed = get_keywords(failed)

        print(f"\n[{stage}] 成功高频词:")
        for w, c in kw_success.most_common(15):
            print(f"  {w}: {c}")

        print(f"\n[{stage}] 失败高频词:")
        for w, c in kw_failed.most_common(15):
            print(f"  {w}: {c}")

        # 差异词
        print(f"\n[{stage}] 差异显著的词:")
        all_words = set(kw_success.keys()).union(set(kw_failed.keys()))
        diff_words = []
        for w in all_words:
            sc = kw_success.get(w, 0)
            fc = kw_failed.get(w, 0)
            total = sc + fc
            if total > 3:
                s_ratio = sc / len(success)
                f_ratio = fc / len(failed)
                diff = s_ratio - f_ratio
                if abs(diff) > 0.2:
                    diff_words.append((w, diff, sc, fc))

        diff_words.sort(key=lambda x: -abs(x[1]))
        for w, diff, sc, fc in diff_words[:10]:
            tag = "SUCCESS" if diff > 0 else "FAILED"
            print(f"  {tag} {w}: (成功:{sc}, 失败:{fc})")

        # 样本展示
        if success:
            print(f"\n[{stage}] 成功样本示例:")
            print(f"  {success[0]['full_text'][:300]}...")
        if failed:
            print(f"\n[{stage}] 失败样本示例:")
            print(f"  {failed[0]['full_text'][:300]}...")

    # 保存结果
    output_file = Path("data/processed/stage_analysis.json")
    result_data = {
        "stage_distribution": {
            stage: {
                "total": len(stages.get(stage, [])),
                "success": len([s for s in stages.get(stage, []) if s["result"] == "success"]),
                "failed": len([s for s in stages.get(stage, []) if s["result"] == "failed"])
            }
            for stage in ["H2", "H1", "S0", "other", "unknown"]
        },
        "filtered_voicemail": voicemail_count,
        "samples_by_stage": {
            stage: [
                {k: v for k, v in s.items() if k != "transcript"}
                for s in stages.get(stage, [])
            ]
            for stage in ["H2", "H1", "S0"]
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果已保存: {output_file}")
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()
