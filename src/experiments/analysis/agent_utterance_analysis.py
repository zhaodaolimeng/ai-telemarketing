#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
催收员话术有效性分析（服务智能语音开发）
重点关注催收员说什么能提高催回率
"""
import pandas as pd
import json
from pathlib import Path
from collections import Counter, defaultdict
import sys
import io

# 设置UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


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
    return False


def separate_utterances(transcript):
    """
    分离催收员和客户的话术
    基于启发式：先说话的通常是催收员
    """
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


def extract_utterance_patterns(utterances):
    """
    提取话术模式
    """
    patterns = []
    for utt in utterances:
        utt_lower = utt.lower()
        if any(greet in utt_lower for greet in ["halo", "selamat", "hello", "hi"]):
            patterns.append("greeting")
        if any(ident in utt_lower for ident in ["dengan", "bapak", "ibu", "pak", "bu"]):
            patterns.append("identify_caller")
        if any(app in utt_lower for app in ["aplikasi", "ekstra", "uang"]):
            patterns.append("mention_app")
        if any(time in utt_lower for time in ["jam", "pukul", "kapan", "hari"]):
            patterns.append("ask_time")
        if any(commit in utt_lower for commit in ["nanti", "tunggu", "maksimal", "pasti"]):
            patterns.append("commit_time")
        if any(confirm in utt_lower for confirm in ["oke", "ya", "iya", "baik", "siap"]):
            patterns.append("confirmation")
        if any(end in utt_lower for end in ["terima kasih", "makasih", "sampai"]):
            patterns.append("closing")
    return patterns


def main():
    print("="*80)
    print("催收员话术有效性分析 - 服务智能语音开发")
    print("="*80)

    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    success_agent = []
    failed_agent = []
    success_patterns = []
    failed_patterns = []
    all_dialogues = []

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
        patterns = extract_utterance_patterns(agent_utts)

        dialogue_data = {
            "match_key": match_key,
            "result": result,
            "agent_utterances": agent_utts,
            "customer_utterances": customer_utts,
            "patterns": patterns,
            "full_text": data["full_text"]
        }
        all_dialogues.append(dialogue_data)

        if result == "success":
            success_agent.extend(agent_utts)
            success_patterns.extend(patterns)
        else:
            failed_agent.extend(agent_utts)
            failed_patterns.extend(patterns)

    print(f"有效对话: {len(all_dialogues)}")
    print(f"  成功: {sum(1 for d in all_dialogues if d['result'] == 'success')}")
    print(f"  失败: {sum(1 for d in all_dialogues if d['result'] == 'failed')}")

    print("\n" + "="*80)
    print("1. 话术模式对比")
    print("="*80)

    success_pat_count = Counter(success_patterns)
    failed_pat_count = Counter(failed_patterns)

    print("\n[成功对话 - 催收员话术模式]")
    for pat, cnt in success_pat_count.most_common():
        print(f"  {pat}: {cnt}")

    print("\n[失败对话 - 催收员话术模式]")
    for pat, cnt in failed_pat_count.most_common():
        print(f"  {pat}: {cnt}")

    print("\n" + "="*80)
    print("2. 催收员高频话术")
    print("="*80)

    def get_phrases(utterances):
        phrases = []
        for utt in utterances:
            words = utt.lower().split()
            for i in range(len(words)-1):
                phrases.append(" ".join(words[i:i+2]))
            for i in range(len(words)-2):
                phrases.append(" ".join(words[i:i+3]))
        return Counter(phrases)

    success_phrases = get_phrases(success_agent)
    failed_phrases = get_phrases(failed_agent)

    print("\n[成功对话 - 催收员高频短语]")
    for phrase, cnt in success_phrases.most_common(20):
        print(f"  '{phrase}': {cnt}")

    print("\n[失败对话 - 催收员高频短语]")
    for phrase, cnt in failed_phrases.most_common(20):
        print(f"  '{phrase}': {cnt}")

    print("\n" + "="*80)
    print("3. 差异显著的话术对比")
    print("="*80)

    success_docs = sum(1 for d in all_dialogues if d['result'] == 'success')
    failed_docs = sum(1 for d in all_dialogues if d['result'] == 'failed')

    all_phrases = set(success_phrases.keys()).union(set(failed_phrases.keys()))
    diff_list = []

    for phrase in all_phrases:
        sc = success_phrases.get(phrase, 0)
        fc = failed_phrases.get(phrase, 0)
        if sc + fc > 3:
            s_ratio = sc / success_docs if success_docs else 0
            f_ratio = fc / failed_docs if failed_docs else 0
            diff = s_ratio - f_ratio
            diff_list.append((phrase, diff, sc, fc))

    diff_list.sort(key=lambda x: -abs(x[1]))

    print("\n[成功导向话术]")
    for phrase, diff, sc, fc in diff_list[:15]:
        if diff > 0:
            print(f"  [+] '{phrase}': 成功{sc}次, 失败{fc}次 (diff: +{diff:.2f})")

    print("\n[失败导向话术]")
    for phrase, diff, sc, fc in diff_list[:30]:
        if diff < 0:
            print(f"  [-] '{phrase}': 成功{sc}次, 失败{fc}次 (diff: {diff:.2f})")

    print("\n" + "="*80)
    print("4. 对话流程结构分析")
    print("="*80)

    success_dialogues = [d for d in all_dialogues if d['result'] == 'success']
    failed_dialogues = [d for d in all_dialogues if d['result'] == 'failed']

    print(f"\n成功对话平均轮数: {sum(len(d['agent_utterances'])+len(d['customer_utterances']) for d in success_dialogues)/len(success_dialogues):.1f}")
    print(f"失败对话平均轮数: {sum(len(d['agent_utterances'])+len(d['customer_utterances']) for d in failed_dialogues)/len(failed_dialogues):.1f}")

    print("\n" + "="*80)
    print("5. 完整对话示例（带角色分离）")
    print("="*80)

    print("\n[成功对话示例]")
    if success_dialogues:
        d = success_dialogues[0]
        print(f"\nMatch Key: {d['match_key']}")
        print("\n对话流程:")
        for i, (agent_utt, customer_utt) in enumerate(zip(d['agent_utterances'], d['customer_utterances'])):
            print(f"  [{i+1}] AGENT: {agent_utt}")
            print(f"      CUSTOMER: {customer_utt}")
        if len(d['agent_utterances']) > len(d['customer_utterances']):
            for i in range(len(d['customer_utterances']), len(d['agent_utterances'])):
                print(f"  [{i+1}] AGENT: {d['agent_utterances'][i]}")

    print("\n[失败对话示例]")
    if failed_dialogues:
        d = failed_dialogues[0]
        print(f"\nMatch Key: {d['match_key']}")
        print("\n对话流程:")
        for i, (agent_utt, customer_utt) in enumerate(zip(d['agent_utterances'], d['customer_utterances'])):
            print(f"  [{i+1}] AGENT: {agent_utt}")
            print(f"      CUSTOMER: {customer_utt}")
        if len(d['agent_utterances']) > len(d['customer_utterances']):
            for i in range(len(d['customer_utterances']), len(d['agent_utterances'])):
                print(f"  [{i+1}] AGENT: {d['agent_utterances'][i]}")

    output_file = Path("data/processed/agent_utterance_analysis.json")
    result_data = {
        "all_dialogues": all_dialogues,
        "success_patterns": dict(success_pat_count),
        "failed_patterns": dict(failed_pat_count),
        "success_phrases": dict(success_phrases.most_common(50)),
        "failed_phrases": dict(failed_phrases.most_common(50))
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果已保存: {output_file}")

    print("\n" + "="*80)
    print("6. 智能语音开发 - 话术建议")
    print("="*80)

    print("""
[推荐话术模板]

1. 开场问候
   - "Halo, selamat [pagi/siang/sore] Pak/Bu"
   - "Halo, dengan [Nama] dari aplikasi Extra"

2. 身份确认
   - "Dengan Bapak/Ibu [Nama] ya?"
   - "Benar, saya dari aplikasi Extra untuk pinjaman"

3. 明确还款时间
   - "Kapan bisa dibayar, Pak/Bu? Jam berapa?"
   - "Jam [X] ya Pak/Bu, saya tunggu"
   - "Maksimal jam [X] hari ini ya"

4. 获得确认
   - "Oke Pak/Bu, saya tunggu jam [X]"
   - "Baik, terima kasih konfirmasinya"

5. 结束对话
   - "Terima kasih Pak/Bu, selamat [pagi/siang/sore]"
   - "Siap, sampai jumpa"

[需要避免的话术]

1. 避免过度强调应用
   - "Untuk aplikasi, wajib dari aplikasi"
   - "Aplikasi Extra uang"

2. 避免被动语态
   - "Dibayar jam berapa?"
   - "Kapan bisa bayar, Pak/Bu?"

3. 避免接受模糊回应
   - "Oke aman"
   - "Jam berapa tepatnya, Pak/Bu?"

[最佳对话流程]
问候 -> 确认身份 -> 说明目的 -> 约定具体时间 -> 获得确认 -> 礼貌结束

[关键成功特征]
- 多次使用确认用语 (oke/ya/iya)
- 使用 "saya tunggu" (我等待) 表达期待
- 明确约定具体时间点 (jam X)
- 使用礼貌称呼 (Pak/Bu/Bapak/Ibu)
- 适时表达感谢 (terima kasih)
""")

    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()
