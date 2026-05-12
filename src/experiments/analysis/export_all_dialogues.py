#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出所有对话到Markdown文档
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
    label_file = Path("data/raw/leads/label-chat-sample.xlsx")
    df = pd.read_excel(label_file)
    df["result"] = df["repay_type"].apply(
        lambda x: "success" if pd.notna(x) and x in ["repay", "extend"] else "failed"
    )

    transcripts_dir = Path("data/processed/transcripts")
    transcript_files = list(transcripts_dir.glob("*.json"))

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
            "full_text": data["full_text"]
        }

        if result == "success":
            success_dialogues.append(dialogue_data)
        else:
            failed_dialogues.append(dialogue_data)

    output_md = []
    output_md.append("# 所有对话完整记录\n")
    output_md.append(f"- 成功对话: {len(success_dialogues)} 个\n")
    output_md.append(f"- 失败对话: {len(failed_dialogues)} 个\n")
    output_md.append(f"- 总计: {len(success_dialogues) + len(failed_dialogues)} 个\n")

    output_md.append("\n---\n")
    output_md.append("## 成功对话\n")

    for idx, d in enumerate(success_dialogues, 1):
        output_md.append(f"\n### 成功对话 {idx}\n")
        output_md.append(f"- Match Key: `{d['match_key']}`\n")
        output_md.append(f"- 结果: 成功\n")
        output_md.append("\n对话内容:\n")

        max_len = max(len(d['agent_utterances']), len(d['customer_utterances']))
        for i in range(max_len):
            if i < len(d['agent_utterances']):
                output_md.append(f"- **AGENT**: {d['agent_utterances'][i]}\n")
            if i < len(d['customer_utterances']):
                output_md.append(f"- **CUSTOMER**: {d['customer_utterances'][i]}\n")

        output_md.append(f"\n完整文本:\n```\n{d['full_text']}\n```\n")

    output_md.append("\n---\n")
    output_md.append("## 失败对话\n")

    for idx, d in enumerate(failed_dialogues, 1):
        output_md.append(f"\n### 失败对话 {idx}\n")
        output_md.append(f"- Match Key: `{d['match_key']}`\n")
        output_md.append(f"- 结果: 失败\n")
        output_md.append("\n对话内容:\n")

        max_len = max(len(d['agent_utterances']), len(d['customer_utterances']))
        for i in range(max_len):
            if i < len(d['agent_utterances']):
                output_md.append(f"- **AGENT**: {d['agent_utterances'][i]}\n")
            if i < len(d['customer_utterances']):
                output_md.append(f"- **CUSTOMER**: {d['customer_utterances'][i]}\n")

        output_md.append(f"\n完整文本:\n```\n{d['full_text']}\n```\n")

    output_file = Path("../docs/所有对话完整记录.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("".join(output_md))

    print(f"已导出 {len(success_dialogues) + len(failed_dialogues)} 个对话到: {output_file}")


if __name__ == "__main__":
    main()
