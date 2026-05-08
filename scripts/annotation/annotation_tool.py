#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金数据集标注工具
"""
import json
from pathlib import Path
import sys
from typing import Dict, List

ANNOTATION_LIST_PATH = "data/gold_dataset_annotation_list.json"
TRANSCRIPTS_DIR = "data/processed/transcripts/"
OUTPUT_DIR = "data/gold_dataset/"

# 创建输出目录
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

def load_annotation_list() -> Dict:
    """加载标注列表"""
    with open(ANNOTATION_LIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_annotation_list(annotation_list: Dict):
    """保存标注列表"""
    with open(ANNOTATION_LIST_PATH, "w", encoding="utf-8") as f:
        json.dump(annotation_list, f, ensure_ascii=False, indent=2)

def load_transcript(file_name: str) -> Dict:
    """加载对话文件"""
    file_path = Path(TRANSCRIPTS_DIR) / file_name
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_annotation(annotation: Dict, file_name: str):
    """保存标注结果"""
    output_path = Path(OUTPUT_DIR) / file_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(annotation, f, ensure_ascii=False, indent=2)

def display_dialogue(transcript: Dict):
    """显示对话内容"""
    print("\n" + "="*80)
    print("对话内容:")
    print("="*80)

    if "transcript_with_speakers" in transcript:
        for turn in transcript["transcript_with_speakers"]:
            speaker = "坐席" if turn["speaker"] == "AGENT" else "用户"
            print(f"{speaker}: {turn['text'].strip()}")
    else:
        for i, turn in enumerate(transcript["transcript"]):
            speaker = "未知"
            if i % 2 == 0:
                speaker = "坐席(猜测)"
            else:
                speaker = "用户(猜测)"
            print(f"{speaker}: {turn['text'].strip()}")

    print("="*80 + "\n")

def annotate_dialogue(item: Dict, transcript: Dict) -> Dict:
    """标注单个对话"""
    print(f"\n标注对话: {item['id']} - {item['file']}")
    print(f"类别: {', '.join(item['categories'])}")
    print(f"抗拒程度: {item['resistance_level']}")
    print(f"对话轮数: {item['turns']}")
    print(f"时长: {item['duration']}秒\n")

    # 显示对话
    display_dialogue(transcript)

    # 开始标注
    annotation = {
        "version": "1.0",
        "case_id": item["file"].replace(".json", ""),
        "basic_info": {
            "collection_stage": "",
            "call_duration": item["duration"],
            "call_result": ""
        },
        "user_profile": {
            "persona": "",
            "resistance_level": item["resistance_level"]
        },
        "dialogue": [],
        "compliance": {
            "has_violation": False,
            "violation_details": ""
        },
        "annotation_info": {
            "labeler": "",
            "label_time": "",
            "notes": ""
        }
    }

    # 1. 标注基本信息
    print("=== 基本信息标注 ===")

    # 催收阶段
    while True:
        stage = input("请选择催收阶段 (H2/H1/S0) [当前建议: H2]: ").strip()
        if stage in ["H2", "H1", "S0", ""]:
            annotation["basic_info"]["collection_stage"] = stage or "H2"
            break
        print("无效输入，请输入H2/H1/S0或留空使用默认值H2")

    # 通话结果
    while True:
        result = input("请选择通话结果 (success/failure/extension): ").strip()
        if result in ["success", "failure", "extension"]:
            annotation["basic_info"]["call_result"] = result
            break
        print("无效输入，请输入success/failure/extension")

    # 2. 标注用户画像
    print("\n=== 用户画像标注 ===")

    # 用户类型
    personas = ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful", "excuse_master"]
    print(f"可选用户类型: {', '.join(personas)}")
    print(f"当前建议: {item['categories']}")
    while True:
        persona = input("请选择用户类型: ").strip()
        if persona in personas:
            annotation["user_profile"]["persona"] = persona
            break
        print(f"无效输入，请输入以下选项之一: {', '.join(personas)}")

    # 3. 标注对话轮次
    print("\n=== 对话轮次标注 ===")
    print("请对每一轮对话进行标注：")
    print("对于坐席轮次：需要标注是否正确(is_correct: true/false)，如果不正确请提供标准回复(standard_response)")
    print("对于用户轮次：需要标注用户意图(user_intent)\n")

    turns = transcript.get("transcript_with_speakers", transcript["transcript"])

    for i, turn in enumerate(turns):
        speaker = turn.get("speaker", "UNKNOWN")
        speaker_cn = "坐席" if speaker == "AGENT" else "用户" if speaker == "CUSTOMER" else "未知"
        text = turn["text"].strip()

        print(f"[{i+1}] {speaker_cn}: {text}")

        turn_annotation = {
            "turn_number": i + 1,
            "speaker": "agent" if speaker == "AGENT" else "customer",
            "text": text,
            "stage": "",
            "is_correct": None,
            "standard_response": "",
            "user_intent": ""
        }

        # 标注对话阶段
        stages = ["greeting", "identity", "purpose", "ask_time", "push", "negotiate", "commit", "close"]
        print(f"可选阶段: {', '.join(stages)}")
        while True:
            stage = input("请选择对话阶段: ").strip()
            if stage in stages:
                turn_annotation["stage"] = stage
                break
            print(f"无效输入，请输入以下选项之一: {', '.join(stages)}")

        if speaker == "AGENT":
            # 坐席轮次：标注是否正确
            while True:
                is_correct = input("坐席回复是否正确? (y/n): ").strip().lower()
                if is_correct in ["y", "n"]:
                    turn_annotation["is_correct"] = is_correct == "y"
                    break
                print("无效输入，请输入y/n")

            if not turn_annotation["is_correct"]:
                standard_response = input("请输入标准回复: ").strip()
                turn_annotation["standard_response"] = standard_response
        else:
            # 用户轮次：标注用户意图
            user_intent = input("请输入用户意图: ").strip()
            turn_annotation["user_intent"] = user_intent

        annotation["dialogue"].append(turn_annotation)
        print()

    # 4. 标注合规检查
    print("\n=== 合规检查标注 ===")
    while True:
        has_violation = input("对话中是否有违规内容? (y/n): ").strip().lower()
        if has_violation in ["y", "n"]:
            annotation["compliance"]["has_violation"] = has_violation == "y"
            break
        print("无效输入，请输入y/n")

    if annotation["compliance"]["has_violation"]:
        violation_details = input("请输入违规详情: ").strip()
        annotation["compliance"]["violation_details"] = violation_details

    # 5. 标注信息
    print("\n=== 标注信息 ===")
    labeler = input("请输入标注人姓名: ").strip()
    annotation["annotation_info"]["labeler"] = labeler

    from datetime import datetime
    annotation["annotation_info"]["label_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    notes = input("请输入其他备注信息(可选): ").strip()
    annotation["annotation_info"]["notes"] = notes

    return annotation

def main():
    """主函数"""
    print("=== 黄金数据集标注工具 ===")

    # 加载标注列表
    annotation_list = load_annotation_list()
    items = annotation_list["items"]

    # 统计进度
    total = len(items)
    completed = sum(1 for item in items if item["status"] == "completed")
    pending = total - completed

    print(f"总样本数: {total}")
    print(f"已完成: {completed}")
    print(f"待标注: {pending}\n")

    if pending == 0:
        print("所有样本已标注完成!")
        return

    # 显示待标注列表
    print("待标注样本列表:")
    pending_items = [item for item in items if item["status"] != "completed"]
    for i, item in enumerate(pending_items[:10]):  # 只显示前10个
        print(f"{i+1}. {item['id']}: {item['file']} - 类别: {', '.join(item['categories'])}")
    if len(pending_items) > 10:
        print(f"... 还有 {len(pending_items) - 10} 个待标注样本\n")

    # 选择要标注的样本
    while True:
        choice = input(f"请选择要标注的样本编号 (1-{len(pending_items)}), 或输入 'q' 退出: ").strip()
        if choice.lower() == 'q':
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(pending_items):
                selected_item = pending_items[idx]
                break
            else:
                print(f"无效编号，请输入1到{len(pending_items)}之间的数字")
        except ValueError:
            print("无效输入，请输入数字或'q'退出")

    # 加载对话
    transcript = load_transcript(selected_item["file"])

    # 开始标注
    try:
        annotation = annotate_dialogue(selected_item, transcript)
    except KeyboardInterrupt:
        print("\n\n标注已中断，本次修改未保存。")
        return

    # 确认保存
    print("\n" + "="*80)
    print("标注完成，请确认是否保存:")
    print("="*80)
    print(f"对话ID: {selected_item['id']}")
    print(f"文件: {selected_item['file']}")
    print(f"催收阶段: {annotation['basic_info']['collection_stage']}")
    print(f"通话结果: {annotation['basic_info']['call_result']}")
    print(f"用户类型: {annotation['user_profile']['persona']}")
    print(f"抗拒程度: {annotation['user_profile']['resistance_level']}")
    print(f"是否有违规: {'是' if annotation['compliance']['has_violation'] else '否'}")
    if annotation['compliance']['has_violation']:
        print(f"违规详情: {annotation['compliance']['violation_details']}")
    print(f"标注人: {annotation['annotation_info']['labeler']}")

    while True:
        confirm = input("\n是否保存标注结果? (y/n): ").strip().lower()
        if confirm in ["y", "n"]:
            break
        print("无效输入，请输入y/n")

    if confirm == "y":
        # 保存标注结果
        save_annotation(annotation, selected_item["file"])

        # 更新标注列表状态
        for item in items:
            if item["id"] == selected_item["id"]:
                item["status"] = "completed"
                break

        save_annotation_list(annotation_list)
        print(f"\n标注结果已保存到: {OUTPUT_DIR}/{selected_item['file']}")
        print("标注状态已更新。")
    else:
        print("\n标注结果未保存。")

if __name__ == "__main__":
    main()
