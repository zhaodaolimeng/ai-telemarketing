#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复标注一致性问题，确保所有标注完全符合规范
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DIR = _PROJECT_ROOT / "data/gold_dataset"
ANNOTATION_LIST_FILE = _PROJECT_ROOT / "data/gold_dataset_annotation_list.json"

# 合法取值集合，与标注规范完全一致
VALID_STAGES = {
    "greeting", "identity_verification", "purpose", "negotiation",
    "ask_time", "push", "confirm", "close", "handle_objection",
    "handle_extension", "identity"
}

VALID_INTENTS = {
    "deny_identity", "busy_later", "threaten", "ask_extension",
    "ask_amount", "question_identity", "no_money", "confirm_time",
    "agree_to_pay", "refuse_to_pay", "confirm_identity", "unknown",
    "greeting", "ask_fee", "ask_payment_method", "already_paid",
    "partial_payment", "third_party", "dont_know"
}

# 字段映射关系
STAGE_MAPPING = {
    "negotiate": "negotiation",
    "identity": "identity_verification",
    "verification": "identity_verification",
    "explain": "purpose",
    "follow_up": "push",
    "closing": "close"
}

INTENT_MAPPING = {
    "unknown_intent": "unknown",
    "respond_to_greeting": "greeting",
    "answer_call_and_apologize": "confirm_identity",
    "confirm_amount": "agree_to_pay",
    "confirm_repayment": "agree_to_pay",
    "request_delay": "ask_extension",
    "user_busy": "busy_later",
    "wrong_number": "deny_identity",
    "user_threat": "threaten",
    "refuse_to_pay_now": "refuse_to_pay",
    "no_payment_plan": "no_money",
    "ask_interest": "ask_fee",
    "ask_payment_account": "ask_payment_method",
    "already_paid": "already_paid",
    "partial_payment_request": "partial_payment",
    "third_party_response": "third_party",
    "dont_understand": "dont_know"
}

def fix_single_file(file_path: Path) -> bool:
    """修复单个标注文件的一致性问题，返回是否有修改"""
    modified = False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 1. 修复label_time格式
        if "annotation_info" in data:
            annotation_info = data["annotation_info"]
            if "label_time" in annotation_info:
                label_time = annotation_info["label_time"]
                if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', label_time):
                    # 提取日期部分
                    new_time = label_time.split(' ')[0]
                    annotation_info["label_time"] = new_time
                    modified = True
                # 统一labeler
                if "labeler" in annotation_info and annotation_info["labeler"] == "ai-annotator":
                    annotation_info["labeler"] = "auto-annotator"
                    modified = True
        # 2. 修复对话轮字段问题
        if "dialogue" in data:
            dialogue = data["dialogue"]
            for turn in dialogue:
                # 补充缺失的notes字段
                if "notes" not in turn:
                    turn["notes"] = ""
                    modified = True
                # 补充缺失的standard_response字段
                if "standard_response" not in turn:
                    turn["standard_response"] = ""
                    modified = True
                # 修复stage命名
                if "stage" in turn:
                    stage = turn["stage"]
                    if stage in STAGE_MAPPING:
                        turn["stage"] = STAGE_MAPPING[stage]
                        modified = True
                    elif stage not in VALID_STAGES:
                        # 无法匹配的默认设为negotiation
                        turn["stage"] = "negotiation"
                        modified = True
                # 修复user_intent取值
                if "user_intent" in turn:
                    intent = turn["user_intent"]
                    speaker = turn.get("speaker", "")
                    if speaker == "agent":
                        if intent != "":
                            turn["user_intent"] = ""
                            modified = True
                    else:  # customer
                        if intent in INTENT_MAPPING:
                            turn["user_intent"] = INTENT_MAPPING[intent]
                            modified = True
                        elif intent not in VALID_INTENTS:
                            turn["user_intent"] = "unknown"
                            modified = True
                # 修复is_correct取值
                if "is_correct" in turn:
                    speaker = turn.get("speaker", "")
                    is_correct = turn["is_correct"]
                    if speaker == "customer":
                        if is_correct is not None:
                            turn["is_correct"] = None
                            modified = True
                    else:  # agent
                        if not isinstance(is_correct, bool):
                            turn["is_correct"] = True
                            modified = True
        # 3. 修复user_profile字段
        if "user_profile" in data:
            user_profile = data["user_profile"]
            if "persona" not in user_profile:
                # 根据抗拒程度推断persona
                resistance = user_profile.get("resistance_level", "medium")
                user_profile["persona"] = "cooperative" if resistance in ["very_low", "low"] else "resistant"
                modified = True
            elif user_profile["persona"] not in ["cooperative", "resistant"]:
                user_profile["persona"] = "cooperative"
                modified = True
        # 4. 修复compliance字段
        if "compliance" in data:
            compliance = data["compliance"]
            if "violation_details" not in compliance:
                compliance["violation_details"] = ""
                modified = True
            if "has_violation" not in compliance:
                compliance["has_violation"] = False
                modified = True
        # 5. 修复basic_info字段
        if "basic_info" in data:
            basic_info = data["basic_info"]
            if "collection_stage" not in basic_info:
                basic_info["collection_stage"] = "H2"
                modified = True
            if "call_duration" not in basic_info:
                basic_info["call_duration"] = 0.0
                modified = True
            if "call_result" in basic_info and basic_info["call_result"] not in ["success", "failure"]:
                basic_info["call_result"] = "failure"
                modified = True
        # 如果有修改，保存文件
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return modified
    except Exception as e:
        print(f"修复文件{file_path.name}时出错: {e}")
        return False

def fix_annotation_list() -> bool:
    """修复标注列表与实际文件的一致性问题"""
    modified = False
    try:
        with open(ANNOTATION_LIST_FILE, 'r', encoding='utf-8') as f:
            annotation_list = json.load(f)
        items = annotation_list.get("items", [])
        # 获取所有实际存在的文件
        actual_files = {f.stem for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"}
        # 检查列表中的文件是否都存在，删除不存在的
        new_items = []
        list_files = set()
        for item in items:
            file_stem = item.get("file", "").replace(".json", "")
            if file_stem in actual_files and file_stem not in list_files:
                new_items.append(item)
                list_files.add(file_stem)
            else:
                modified = True
        # 检查实际存在的文件是否都在列表中，补充缺失的
        max_id = max([int(item.get("id", "GOLD-000").replace("GOLD-", "")) for item in new_items], default=0)
        for file_stem in actual_files:
            if file_stem not in list_files:
                max_id += 1
                # 读取文件获取基本信息
                file_path = GOLD_DIR / f"{file_stem}.json"
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    turns = len(data.get("dialogue", []))
                    duration = data.get("basic_info", {}).get("call_duration", 0)
                    resistance = data.get("user_profile", {}).get("resistance_level", "low")
                    success = data.get("basic_info", {}).get("call_result", "failure") == "success"
                    categories = ["success" if success else "failure"]
                    if resistance in ["high", "very_high"]:
                        categories.append("high_resistance")
                    elif resistance == "medium":
                        categories.append("medium_resistance")
                    else:
                        categories.append("low_resistance")
                    # 计算stage数量
                    stages = set([turn.get("stage", "") for turn in data.get("dialogue", [])])
                    stage_count = len(stages)
                    new_item = {
                        "id": f"GOLD-{max_id:03d}",
                        "file": f"{file_stem}.json",
                        "priority": 1.0,
                        "categories": categories,
                        "resistance_level": resistance,
                        "turns": turns,
                        "duration": duration,
                        "stage_count": stage_count,
                        "status": "completed",
                        "notes": "Auto-added during consistency fix"
                    }
                    new_items.append(new_item)
                    modified = True
                except:
                    continue
        # 更新annotation_list
        if modified:
            annotation_list["items"] = new_items
            annotation_list["total"] = len(new_items)
            # 重新排序id
            for i, item in enumerate(new_items, 1):
                item["id"] = f"GOLD-{i:03d}"
            with open(ANNOTATION_LIST_FILE, 'w', encoding='utf-8') as f:
                json.dump(annotation_list, f, ensure_ascii=False, indent=2)
        return modified
    except Exception as e:
        print(f"修复标注列表时出错: {e}")
        return False

def main():
    print("=" * 80)
    print("批量修复标注一致性问题")
    print("=" * 80)
    # 获取所有标注文件
    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]
    print(f"待修复文件数量: {len(all_files)}")
    # 修复所有文件
    modified_count = 0
    for i, file_path in enumerate(all_files, 1):
        if i % 100 == 0:
            print(f"已处理: {i}/{len(all_files)}")
        if fix_single_file(file_path):
            modified_count += 1
    print(f"\n文件修复完成，共修改了{modified_count}个文件")
    # 修复标注列表
    print(f"\n正在修复标注列表...")
    list_modified = fix_annotation_list()
    if list_modified:
        print("标注列表修复完成")
    else:
        print("标注列表无需修复")
    # 输出结果
    print("\n" + "=" * 80)
    print("修复完成!")
    print("=" * 80)
    print(f"已修改文件数: {modified_count}")
    print(f"列表是否修改: {'是' if list_modified else '否'}")
    print("\n建议重新运行一致性检查，确认所有问题已解决。")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
