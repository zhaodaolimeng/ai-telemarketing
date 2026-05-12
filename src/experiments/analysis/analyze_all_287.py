#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析所有287个转写的对话
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
    print("分析所有287个对话")
    print("="*80)

    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    all_dialogues = []
    matched_dialogues = []
    unmatched_dialogues = []
    success_dialogues = []
    failed_dialogues = []

    for f in transcript_files:
        match_key = f.stem
        label_row = df[df["match_key"] == match_key]

        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)

        if is_voicemail(data["full_text"]):
            continue

        agent_utts, customer_utts = separate_utterances(data["transcript"])

        dialogue_data = {
            "match_key": match_key,
            "agent_utterances": agent_utts,
            "customer_utterances": customer_utts,
            "full_text": data["full_text"]
        }

        all_dialogues.append(dialogue_data)

        if len(label_row) > 0:
            row = label_row.iloc[0]
            result = row["result"]
            dialogue_data["result"] = result
            dialogue_data["repay_type"] = row["repay_type"] if pd.notna(row["repay_type"]) else None
            matched_dialogues.append(dialogue_data)

            if result == "success":
                success_dialogues.append(dialogue_data)
            else:
                failed_dialogues.append(dialogue_data)
        else:
            unmatched_dialogues.append(dialogue_data)

    print(f"总对话数（排除语音信箱）: {len(all_dialogues)}")
    print(f"  有标签的: {len(matched_dialogues)}")
    print(f"    成功: {len(success_dialogues)}")
    print(f"    失败: {len(failed_dialogues)}")
    print(f"  无标签的: {len(unmatched_dialogues)}")

    # 统计所有话术
    all_agent_utts = []
    for d in all_dialogues:
        all_agent_utts.extend(d["agent_utterances"])

    agent_counter = Counter(all_agent_utts)

    print(f"\n催收员话术总数: {len(all_agent_utts)}")
    print(f"独特话术种类: {len(agent_counter)}")

    print("\n" + "="*80)
    print("催收员高频话术 TOP 50")
    print("="*80)
    for utt, cnt in agent_counter.most_common(50):
        print(f"  [{cnt}] {utt}")

    # 按分类统计
    greeting = []
    identify = []
    time_commit = []
    confirm = []
    closing = []
    app_mention = []

    for utt in all_agent_utts:
        utt_lower = utt.lower()
        if any(g in utt_lower for g in ["halo", "selamat", "hello", "hi"]):
            greeting.append(utt)
        if any(i in utt_lower for i in ["dengan", "bapak", "ibu", "pak", "bu", "nama"]):
            identify.append(utt)
        if any(t in utt_lower for t in ["jam", "pukul", "kapan", "hari", "nanti", "tunggu"]):
            time_commit.append(utt)
        if any(c in utt_lower for c in ["oke", "ya", "iya", "baik", "siap"]):
            confirm.append(utt)
        if any(e in utt_lower for e in ["terima kasih", "makasih", "sampai"]):
            closing.append(utt)
        if any(a in utt_lower for a in ["aplikasi", "ekstra", "uang"]):
            app_mention.append(utt)

    print("\n" + "="*80)
    print("按分类统计")
    print("="*80)
    print(f"\n问候类: {len(greeting)} 个")
    for utt, cnt in Counter(greeting).most_common(20):
        print(f"  [{cnt}] {utt}")
    print(f"\n身份确认类: {len(identify)} 个")
    for utt, cnt in Counter(identify).most_common(20):
        print(f"  [{cnt}] {utt}")
    print(f"\n时间约定类: {len(time_commit)} 个")
    for utt, cnt in Counter(time_commit).most_common(20):
        print(f"  [{cnt}] {utt}")
    print(f"\n确认类: {len(confirm)} 个")
    for utt, cnt in Counter(confirm).most_common(20):
        print(f"  [{cnt}] {utt}")
    print(f"\n结束类: {len(closing)} 个")
    for utt, cnt in Counter(closing).most_common(20):
        print(f"  [{cnt}] {utt}")
    print(f"\n提及应用类: {len(app_mention)} 个")
    for utt, cnt in Counter(app_mention).most_common(20):
        print(f"  [{cnt}] {utt}")

    # 保存结果
    output_data = {
        "all_dialogues": all_dialogues,
        "matched_dialogues": matched_dialogues,
        "success_dialogues": success_dialogues,
        "failed_dialogues": failed_dialogues,
        "unmatched_dialogues": unmatched_dialogues,
        "agent_utterance_library": dict(agent_counter.most_common(200)),
        "by_category": {
            "greeting": dict(Counter(greeting).most_common(100)),
            "identify": dict(Counter(identify).most_common(100)),
            "time_commit": dict(Counter(time_commit).most_common(100)),
            "confirm": dict(Counter(confirm).most_common(100)),
            "closing": dict(Counter(closing).most_common(100)),
            "app_mention": dict(Counter(app_mention).most_common(100))
        },
        "summary": {
            "total_dialogues": len(all_dialogues),
            "matched": len(matched_dialogues),
            "success": len(success_dialogues),
            "failed": len(failed_dialogues),
            "unmatched": len(unmatched_dialogues),
            "total_agent_utterances": len(all_agent_utts),
            "unique_utterances": len(agent_counter)
        }
    }

    output_file = Path("data/processed/all_287_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n完整分析结果已保存: {output_file}")

    # 如果有标签数据，做对比分析
    if matched_dialogues:
        print("\n" + "="*80)
        print("成功 vs 失败 对比分析")
        print("="*80)

        success_agent_utts = []
        failed_agent_utts = []
        for d in success_dialogues:
            success_agent_utts.extend(d["agent_utterances"])
        for d in failed_dialogues:
            failed_agent_utts.extend(d["agent_utterances"])

        success_counter = Counter(success_agent_utts)
        failed_counter = Counter(failed_agent_utts)

        print(f"\n成功对话话术: {len(success_agent_utts)} 个")
        print("成功高频话术:")
        for utt, cnt in success_counter.most_common(30):
            print(f"  [{cnt}] {utt}")

        print(f"\n失败对话话术: {len(failed_agent_utts)} 个")
        print("失败高频话术:")
        for utt, cnt in failed_counter.most_common(30):
            print(f"  [{cnt}] {utt}")

        # 找差异
        print(f"\n差异分析:")
        all_phrases = set(success_counter.keys()).union(set(failed_counter.keys()))
        diff_list = []
        success_docs = len(success_dialogues)
        failed_docs = len(failed_dialogues)

        for phrase in all_phrases:
            sc = success_counter.get(phrase, 0)
            fc = failed_counter.get(phrase, 0)
            if sc + fc > 5:
                s_ratio = sc / success_docs if success_docs else 0
                f_ratio = fc / failed_docs if failed_docs else 0
                diff = s_ratio - f_ratio
                diff_list.append((phrase, diff, sc, fc))

        diff_list.sort(key=lambda x: -abs(x[1]))

        print(f"\n成功导向话术:")
        for phrase, diff, sc, fc in diff_list[:30]:
            if diff > 0:
                print(f"  [+] '{phrase}' (成功:{sc}, 失败:{fc}, diff:{diff:.2f})")

        print(f"\n失败导向话术:")
        for phrase, diff, sc, fc in diff_list[:50]:
            if diff < 0:
                print(f"  [-] '{phrase}' (成功:{sc}, 失败:{fc}, diff:{diff:.2f})")

    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()
