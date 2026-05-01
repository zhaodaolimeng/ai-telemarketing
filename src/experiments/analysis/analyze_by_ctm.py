#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按CTM座席号分组分析话术差异
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter, defaultdict
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def is_voicemail(text):
    text = text.lower()
    vm_keywords = [
        "tinggalkan pesan", "bunyi bip", "voice mail", "voicemail",
        "tidak dapat dihubungi", "selamat tinggalkan", "pesan suara",
        "setelah bunyi", "silakan tinggalkan"
    ]
    for kw in vm_keywords:
        if kw in text:
            return True
    return False


def separate_utterances(transcript):
    agent_utterances = []
    customer_utterances = []
    for i, turn in enumerate(transcript):
        speaker = "agent" if i % 2 == 0 else "customer"
        text = turn.get("text", "").strip()
        if text:
            if speaker == "agent":
                agent_utterances.append(text)
            else:
                customer_utterances.append(text)
    return agent_utterances, customer_utterances


def main():
    print("="*80)
    print("按CTM座席号分组分析话术差异")
    print("="*80)

    label_file = Path("data/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))

    # 按CTM分组
    ctm_data = defaultdict(list)
    ctm_stats = defaultdict(lambda: {"success": 0, "failed": 0, "total_utterances": 0})

    for f in transcript_files:
        match_key = f.stem
        label_row = df[df["match_key"] == match_key]
        if len(label_row) == 0:
            continue

        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)

        if is_voicemail(data["full_text"]):
            continue

        row = label_row.iloc[0]
        seats_name = row["seats_name"]
        result = row["result"]

        agent_utts, customer_utts = separate_utterances(data["transcript"])

        ctm_data[seats_name].append({
            "result": result,
            "agent_utterances": agent_utts,
            "full_text": data["full_text"]
        })

        ctm_stats[seats_name][result] += 1
        ctm_stats[seats_name]["total_utterances"] += len(agent_utts)

    # 统计CTM分布
    print("\n" + "="*80)
    print("CTM座席分布和成功率")
    print("="*80)
    print(f"\n{'CTM':<10} {'成功':<6} {'失败':<6} {'总计':<6} {'成功率':<8} {'话术数':<8}")
    print("-"*60)

    ctm_list = sorted(ctm_stats.keys(), key=lambda x: ctm_stats[x]["success"] + ctm_stats[x]["failed"], reverse=True)

    for ctm in ctm_list:
        s = ctm_stats[ctm]["success"]
        f = ctm_stats[ctm]["failed"]
        total = s + f
        rate = (s/total*100) if total > 0 else 0
        utts = ctm_stats[ctm]["total_utterances"]
        print(f"{ctm:<10} {s:<6} {f:<6} {total:<6} {rate:.1f}%{'':<2} {utts:<8}")

    # 按CTM分析话术
    print("\n" + "="*80)
    print("各CTM的高频话术")
    print("="*80)

    for ctm in ctm_list:
        if len(ctm_data[ctm]) < 5:
            continue

        s = ctm_stats[ctm]["success"]
        f = ctm_stats[ctm]["failed"]
        total = s + f
        rate = (s/total*100) if total > 0 else 0

        all_utts = []
        for d in ctm_data[ctm]:
            all_utts.extend(d["agent_utterances"])

        counter = Counter(all_utts)

        print(f"\n--- {ctm} (共{total}条, 成功率{rate:.1f}%) ---")
        for utt, cnt in counter.most_common(10):
            print(f"  [{cnt}] {utt}")

    # 高成功率 vs 低成功率CTM对比
    print("\n" + "="*80)
    print("高成功率CTM vs 低成功率CTM 话术对比")
    print("="*80)

    high_success_ctms = []  # 成功率>70%
    low_success_ctms = []   # 成功率<50%

    for ctm in ctm_list:
        s = ctm_stats[ctm]["success"]
        f = ctm_stats[ctm]["failed"]
        total = s + f
        if total < 10:
            continue
        rate = s/total
        if rate >= 0.7:
            high_success_ctms.append(ctm)
        elif rate < 0.5:
            low_success_ctms.append(ctm)

    print(f"\n高成功率CTM (>{len(high_success_ctms)}个): {high_success_ctms}")
    print(f"低成功率CTM (<50%{len(low_success_ctms)}个): {low_success_ctms}")

    # 收集话术
    high_utts = []
    low_utts = []

    for ctm in high_success_ctms:
        for d in ctm_data[ctm]:
            high_utts.extend(d["agent_utterances"])

    for ctm in low_success_ctms:
        for d in ctm_data[ctm]:
            low_utts.extend(d["agent_utterances"])

    high_counter = Counter(high_utts)
    low_counter = Counter(low_utts)

    print(f"\n高成功率CTM高频话术:")
    for utt, cnt in high_counter.most_common(20):
        print(f"  [{cnt}] {utt}")

    print(f"\n低成功率CTM高频话术:")
    for utt, cnt in low_counter.most_common(20):
        print(f"  [{cnt}] {utt}")

    # 差异分析
    print(f"\n差异话术分析:")
    all_phrases = set(high_counter.keys()).union(set(low_counter.keys()))
    diff_list = []

    high_total = sum(high_counter.values())
    low_total = sum(low_counter.values())

    for phrase in all_phrases:
        hc = high_counter.get(phrase, 0)
        lc = low_counter.get(phrase, 0)
        if hc + lc > 5:
            h_ratio = hc / high_total if high_total else 0
            l_ratio = lc / low_total if low_total else 0
            diff = h_ratio - l_ratio
            diff_list.append((phrase, diff, hc, lc))

    diff_list.sort(key=lambda x: -abs(x[1]))

    print(f"\n高成功率CTM偏好话术:")
    for phrase, diff, hc, lc in diff_list[:20]:
        if diff > 0:
            print(f"  [+] '{phrase}' (高:{hc}, 低:{lc}, diff:{diff:.3f})")

    print(f"\n低成功率CTM偏好话术:")
    for phrase, diff, hc, lc in diff_list[:30]:
        if diff < 0:
            print(f"  [-] '{phrase}' (高:{hc}, 低:{lc}, diff:{diff:.3f})")

    # 保存结果
    output = {
        "ctm_stats": {
            ctm: {
                "success": ctm_stats[ctm]["success"],
                "failed": ctm_stats[ctm]["failed"],
                "total": ctm_stats[ctm]["success"] + ctm_stats[ctm]["failed"],
                "success_rate": ctm_stats[ctm]["success"] / (ctm_stats[ctm]["success"] + ctm_stats[ctm]["failed"]) if (ctm_stats[ctm]["success"] + ctm_stats[ctm]["failed"]) > 0 else 0
            }
            for ctm in ctm_stats
        },
        "high_success_ctms": high_success_ctms,
        "low_success_ctms": low_success_ctms
    }

    with open("data/processed/ctm_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果保存到: data/processed/ctm_analysis.json")


if __name__ == "__main__":
    main()
