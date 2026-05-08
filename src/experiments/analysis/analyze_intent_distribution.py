#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析数据集中的意图分布情况，检查是否有遗漏的意图类型
"""
import json
from pathlib import Path
from collections import defaultdict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GOLD_DIR = _PROJECT_ROOT / "data/gold_dataset"
ANNOTATION_LIST_FILE = _PROJECT_ROOT / "data/gold_dataset_annotation_list.json"

# 标准意图集合（扩展后）
STANDARD_INTENTS = {
    "deny_identity", "busy_later", "threaten", "ask_extension",
    "ask_amount", "question_identity", "no_money", "confirm_time",
    "agree_to_pay", "refuse_to_pay", "confirm_identity", "unknown",
    "greeting", "ask_fee", "ask_payment_method", "already_paid",
    "partial_payment", "third_party", "dont_know"
}

def analyze_intent_distribution():
    """分析所有标注文件的意图分布"""
    # 加载标注列表，区分原200条和新486条
    with open(ANNOTATION_LIST_FILE, 'r', encoding='utf-8') as f:
        annotation_list = json.load(f)
    file_to_source = {}
    for item in annotation_list["items"]:
        file_stem = item["file"].replace(".json", "")
        # 原200条人工标注priority>=1，新增的auto标注priority=1？不对，原人工标注的labeler是"ai-annotator"，新增的是"auto-annotator"
        # 所以从文件内容里读labeler更准确
        file_to_source[file_stem] = "unknown"
    # 统计意图分布
    intent_total = defaultdict(int)
    intent_original = defaultdict(int)  # 原200条人工标注
    intent_new = defaultdict(int)       # 新486条自动标注
    intent_files = defaultdict(list)
    abnormal_intents = []
    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            file_stem = file_path.stem
            labeler = data.get("annotation_info", {}).get("labeler", "")
            source = "original" if labeler == "ai-annotator" else "new"
            file_to_source[file_stem] = source
            # 提取所有customer的意图
            for turn in data.get("dialogue", []):
                if turn.get("speaker") == "customer":
                    intent = turn.get("user_intent", "unknown")
                    intent_total[intent] += 1
                    intent_files[intent].append(file_stem)
                    if source == "original":
                        intent_original[intent] += 1
                    else:
                        intent_new[intent] += 1
                    # 检查是否是异常意图
                    if intent not in STANDARD_INTENTS:
                        abnormal_intents.append({
                            "file": file_stem,
                            "intent": intent,
                            "text": turn.get("text", "")
                        })
        except Exception as e:
            print(f"处理文件{file_path.name}出错: {e}")
    # 输出结果
    print("=" * 80)
    print("意图分布分析报告")
    print("=" * 80)
    print(f"总标注文件数: {len(all_files)}")
    print(f"原人工标注文件数: {len([s for s in file_to_source.values() if s == 'original'])}")
    print(f"新增自动标注文件数: {len([s for s in file_to_source.values() if s == 'new'])}")
    print(f"\n标准意图总数: {len(STANDARD_INTENTS)}类")
    print(f"实际出现的意图数: {len(intent_total)}类")
    # 输出意图分布详情
    print("\n📊 意图分布详情:")
    print(f"{'意图类型':<20} {'总样本量':<8} {'原200条':<8} {'新增486条':<8} {'覆盖情况':<10}")
    print("-" * 70)
    all_covered = True
    for intent in sorted(STANDARD_INTENTS):
        total = intent_total.get(intent, 0)
        original = intent_original.get(intent, 0)
        new = intent_new.get(intent, 0)
        covered = "✅ 覆盖" if total > 0 else "❌ 遗漏"
        if total == 0:
            all_covered = False
        print(f"{intent:<20} {total:<8} {original:<8} {new:<8} {covered:<10}")
    # 输出非标准意图
    if abnormal_intents:
        print(f"\n⚠️ 发现{len(abnormal_intents)}个非标准意图:")
        for ab in abnormal_intents[:10]:
            print(f"  🔴 文件: {ab['file']}, 意图: {ab['intent']}, 文本: {ab['text'][:50]}...")
        if len(abnormal_intents) > 10:
            print(f"  ... 还有{len(abnormal_intents) - 10}个")
    # 检查新增数据是否覆盖所有意图
    print(f"\n🆕 新增486条数据覆盖情况:")
    missing_in_new = []
    for intent in STANDARD_INTENTS:
        if intent_new.get(intent, 0) == 0:
            missing_in_new.append(intent)
    if missing_in_new:
        print(f"⚠️ 新增数据中没有覆盖的意图: {missing_in_new}")
    else:
        print("✅ 新增数据已覆盖所有标准意图类型")
    # 输出样本量最少的TOP 5意图
    print(f"\n📉 样本量最少的5类意图:")
    sorted_intents = sorted(intent_total.items(), key=lambda x: x[1])
    for intent, count in sorted_intents[:5]:
        print(f"  {intent}: {count}个样本")
    # 统计每个意图的对话占比
    total_intent_count = sum(intent_total.values())
    print(f"\n📈 意图占比分布:")
    for intent, count in sorted(intent_total.items(), key=lambda x: -x[1]):
        percentage = count / total_intent_count * 100
        if percentage >= 1:
            print(f"  {intent:<20} {count:<6} ({percentage:.1f}%)")
    return {
        "intent_total": intent_total,
        "intent_original": intent_original,
        "intent_new": intent_new,
        "abnormal_intents": abnormal_intents,
        "missing_in_new": missing_in_new,
        "all_covered": all_covered
    }

if __name__ == "__main__":
    result = analyze_intent_distribution()
