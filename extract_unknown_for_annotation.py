#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取所有unknown意图的用户回复，导出为待人工标注格式
同时导出所有已标注的用户回复用于交叉检查
"""
import json
from pathlib import Path
import csv
from typing import List, Dict

# 路径配置
GOLD_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset")
OUTPUT_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/manual_annotation")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def extract_all_user_utterances() -> Dict[str, List]:
    """提取所有用户回复，分为unknown和已标注两类"""
    unknown_utterances = []
    labeled_utterances = []
    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            case_id = data.get("case_id", file_path.stem)
            dialogue = data.get("dialogue", [])

            for turn in dialogue:
                if turn.get("speaker") == "customer":
                    text = turn.get("text", "").strip()
                    intent = turn.get("user_intent", "unknown")
                    turn_num = turn.get("turn_number", 0)

                    if not text:
                        continue

                    utterance_info = {
                        "case_id": case_id,
                        "turn_number": turn_num,
                        "text": text,
                        "current_intent": intent,
                        "file_path": str(file_path)
                    }

                    if intent == "unknown":
                        unknown_utterances.append(utterance_info)
                    else:
                        labeled_utterances.append(utterance_info)

        except Exception as e:
            print(f"处理文件{file_path.name}出错: {e}")

    return {
        "unknown": unknown_utterances,
        "labeled": labeled_utterances
    }

def export_to_csv(utterances: List[Dict], output_file: str):
    """导出为CSV格式方便标注"""
    with open(OUTPUT_DIR / output_file, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ["case_id", "turn_number", "text", "current_intent", "manual_intent", "notes"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for utt in utterances:
            writer.writerow({
                "case_id": utt["case_id"],
                "turn_number": utt["turn_number"],
                "text": utt["text"],
                "current_intent": utt["current_intent"],
                "manual_intent": "",
                "notes": ""
            })

def main():
    print("正在提取用户回复...")
    data = extract_all_user_utterances()

    print(f"提取到unknown意图回复: {len(data['unknown'])}条")
    print(f"提取到已标注意图回复: {len(data['labeled'])}条")

    # 导出unknown待标注
    export_to_csv(data["unknown"], "unknown_intent_待标注.csv")
    # 导出已标注待检查
    export_to_csv(data["labeled"], "labeled_intent_待检查.csv")

    # 导出意图说明手册
    intent_definitions = {
        "deny_identity": "用户否认身份/表示打错电话/不是要找的人",
        "busy_later": "用户表示现在忙/不方便/等下再说/稍后回电",
        "threaten": "用户威胁要投诉/报警/告到监管机构",
        "ask_extension": "用户申请延期还款/展期/宽限几天",
        "ask_amount": "用户询问欠款金额/多少钱/还有多少没还",
        "question_identity": "用户质疑催收人员身份/问对方是谁/从哪来的/要证据",
        "no_money": "用户表示没钱/还不起/经济困难/工资没发",
        "confirm_time": "用户给出明确的还款时间/承诺什么时候还",
        "agree_to_pay": "用户同意还款/答应会还/表示会处理",
        "refuse_to_pay": "用户明确拒绝还款/表示不还/不打算还",
        "confirm_identity": "用户确认身份/应答/是的/我就是/对的",
        "greeting": "用户问候/打招呼/喂/你好/早上好/下午好",
        "ask_fee": "用户询问利息/滞纳金/手续费/为什么费用这么高",
        "ask_payment_method": "用户询问还款方式/转账到哪里/账户信息",
        "already_paid": "用户表示已经还款/已经转了/刚才还过了",
        "partial_payment": "用户询问/申请部分还款/先还一部分/分期还",
        "third_party": "接听人是第三方/家属/同事/表示要找的人不在",
        "dont_know": "用户表示不知道/不清楚/不了解相关情况",
        "unknown": "无法识别的意图/语义不完整/噪音/无效回复"
    }

    with open(OUTPUT_DIR / "intent标注规范.md", 'w', encoding='utf-8') as f:
        f.write("# 催收对话用户意图标注规范\n\n")
        f.write("## 意图类型定义\n\n")
        for intent, desc in intent_definitions.items():
            f.write(f"### `{intent}`\n")
            f.write(f"{desc}\n\n")
        f.write("\n## 标注规则\n")
        f.write("1. 优先匹配最具体的意图，而不是通用意图\n")
        f.write("2. 语义含糊/无法确定的标记为unknown\n")
        f.write("3. ASR识别错误严重、完全看不懂的标记为unknown\n")
        f.write("4. 一个回复同时包含多个意图时，选择最核心的那个意图\n")

    print(f"\n文件已导出到: {OUTPUT_DIR}")
    print("- unknown_intent_待标注.csv: 1647条待标注的unknown回复")
    print("- labeled_intent_待检查.csv: 1854条规则标注的回复待检查")
    print("- intent标注规范.md: 标注参考手册")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
