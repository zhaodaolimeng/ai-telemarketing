#!/usr/bin/env python3
"""
深度分析：正例负例对比，总结对话流程、话术、状态
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter, defaultdict


def main():
    print("="*80)
    print("深度分析：对话流程、话术、状态总结")
    print("="*80)

    # 读取标签
    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if x in ["repay", "extend"] else "failed"
    )

    # 读取已转写文件
    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    # 匹配
    success_samples = []
    failed_samples = []

    for f in transcript_files:
        match_key = f.stem
        label_row = df[df["match_key"] == match_key]
        if len(label_row) > 0:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            row = label_row.iloc[0]
            sample = {
                "match_key": match_key,
                "result": row["result"],
                "transcript": data["transcript"],
                "full_text": data["full_text"]
            }
            if row["result"] == "success":
                success_samples.append(sample)
            else:
                failed_samples.append(sample)

    print(f"成功样本: {len(success_samples)}")
    print(f"失败样本: {len(failed_samples)}")

    if not success_samples or not failed_samples:
        print("\n样本不足，等更多转写完成后再运行！")
        return

    print("\n" + "="*80)
    print("1. 对话流程分析")
    print("="*80)

    # 分析对话长度
    print(f"\n成功样本平均轮数: {sum(len(s['transcript']) for s in success_samples)/len(success_samples):.1f}")
    print(f"失败样本平均轮数: {sum(len(s['transcript']) for s in failed_samples)/len(failed_samples):.1f}")

    # 提取常见开场白
    def get_openings(samples):
        openings = []
        for s in samples:
            if s["transcript"]:
                first_text = s["transcript"][0]["text"].strip()
                openings.append(first_text[:50])
        return Counter(openings)

    print("\n成功样本常见开场白:")
    for text, cnt in get_openings(success_samples).most_common(5):
        print(f"  [{cnt}] {text}")

    print("\n失败样本常见开场白:")
    for text, cnt in get_openings(failed_samples).most_common(5):
        print(f"  [{cnt}] {text}")

    print("\n" + "="*80)
    print("2. 话术分析 - 关键词对比")
    print("="*80)

    def extract_phrases(samples):
        all_words = []
        for s in samples:
            text = s["full_text"].lower()
            words = [w.strip(",.?!") for w in text.split() if len(w) > 2]
            all_words.extend(words)
        return Counter(all_words)

    kw_success = extract_phrases(success_samples)
    kw_failed = extract_phrases(failed_samples)

    print("\n[成功类高频词]:")
    for w, c in kw_success.most_common(20):
        print(f"  {w}: {c}")

    print("\n[失败类高频词]:")
    for w, c in kw_failed.most_common(20):
        print(f"  {w}: {c}")

    # 找差异词
    print("\n[差异显著的词]:")
    all_words = set(kw_success.keys()).union(set(kw_failed.keys()))
    diff_words = []
    for w in all_words:
        s_cnt = kw_success.get(w, 0)
        f_cnt = kw_failed.get(w, 0)
        total = s_cnt + f_cnt
        if total > 5:
            s_ratio = s_cnt / len(success_samples)
            f_ratio = f_cnt / len(failed_samples)
            diff = s_ratio - f_ratio
            if abs(diff) > 0.3:
                diff_words.append((w, diff, s_cnt, f_cnt))

    diff_words.sort(key=lambda x: -abs(x[1]))
    for w, diff, sc, fc in diff_words[:15]:
        tag = "✅成功类" if diff > 0 else "❌失败类"
        print(f"  {tag} {w}: (成功:{sc}, 失败:{fc})")

    print("\n" + "="*80)
    print("3. 对话状态模式总结")
    print("="*80)

    # 成功对话常见模式
    print("\n📌 成功对话典型模式:")
    success_patterns = analyze_patterns(success_samples)
    for i, pattern in enumerate(success_patterns[:5], 1):
        print(f"\n模式{i}: {pattern}")

    # 失败对话常见模式
    print("\n❌ 失败对话典型模式:")
    failed_patterns = analyze_patterns(failed_samples)
    for i, pattern in enumerate(failed_patterns[:5], 1):
        print(f"\n模式{i}: {pattern}")

    # 样本展示
    print("\n" + "="*80)
    print("4. 详细样本展示")
    print("="*80)

    if success_samples:
        print("\n✅ 成功样本示例:")
        print_sample(success_samples[0])

    if failed_samples:
        print("\n❌ 失败样本示例:")
        print_sample(failed_samples[0])

    # 保存结果
    output_file = Path("data/processed/deep_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "success_count": len(success_samples),
            "failed_count": len(failed_samples),
            "success_keywords": dict(kw_success.most_common(30)),
            "failed_keywords": dict(kw_failed.most_common(30)),
            "diff_words": diff_words[:20],
            "success_samples": [s["full_text"][:500] for s in success_samples[:3]],
            "failed_samples": [s["full_text"][:500] for s in failed_samples[:3]]
        }, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果已保存: {output_file}")
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)


def analyze_patterns(samples):
    """简单的模式分析"""
    patterns = []

    for s in samples:
        text = s["full_text"].lower()
        pattern = []
        if "sudah" in text and "dibayar" in text:
            pattern.append("确认已还款")
        if "jam" in text:
            pattern.append("约定时间")
        if "ya" in text and "oke" in text:
            pattern.append("确认用语")
        if "ngga" in text or "tidak" in text:
            pattern.append("否定表达")
        if "selamat" in text:
            pattern.append("礼貌问候")

        if pattern:
            patterns.append(" + ".join(pattern))

    return Counter(patterns).most_common(10)


def print_sample(sample):
    """打印样本"""
    print(f"  ID: {sample['match_key']}")
    print(f"  结果: {sample['result']}")
    text = sample["full_text"][:400] if len(sample["full_text"]) > 400 else sample["full_text"]
    print(f"\n  {text}...\n")


if __name__ == "__main__":
    main()
