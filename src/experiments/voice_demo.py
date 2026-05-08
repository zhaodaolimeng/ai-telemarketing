#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音催收对话 Demo
使用麦克风进行实时语音对话

Usage:
    python src/experiments/voice_demo.py                    # 默认H1催收
    python src/experiments/voice_demo.py --group H2         # H2宽限期提醒
    python src/experiments/voice_demo.py --group S0         # S0逾期催收
    python src/experiments/voice_demo.py --group H1 --asr-model tiny  # 使用小模型
"""
import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.chatbot import CollectionChatBot, ChatState
from src.core.voice.conversation import VoiceConversation, ConversationState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voice_demo")


async def main():
    parser = argparse.ArgumentParser(description="语音催收对话 Demo")
    parser.add_argument("--group", default="H1", choices=["H2", "H1", "S0"],
                        help="催收阶段 (default: H1)")
    parser.add_argument("--name", default="Budi", help="客户名称")
    parser.add_argument("--asr-model", default="small", choices=["tiny", "small", "medium"],
                        help="ASR模型大小 (default: small)")
    parser.add_argument("--silence", type=float, default=1.0,
                        help="静音判定时长(秒) (default: 1.0)")
    parser.add_argument("--energy", type=float, default=0.01,
                        help="语音能量阈值 (default: 0.01)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  语音催收对话 Demo")
    print(f"  催收阶段: {args.group}  客户: {args.name}")
    print(f"  ASR模型: faster-whisper {args.asr_model}")
    print(f"  静音阈值: {args.silence}s  能量阈值: {args.energy}")
    print("=" * 60)
    print()
    print("  启动中...")
    print()

    bot = CollectionChatBot(
        chat_group=args.group,
        customer_name=args.name,
    )

    conv = VoiceConversation(
        chatbot=bot,
        asr_model_size=args.asr_model,
        silence_duration=args.silence,
        energy_threshold=args.energy,
    )

    conv.on_agent_response = lambda text: print(f"\n  AGENT: {text}\n")
    conv.on_asr_result = lambda text: print(f"  [ASR]: {text}")
    conv.on_state_change = lambda old, new: logger.debug(f"State: {old} → {new}")

    # 处理 Ctrl+C
    loop = asyncio.get_event_loop()

    def shutdown():
        print("\n  正在停止...")
        asyncio.ensure_future(conv.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: shutdown())

    try:
        await conv.start()
        print("  语音对话已启动，请说话...")
        print("  (按 Ctrl+C 停止)\n")

        # 先让机器人打招呼
        first_msg, _ = await bot.process(use_tts=False)
        if first_msg:
            print(f"  AGENT: {first_msg}\n")
            tts_result = await conv._tts.synthesize(first_msg)
            if tts_result.success and tts_result.audio_data is not None:
                conv._audio_out.play_array(tts_result.audio_data, blocking=True)

        # 进入对话循环
        while bot.state not in (ChatState.CLOSE, ChatState.FAILED):
            turn = await conv.run_once()
            if turn is None:
                continue
            if bot.state in (ChatState.CLOSE, ChatState.FAILED):
                break
            await asyncio.sleep(0.5)

    finally:
        await conv.stop()

    print(f"\n  对话结束，最终状态: {bot.state.name}")
    if bot.commit_time:
        print(f"  承诺还款时间: {bot.commit_time}")
    print(f"  对话轮数: {len(bot.conversation)}")


if __name__ == "__main__":
    asyncio.run(main())
