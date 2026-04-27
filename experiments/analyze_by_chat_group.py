#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按chat_group分组分析：H2/H1/S0
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
    print("按chat_group分组分析：H2/H1/S0")
    print("="*80)

    label_file = Path("data/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))

    # 按chat_group分组
    group_data = defaultdict(list)
    group_stats = defaultdict(lambda: {"success": 0, "failed": 0, "total_utterances": 0})

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
        chat_group = row["chat_group"]
        result = row["result"]

        agent_utts, customer_utts = separate_utterances(data["transcript"])

        group_data[chat_group].append({
            "result": result,
            "agent_utterances": agent_utts,
            "customer_utterances": customer_utts,
            "full_text": data["full_text"],
            "match_key": match_key
        })

        group_stats[chat_group][result] += 1
        group_stats[chat_group]["total_utterances"] += len(agent_utts)

    # 统计各group的分布
    print("\n" + "="*80)
    print("各chat_group分布和成功率")
    print("="*80)
    print(f"\n{'Group':<10} {'成功':<8} {'失败':<8} {'总计':<8} {'成功率':<8} {'话术数':<8}")
    print("-"*70)

    groups = sorted(group_stats.keys())
    for group in groups:
        s = group_stats[group]["success"]
        f = group_stats[group]["failed"]
        total = s + f
        rate = (s/total*100) if total > 0 else 0
        utts = group_stats[group]["total_utterances"]
        print(f"{group:<10} {s:<8} {f:<8} {total:<8} {rate:.1f}%{'':<3} {utts:<8}")

    # 按group分析话术
    print("\n" + "="*80)
    print("各chat_group的高频话术")
    print("="*80)

    for group in groups:
        s = group_stats[group]["success"]
        f = group_stats[group]["failed"]
        total = s + f
        rate = (s/total*100) if total > 0 else 0

        all_utts = []
        for d in group_data[group]:
            all_utts.extend(d["agent_utterances"])

        counter = Counter(all_utts)

        print(f"\n--- {group} (共{total}条, 成功率{rate:.1f}%) ---")
        for utt, cnt in counter.most_common(20):
            print(f"  [{cnt}] {utt}")

    # 分组内的成功vs失败对比
    print("\n" + "="*80)
    print("各chat_group内的成功vs失败对比")
    print("="*80)

    for group in groups:
        print(f"\n--- {group} ---")
        success_utts = []
        failed_utts = []

        for d in group_data[group]:
            if d["result"] == "success":
                success_utts.extend(d["agent_utterances"])
            else:
                failed_utts.extend(d["agent_utterances"])

        success_counter = Counter(success_utts)
        failed_counter = Counter(failed_utts)

        print(f"\n{group}成功对话高频话术:")
        for utt, cnt in success_counter.most_common(15):
            print(f"  [{cnt}] {utt}")

        print(f"\n{group}失败对话高频话术:")
        for utt, cnt in failed_counter.most_common(15):
            print(f"  [{cnt}] {utt}")

        # 差异分析
        print(f"\n{group}差异话术:")
        all_phrases = set(success_counter.keys()).union(set(failed_counter.keys()))
        diff_list = []
        success_total = len(success_utts)
        failed_total = len(failed_utts)

        for phrase in all_phrases:
            sc = success_counter.get(phrase, 0)
            fc = failed_counter.get(phrase, 0)
            if sc + fc > 3:
                s_ratio = sc / success_total if success_total else 0
                f_ratio = fc / failed_total if failed_total else 0
                diff = s_ratio - f_ratio
                diff_list.append((phrase, diff, sc, fc))

        diff_list.sort(key=lambda x: -abs(x[1]))

        print(f"\n{group}成功导向话术:")
        for phrase, diff, sc, fc in diff_list[:10]:
            if diff > 0:
                print(f"  [+] '{phrase}' (成功:{sc}, 失败:{fc}, diff:{diff:.3f})")

        print(f"\n{group}失败导向话术:")
        for phrase, diff, sc, fc in diff_list[:15]:
            if diff < 0:
                print(f"  [-] '{phrase}' (成功:{sc}, 失败:{fc}, diff:{diff:.3f})")

    # 保存结果
    output = {
        "group_stats": {},
        "group_data": {}
    }

    for group in groups:
        s = group_stats[group]["success"]
        f = group_stats[group]["failed"]
        total = s + f
        rate = (s/total) if total > 0 else 0
        output["group_stats"][group] = {
            "success": s,
            "failed": f,
            "total": total,
            "success_rate": rate
        }

        success_utts = []
        failed_utts = []
        for d in group_data[group]:
            if d["result"] == "success":
                success_utts.extend(d["agent_utterances"])
            else:
                failed_utts.extend(d["agent_utterances"])

        output["group_data"][group] = {
            "success_utterances": dict(Counter(success_utts).most_common(50)),
            "failed_utterances": dict(Counter(failed_utts).most_common(50)),
            "all_utterances": dict(Counter(success_utts + failed_utts).most_common(50))
        }

    with open("data/processed/chat_group_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果保存到: data/processed/chat_group_analysis.json")


if __name__ == "__main__":
    main()
