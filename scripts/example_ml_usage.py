#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML意图分类器使用示例
"""
import sys
sys.path.insert(0, 'src')
from core.chatbot import CollectionChatBot, IntentDetector
from core.simple_classifier import SimpleIntentClassifier

print("=== 简易意图分类器使用示例 ===\n")

# 方式1：直接使用独立的ML分类器
print("1. 独立使用ML分类器:")
try:
    classifier = SimpleIntentClassifier.load_model('models/simple_intent_classifier.pkl')

    test_utterances = [
        "Saya tidak ada uang sekarang, mau bayar nanti ya",
        "Ini salah orang, saya tidak pernah pinjam",
        "Transfer ke rekening mana ya?",
        "Saya sedang diluar, nanti bicara lagi",
        "Bisa tidak perpanjang waktu bayar?",
        "Bunganya terlalu tinggi bisa tidak kurangin?"
    ]

    for utterance in test_utterances:
        results = classifier.predict(utterance, top_k=2)
        print(f"\n输入: {utterance}")
        for intent, prob in results:
            print(f"  {intent}: {prob:.2%}")

except Exception as e:
    print(f"ML分类器未训练或加载失败: {e}")
    print("请先运行: python src/experiments/train_classifier.py")

print("\n" + "="*50 + "\n")

# 方式2：在chatbot中集成使用
print("2. 在ChatBot中集成使用（规则+ML混合模式）:")
bot = CollectionChatBot(chat_group="H2", customer_name="Bapak Andi")

# 启用ML分类
success = bot.enable_ml_intent_classification(threshold=0.6)
if success:
    print("ML分类器已启用，将作为规则系统的fallback")
else:
    print("ML分类器不可用，将只使用规则系统")

# 测试对话
test_cases = [
    ("Halo, apakah ini Bapak Andi?", "Ya ini saya"),  # confirm_identity
    ("Tagihan Anda sebesar 500.000 sudah jatuh tempo, bisa bayar sekarang?", "Oke saya bayar nanti jam 3"),  # agree_to_pay
    ("Saya sedang tidak ada uang sekarang, bisa tidak perpanjang?", "Iya bisa"),  # 应该识别为confirm？不，这里用户是回答能不能延期，所以应该是agree_to_pay或者ask_extension？
    ("Kapan Anda bisa melakukan pembayaran?", "Besok pagi jam 9 saya transfer"),  # agree_to_pay + confirm_time
]

print("\n对话测试：")
for bot_question, user_answer in test_cases:
    bot.conversation.append(type('obj', (), {'agent': bot_question, 'customer': ''})())
    corrected = bot.asr_corrector.correct(user_answer)
    intent = bot.intent_detector.detect(corrected, context=bot_question)
    print(f"\nBot: {bot_question}")
    print(f"用户: {user_answer}")
    print(f"识别意图: {intent}")
