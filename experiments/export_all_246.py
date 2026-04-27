#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出所有246个有效对话到Markdown文档
"""
import pandas as pd
import json
from pathlib import Path
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
    label_file = Path("data/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))

    all_dialogues = []
    success_dialogues = []
    failed_dialogues = []
    unmatched_dialogues = []

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

            if result == "success":
                success_dialogues.append(dialogue_data)
            else:
                failed_dialogues.append(dialogue_data)
        else:
            unmatched_dialogues.append(dialogue_data)

    # 生成Markdown
    output_md = []
    output_md.append("# 所有246个对话完整记录\n")
    output_md.append(f"- 总对话数: {len(all_dialogues)}\n")
    output_md.append(f"- 成功对话: {len(success_dialogues)} 个\n")
    output_md.append(f"- 失败对话: {len(failed_dialogues)} 个\n")
    output_md.append(f"- 无标签对话: {len(unmatched_dialogues)} 个\n")

    output_md.append("\n---\n")
    output_md.append("## 成功对话 (144个)\n")

    for idx, d in enumerate(success_dialogues, 1):
        output_md.append(f"\n### 成功对话 {idx}\n")
        output_md.append(f"- Match Key: `{d['match_key']}`\n")
        output_md.append(f"- Result: Success\n")
        if d.get("repay_type"):
            output_md.append(f"- Repay Type: {d['repay_type']}\n")
        output_md.append("\n对话内容:\n")

        max_len = max(len(d["agent_utterances"]), len(d["customer_utterances"]))
        for i in range(max_len):
            if i < len(d["agent_utterances"]):
                output_md.append(f"- **AGENT**: {d['agent_utterances'][i]}\n")
            if i < len(d["customer_utterances"]):
                output_md.append(f"- **CUSTOMER**: {d['customer_utterances'][i]}\n")

        output_md.append(f"\n完整文本:\n```\n{d['full_text'][:1000]}\n```\n")

    output_md.append("\n---\n")
    output_md.append("## 失败对话 (98个)\n")

    for idx, d in enumerate(failed_dialogues, 1):
        output_md.append(f"\n### 失败对话 {idx}\n")
        output_md.append(f"- Match Key: `{d['match_key']}`\n")
        output_md.append(f"- Result: Failed\n")
        output_md.append("\n对话内容:\n")

        max_len = max(len(d["agent_utterances"]), len(d["customer_utterances"]))
        for i in range(max_len):
            if i < len(d["agent_utterances"]):
                output_md.append(f"- **AGENT**: {d['agent_utterances'][i]}\n")
            if i < len(d["customer_utterances"]):
                output_md.append(f"- **CUSTOMER**: {d['customer_utterances'][i]}\n")

        output_md.append(f"\n完整文本:\n```\n{d['full_text'][:1000]}\n```\n")

    if unmatched_dialogues:
        output_md.append("\n---\n")
        output_md.append("## 无标签对话 (4个)\n")
        for idx, d in enumerate(unmatched_dialogues, 1):
            output_md.append(f"\n### 无标签对话 {idx}\n")
            output_md.append(f"- Match Key: `{d['match_key']}`\n")
            output_md.append(f"\n完整文本:\n```\n{d['full_text'][:1000]}\n```\n")

    output_file = Path("../docs/all_246_dialogues.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("".join(output_md))

    print(f"已导出 {len(all_dialogues)} 个对话到: {output_file}")

    # 同时生成精简版话术库
    output_lib = []
    output_lib.append("# 完整话术库 - 基于246个对话\n")
    output_lib.append("\n## 数据统计\n")
    output_lib.append(f"- 总对话数: {len(all_dialogues)}\n")
    output_lib.append(f"- 成功: {len(success_dialogues)}\n")
    output_lib.append(f"- 失败: {len(failed_dialogues)}\n")

    # 收集所有话术
    all_agent_utts = []
    for d in all_dialogues:
        all_agent_utts.extend(d["agent_utterances"])

    from collections import Counter
    counter = Counter(all_agent_utts)

    output_lib.append(f"\n## 催收员高频话术 TOP 100\n")
    for utt, cnt in counter.most_common(100):
        output_lib.append(f"- [{cnt}] {utt}\n")

    # 按分类整理
    greeting = []
    identify = []
    time_commit = []
    confirm = []
    closing = []

    for utt in all_agent_utts:
        utt_lower = utt.lower()
        if any(g in utt_lower for g in ["halo", "selamat", "hello", "hi"]):
            greeting.append(utt)
        if any(i in utt_lower for i in ["dengan", "bapak", "ibu", "pak", "bu"]):
            identify.append(utt)
        if any(t in utt_lower for t in ["jam", "pukul", "kapan", "tunggu"]):
            time_commit.append(utt)
        if any(c in utt_lower for c in ["oke", "ya", "iya", "baik", "siap"]):
            confirm.append(utt)
        if any(e in utt_lower for e in ["terima kasih", "makasih", "sampai"]):
            closing.append(utt)

    output_lib.append(f"\n## 分类话术库\n")

    output_lib.append(f"\n### 问候类 (TOP 30)\n")
    for utt, cnt in Counter(greeting).most_common(30):
        output_lib.append(f"- [{cnt}] {utt}\n")

    output_lib.append(f"\n### 身份确认类 (TOP 30)\n")
    for utt, cnt in Counter(identify).most_common(30):
        output_lib.append(f"- [{cnt}] {utt}\n")

    output_lib.append(f"\n### 时间约定类 (TOP 30)\n")
    for utt, cnt in Counter(time_commit).most_common(30):
        output_lib.append(f"- [{cnt}] {utt}\n")

    output_lib.append(f"\n### 确认类 (TOP 30)\n")
    for utt, cnt in Counter(confirm).most_common(30):
        output_lib.append(f"- [{cnt}] {utt}\n")

    output_lib.append(f"\n### 结束类 (TOP 20)\n")
    for utt, cnt in Counter(closing).most_common(20):
        output_lib.append(f"- [{cnt}] {utt}\n")

    lib_file = Path("../docs/complete_phrase_library.md")
    with open(lib_file, "w", encoding="utf-8") as f:
        f.write("".join(output_lib))

    print(f"话术库已保存到: {lib_file}")


if __name__ == "__main__":
    main()
