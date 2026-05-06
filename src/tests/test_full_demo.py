#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的催收对话demo，测试ML集成后的端到端效果
"""
import sys
sys.path.insert(0, 'src')
from core.chatbot import CollectionChatBot

async def run_demo():
    print("=== 智能催收机器人完整demo ===")
    print("测试混合意图识别（规则+ML）效果\n")

    # 初始化机器人，H2组，逾期5天，500k
    bot = CollectionChatBot(
        chat_group="H2",
        customer_name="Bapak Joko",
        overdue_amount=500000,
        overdue_days=5
    )

    # 启用ML分类
    bot.enable_ml_intent_classification(threshold=0.6)
    print(f"机器人初始化完成，当前状态: {bot.state}\n")

    # 模拟对话流程
    dialogue_steps = [
        # 阶段1：问候+身份验证
        ("", None, "机器人开场白"),
        ("Ya halo saya Joko", None, "用户接电话"),
        ("Benar ini saya", None, "用户确认身份"),

        # 阶段2：告知欠款
        ("Oh ya saya ingat, tagihan berapa ya?", None, "用户询问金额"),

        # 阶段3：协商还款时间
        ("Oke saya bayar, tapi saya sedang di luar sekarang", None, "用户说在外面"),
        ("Besok pagi jam 10 saya transfer ya", None, "用户承诺明天还款"),
        ("Bisa tidak kasih waktu sampai akhir minggu? Saya lagi butuh uang", None, "用户请求延期"),

        # 阶段4：特殊情况
        ("Buktinya mana? Anda penipuan ya?", None, "用户质疑身份"),
        ("Saya tidak pernah pinjam, salah orang", None, "用户否认借款"),
        ("Saya sedang meeting, nanti saya telepon balik ya", None, "用户说忙晚点打"),
        ("Bisa kurangin bunganya tidak? Terlalu tinggi", None, "用户要求减息"),
        ("Yang punya pinjaman adalah suami saya, dia sedang keluar", None, "第三方接电话"),
    ]

    turn_count = 0
    for user_input, expected_intent, description in dialogue_steps:
        turn_count += 1
        print(f"[Turn {turn_count}] {description}")

        if not user_input:
            # 机器人主动发起对话
            response, _ = await bot.process()
            print(f"🤖 Bot: {response}")
        else:
            # 用户回复
            print(f"👤 User: {user_input}")
            response, _ = await bot.process(user_input)
            print(f"🤖 Bot: {response}")
            print(f"ℹ️  识别意图: {bot.user_intent}")
            if expected_intent:
                print(f"✅ 预期意图: {expected_intent} {'匹配' if bot.user_intent == expected_intent else '不匹配'}")

        print(f"🔄 当前状态: {bot.state}")
        print("-" * 50)

    print("\n✅ 对话demo运行完成！")
    print("\n📊 会话历史:")
    for i, turn in enumerate(bot.conversation, 1):
        if turn.agent:
            print(f"{i}. Bot: {turn.agent}")
        if turn.customer:
            print(f"   User: {turn.customer} (意图: {turn.user_intent if hasattr(turn, 'user_intent') else 'N/A'})")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_demo())
