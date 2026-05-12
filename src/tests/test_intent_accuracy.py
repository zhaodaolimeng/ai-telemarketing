#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试意图识别准确率，对比标注结果和自动识别结果
支持测试纯规则系统和混合（规则+ML）系统
"""
import json
import sys
import argparse
sys.path.insert(0, 'src')
from pathlib import Path
from core.chatbot import IntentDetector, ASRCorrector

def main():
    parser = argparse.ArgumentParser(description='测试意图识别准确率')
    parser.add_argument('--use-ml', action='store_true', help='启用ML分类器作为fallback')
    parser.add_argument('--ml-threshold', type=float, default=0.6, help='ML分类置信度阈值')
    parser.add_argument('--model-path', default='models/simple_intent_classifier.pkl', help='ML模型路径')
    args = parser.parse_args()

    gold_dir = Path('data/raw/gold_dataset')
    intent_detector = IntentDetector()
    asr_corrector = ASRCorrector()

    # 启用ML分类器
    if args.use_ml:
        print("正在加载ML分类器...")
        success = IntentDetector.load_ml_classifier(args.model_path)
        if not success:
            print("ML分类器加载失败，将只使用规则系统")
        else:
            IntentDetector.set_ml_threshold(args.ml_threshold)
            print(f"ML分类器已启用，置信度阈值: {args.ml_threshold}")

    total = 0
    correct = 0
    errors = []
    ml_helped = 0  # ML纠正了规则系统错误的数量

    for file_path in gold_dir.glob('*.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue

        dialogue = data.get('dialogue', [])
        previous_bot_text = None  # 跟踪上一条机器人消息作为上下文
        for turn in dialogue:
            if turn.get('speaker') == 'agent':
                previous_bot_text = turn.get('text', '')
                continue
            elif turn.get('speaker') == 'customer':
                text = turn.get('text', '')
                labeled_intent = turn.get('user_intent', 'unknown')
                if not labeled_intent or labeled_intent == 'unknown' or labeled_intent == '':
                    continue

                # 先纠正ASR错误
                corrected_text = asr_corrector.correct(text)

                # 先禁用ML，获取规则系统的结果
                if args.use_ml:
                    IntentDetector.enable_ml_fallback(False)
                    rule_result = intent_detector.detect(corrected_text, context=previous_bot_text)

                    # 再启用ML，获取混合结果
                    IntentDetector.enable_ml_fallback(True)
                    detected_intent = intent_detector.detect(corrected_text, context=previous_bot_text)

                    # 统计ML的帮助
                    if rule_result != labeled_intent and detected_intent == labeled_intent:
                        ml_helped += 1
                else:
                    detected_intent = intent_detector.detect(corrected_text, context=previous_bot_text)

                total += 1
                if detected_intent == labeled_intent:
                    correct += 1
                else:
                    errors.append({
                        'file': file_path.name,
                        'text': text,
                        'corrected_text': corrected_text,
                        'labeled': labeled_intent,
                        'detected': detected_intent,
                        'rule_result': rule_result if args.use_ml else None
                    })

    print(f"总测试样本数: {total}")
    print(f"正确识别数: {correct}")
    print(f"准确率: {correct/total*100:.2f}%")

    if args.use_ml and IntentDetector._ml_classifier is not None:
        print(f"\nML分类器效果:")
        print(f"ML成功纠正规则系统错误: {ml_helped} 个")
        print(f"ML贡献准确率提升: {ml_helped/total*100:.2f}%")
    print(f"\n错误样本 ({len(errors)} 个):")
    for i, error in enumerate(errors[:20], 1):  # 只显示前20个错误
        print(f"\n{i}. 文件: {error['file']}")
        print(f"   原文: {error['text']}")
        print(f"   纠正后: {error['corrected_text']}")
        print(f"   标注意图: {error['labeled']}")
        print(f"   识别意图: {error['detected']}")

    # 统计错误类型分布
    print(f"\n\n错误类型分布:")
    error_dist = {}
    for error in errors:
        key = f"{error['labeled']} → {error['detected']}"
        error_dist[key] = error_dist.get(key, 0) + 1

    for key, count in sorted(error_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"{key}: {count} 次")

if __name__ == "__main__":
    main()
