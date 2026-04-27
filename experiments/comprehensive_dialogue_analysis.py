#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合对话分析 - 整理所有转写对话，构建丰富的话术库
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
    print("综合对话分析 - 构建话术库")
    print("="*80)

    label_file = Path("data/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    all_dialogues = []
    all_agent_utterances = []
    all_customer_utterances = []
    success_dialogues = []
    failed_dialogues = []

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
        result = row["result"]

        agent_utts, customer_utts = separate_utterances(data["transcript"])

        dialogue_data = {
            "match_key": match_key,
            "result": result,
            "agent_utterances": agent_utts,
            "customer_utterances": customer_utts,
            "full_text": data["full_text"],
            "transcript": data["transcript"]
        }

        all_dialogues.append(dialogue_data)
        all_agent_utterances.extend(agent_utts)
        all_customer_utterances.extend(customer_utts)

        if result == "success":
            success_dialogues.append(dialogue_data)
        else:
            failed_dialogues.append(dialogue_data)

    print(f"有效对话: {len(all_dialogues)}")
    print(f"  成功: {len(success_dialogues)}")
    print(f"  失败: {len(failed_dialogues)}")

    print("\n" + "="*80)
    print("1. 所有成功对话完整记录")
    print("="*80)

    idx = 1
    for d in success_dialogues:
        print(f"\n--- 成功对话 {idx} (Match Key: {d['match_key']})")
        idx += 1
        for i, (agent_utt, customer_utt) in enumerate(zip(d['agent_utterances'], d['customer_utterances'])):
            print(f"  [{i+1}] AGENT: {agent_utt}")
            print(f"      CUSTOMER: {customer_utt}")
        if len(d['agent_utterances']) > len(d['customer_utterances']):
            for i in range(len(d['customer_utterances']), len(d['agent_utterances'])):
                print(f"  [{i+1}] AGENT: {d['agent_utterances'][i]}")

    print("\n" + "="*80)
    print("2. 所有失败对话完整记录")
    print("="*80)

    idx = 1
    for d in failed_dialogues:
        print(f"\n--- 失败对话 {idx} (Match Key: {d['match_key']})")
        idx += 1
        for i, (agent_utt, customer_utt) in enumerate(zip(d['agent_utterances'], d['customer_utterances'])):
            print(f"  [{i+1}] AGENT: {agent_utt}")
            print(f"      CUSTOMER: {customer_utt}")
        if len(d['agent_utterances']) > len(d['customer_utterances']):
            for i in range(len(d['customer_utterances']), len(d['agent_utterances'])):
                print(f"  [{i+1}] AGENT: {d['agent_utterances'][i]}")

    print("\n" + "="*80)
    print("3. 催收员话术库（按使用频率）")
    print("="*80)

    agent_counter = Counter(all_agent_utterances)

    print(f"\n所有催收员话术 (共 {len(agent_counter)} 种):")
    for utt, cnt in agent_counter.most_common(50):
        print(f"  [{cnt}] {utt}")

    print("\n" + "="*80)
    print("4. 按对话阶段分类的话术")
    print("="*80)

    greeting_phrases = []
    identify_phrases = []
    time_phrases = []
    confirm_phrases = []
    closing_phrases = []
    app_phrases = []

    for utt in all_agent_utterances:
        utt_lower = utt.lower()
        if any(g in utt_lower for g in ["halo", "selamat", "hello", "hi"]):
            greeting_phrases.append(utt)
        if any(i in utt_lower for i in ["dengan", "bapak", "ibu", "pak", "bu", "nama"]):
            identify_phrases.append(utt)
        if any(t in utt_lower for t in ["jam", "pukul", "kapan", "hari", "nanti", "tunggu"]):
            time_phrases.append(utt)
        if any(c in utt_lower for c in ["oke", "ya", "iya", "baik", "siap"]):
            confirm_phrases.append(utt)
        if any(e in utt_lower for e in ["terima kasih", "makasih", "sampai"]):
            closing_phrases.append(utt)
        if any(a in utt_lower for a in ["aplikasi", "ekstra", "uang"]):
            app_phrases.append(utt)

    print("\n[问候类话术]")
    for utt, cnt in Counter(greeting_phrases).most_common(20):
        print(f"  [{cnt}] {utt}")

    print("\n[身份确认类话术]")
    for utt, cnt in Counter(identify_phrases).most_common(20):
        print(f"  [{cnt}] {utt}")

    print("\n[时间/约定类话术]")
    for utt, cnt in Counter(time_phrases).most_common(20):
        print(f"  [{cnt}] {utt}")

    print("\n[确认类话术]")
    for utt, cnt in Counter(confirm_phrases).most_common(20):
        print(f"  [{cnt}] {utt}")

    print("\n[结束类话术]")
    for utt, cnt in Counter(closing_phrases).most_common(20):
        print(f"  [{cnt}] {utt}")

    print("\n[提及应用类话术]")
    for utt, cnt in Counter(app_phrases).most_common(20):
        print(f"  [{cnt}] {utt}")

    output_data = {
        "all_dialogues": all_dialogues,
        "agent_utterance_library": dict(Counter(all_agent_utterances).most_common(100)),
        "by_category": {
            "greeting": dict(Counter(greeting_phrases).most_common(50)),
            "identify": dict(Counter(identify_phrases).most_common(50)),
            "time": dict(Counter(time_phrases).most_common(50)),
            "confirm": dict(Counter(confirm_phrases).most_common(50)),
            "closing": dict(Counter(closing_phrases).most_common(50)),
            "app": dict(Counter(app_phrases).most_common(50))
        }
    }

    output_file = Path("data/processed/comprehensive_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n完整分析结果已保存: {output_file}")

    print("\n" + "="*80)
    print("5. 成功对话统计汇总")
    print("="*80)

    print(f"\n成功对话数: {len(success_dialogues)}")
    print(f"失败对话数: {len(failed_dialogues)}")
    print(f"催收员话术总数: {len(all_agent_utterances)}")
    print(f"独特话术种类: {len(agent_counter)}")

    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()
