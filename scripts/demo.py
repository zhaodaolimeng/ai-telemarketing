#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
催收机器人交互Demo
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.chatbot import CollectionChatBot, ChatState

async def main():
    print("=" * 60)
    print("🤖 印尼语智能催收机器人 Demo")
    print("=" * 60)
    print("📝 说明：")
    print("  - 输入印尼语句子和机器人对话")
    print("  - 输入 'quit' 或 'exit' 退出Demo")
    print("  - 测试场景：身份确认、还款询问、展期请求、异议处理等")
    print("=" * 60)

    # 初始化机器人（H2阶段，逾期5天，欠款500k印尼盾）
    bot = CollectionChatBot(chat_group="H2", overdue_amount=500000, overdue_days=5)

    # 机器人首先发起对话
    first_response, _ = await bot.process()
    print(f"\n🤖 机器人: {first_response}")

    while True:
        user_input = input("\n👤 用户: ").strip()

        if user_input.lower() in ["quit", "exit", "退出"]:
            print("\n👋 再见！")
            break

        if not user_input:
            print("⚠️ 请输入内容")
            continue

        # 处理用户输入
        response, _ = await bot.process(user_input)
        print(f"🤖 机器人: {response}")

        # 如果对话结束，询问是否重新开始
        if bot.state in [ChatState.CLOSE, ChatState.FAILED]:
            restart = input("\n🔄 对话结束，是否重新开始？(y/n): ").strip().lower()
            if restart == "y":
                bot = CollectionChatBot(chat_group="H2", overdue_amount=500000, overdue_days=5)
                first_response, _ = await bot.process()
                print(f"\n🤖 机器人: {first_response}")
            else:
                print("\n👋 再见！")
                break

if __name__ == "__main__":
    asyncio.run(main())
