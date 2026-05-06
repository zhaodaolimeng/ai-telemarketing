#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试机器人demo功能，验证核心逻辑是否正常
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
from core.chatbot import CollectionChatBot

async def test_scenario(scenario_name, user_inputs):
    """测试特定场景"""
    print(f"\n{'='*60}")
    print(f"🎯 测试场景: {scenario_name}")
    print(f"{'='*60}")

    bot = CollectionChatBot(
        chat_group="H2",
        overdue_amount=500000,
        overdue_days=5,
        customer_name="Bapak Joko"
    )

    # 获取开场白
    response, _ = await bot.process()
    print(f"🤖 机器人: {response}")

    # 模拟用户输入
    for i, user_input in enumerate(user_inputs, 1):
        print(f"👤 用户: {user_input}")
        response, _ = await bot.process(user_input)
        print(f"🤖 机器人: {response}")

        if bot.is_finished():
            print(f"\n✅ 对话结束，结果: {'成功' if bot.is_successful() else '失败'}")
            if bot.commit_time:
                print(f"⏰ 约定还款时间: {bot.commit_time}")
            break

async def main():
    print("🤖 印尼语智能催收机器人功能测试\n")

    # 测试场景1：用户配合，直接确认身份并给出还款时间
    await test_scenario(
        "用户配合场景",
        ["Ya, ini saya.", "Saya bayar jam 3 sore ya."]
    )

    # 测试场景2：用户说现在忙
    await test_scenario(
        "用户忙场景",
        ["Ya, tapi saya sedang sibuk sekarang."]
    )

    # 测试场景3：用户否认身份（打错电话）
    await test_scenario(
        "用户否认身份场景",
        ["Bukan, Anda salah nomor."]
    )

    # 测试场景4：用户威胁要投诉到OJK
    await test_scenario(
        "用户威胁投诉场景",
        ["Ya, tapi kalau Anda terus telepon saya akan laporkan ke OJK!"]
    )

    # 测试场景5：用户询问是否可以展期
    await test_scenario(
        "用户询问展期场景",
        ["Ya, bisa nggak saya perpanjang masa pembayaran?", "Ya, saya setuju.", "Saya bayar besok jam 2 ya."]
    )

    # 测试场景6：用户询问欠款金额
    await test_scenario(
        "用户询问金额场景",
        ["Ya, berapa total tagihan saya?", "Saya bayar hari ini jam 4 ya."]
    )

    # 测试场景7：用户说现在没钱
    await test_scenario(
        "用户没钱场景",
        ["Ya, tapi saya tidak punya uang sekarang.", "Saya bisa bayar 300k dulu hari ini, sisanya besok."]
    )

    # 测试场景8：用户明确拒绝还款
    await test_scenario(
        "用户拒绝还款场景",
        ["Saya tidak mau bayar!"]
    )

    # 测试场景9：用户使用口语化时间
    await test_scenario(
        "口语化时间识别场景",
        ["Ya", "Nanti sore jam 5 ya saya transfer."]
    )

    # 测试场景10：用户给出模糊时间，被催促后给出明确时间
    await test_scenario(
        "模糊时间处理场景",
        ["Ya", "Nanti aja ya.", "Besok jam 3 ya."]
    )

if __name__ == "__main__":
    asyncio.run(main())
