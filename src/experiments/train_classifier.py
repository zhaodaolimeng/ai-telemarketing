#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
训练简易意图分类器的脚本
"""
import sys
sys.path.insert(0, 'src')

from core.simple_classifier import train_and_save_model

if __name__ == "__main__":
    print("开始训练简易意图分类器...")
    print("=" * 50)
    train_and_save_model()
    print("=" * 50)
    print("训练完成！模型已保存到 models/simple_intent_classifier.pkl")
    print("\n使用方法：")
    print("1. 在chatbot中启用ML分类: bot.enable_ml_intent_classification()")
    print("2. 测试准确率: python src/tests/test_intent_accuracy.py --use-ml")
