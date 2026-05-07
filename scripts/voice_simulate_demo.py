#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客户语音模拟 Demo
用TTS生成印尼语客户语音，注入ASR管线，端到端测试催收对话

Usage:
    python scripts/voice_simulate_demo.py                                    # 默认: cooperative, medium, H2
    python scripts/voice_simulate_demo.py --persona resistant --resistance high
    python scripts/voice_simulate_demo.py --chat-group S0 --max-turns 10
    python scripts/voice_simulate_demo.py --persona excuse_master --realtime
    python scripts/voice_simulate_demo.py --persona silent --max-turns 5 --no-save
"""
import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.chatbot import CollectionChatBot, ChatState
from src.core.voice.customer_simulator import CustomerVoiceSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voice_simulate")


PERSONAS = ["cooperative", "busy", "negotiating", "silent", "forgetful", "resistant", "excuse_master"]
RESISTANCE_LEVELS = ["very_low", "low", "medium", "high", "very_high"]
CHAT_GROUPS = ["H2", "H1", "S0"]


def print_header(args):
    print()
    print("=" * 62)
    print("  客户语音模拟器 - Customer Voice Simulator")
    print("=" * 62)
    print(f"  Persona: {args.persona:<15s} Resistance: {args.resistance}")
    print(f"  Group: {args.chat_group:<5s}  Max turns: {args.max_turns}")
    print(f"  Customer voice: id-ID-GadisNeural (female)")
    print(f"  Agent voice:    id-ID-ArdiNeural (male)")
    print(f"  Mode: {'real-time' if args.realtime else 'fast-forward'}")
    print(f"  Save: {'yes' if not args.no_save else 'no'}")
    print("=" * 62)


def print_turn(turn):
    """打印单轮结果"""
    match_icon = "[MATCH]" if turn.asr_exact_match else "[DIFF]"
    print(f"\n--- Turn {turn.turn_id} ({turn.state_before} → {turn.state_after}) ---")

    if turn.tts_failed:
        print(f"  [TTS FAILED]")
    else:
        print(f"  Customer text : \"{turn.customer_text}\"")

    if turn.vad_dropped:
        print(f"  [VAD DROPPED - speech too short/quiet]")
    elif turn.asr_text:
        print(f"  ASR {match_icon}  : \"{turn.asr_text}\" (CER: {turn.asr_cer:.3f}, {turn.asr_time:.2f}s)")

    if turn.agent_text:
        preview = turn.agent_text[:120] + ("..." if len(turn.agent_text) > 120 else "")
        print(f"  Agent          : {preview}")

    print(f"  Timing: TTS={turn.tts_time:.2f}s ASR={turn.asr_time:.2f}s Bot={turn.chatbot_time:.2f}s")


def print_report(report):
    """打印汇总报告"""
    print()
    print("=" * 62)
    print("  Simulation Complete")
    print("=" * 62)
    print(f"  Turns: {report.total_turns}  |  Ended: {report.conversation_ended}")
    print(f"  Final state: {report.final_state}")
    if report.committed_time:
        print(f"  Committed time: {report.committed_time}")

    print(f"\n  ASR Accuracy:")
    print(f"    Exact Match Rate: {report.asr_exact_match_rate:.1%}")
    print(f"    Avg CER:          {report.avg_cer:.3f}")
    print(f"    Avg Confidence:   {report.avg_asr_confidence:.3f}")

    print(f"\n  Timing (avg):")
    print(f"    TTS:      {report.avg_tts_time:.2f}s")
    print(f"    ASR:      {report.avg_asr_time:.2f}s")
    print(f"    Chatbot:  {report.avg_chatbot_time:.2f}s")
    print(f"    Round-trip: {report.avg_round_trip_time:.2f}s")
    print(f"    Wall clock:  {report.total_wall_time:.0f}s")

    if report.vad_dropped_count or report.tts_failed_count:
        print(f"\n  Issues:")
        if report.vad_dropped_count:
            print(f"    VAD dropped: {report.vad_dropped_count} turns")
        if report.tts_failed_count:
            print(f"    TTS failed:  {report.tts_failed_count} turns")

    if report.artifacts_dir:
        print(f"\n  Artifacts: {report.artifacts_dir}")

    print("=" * 62)
    print()


async def main():
    parser = argparse.ArgumentParser(
        description="客户语音模拟器 - 端到端测试催收语音对话",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                                # 默认参数
  %(prog)s --persona resistant --resistance high           # 高抗拒客户
  %(prog)s --chat-group S0 --persona excuse_master         # S0逾期+借口型客户
  %(prog)s --realtime --persona negotiating                # 实时模式
  %(prog)s --persona silent --max-turns 5 --no-save        # 仅终端输出
  %(prog)s --asr-model tiny --persona cooperative          # 快速小模型测试
        """,
    )
    parser.add_argument("--persona", default="cooperative", choices=PERSONAS,
                        help="客户画像类型 (default: cooperative)")
    parser.add_argument("--resistance", default="medium", choices=RESISTANCE_LEVELS,
                        help="抗拒等级 (default: medium)")
    parser.add_argument("--chat-group", default="H2", choices=CHAT_GROUPS,
                        help="催收阶段 (default: H2)")
    parser.add_argument("--max-turns", type=int, default=20,
                        help="最大对话轮数 (default: 20)")
    parser.add_argument("--realtime", action="store_true",
                        help="模拟真实对话节奏(等待音频时长)")
    parser.add_argument("--no-save", action="store_true",
                        help="不保存音频和报告文件")
    parser.add_argument("--asr-model", default="small",
                        choices=["tiny", "small", "medium"],
                        help="ASR模型大小 (default: small)")
    parser.add_argument("--output-dir", default="data/voice_simulations",
                        help="输出目录 (default: data/voice_simulations)")
    parser.add_argument("--customer-name", default="Budi",
                        help="客户名称 (default: Budi)")
    parser.add_argument("--seed", type=int, help="随机种子")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细日志")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.seed:
        import random
        random.seed(args.seed)

    print_header(args)
    print("  启动中...")

    # 创建 Chatbot
    bot = CollectionChatBot(
        chat_group=args.chat_group,
        customer_name=args.customer_name,
    )

    # 创建语音模拟器
    print("  加载 ASR 模型...")
    sim = await CustomerVoiceSimulator.create(
        chatbot=bot,
        persona=args.persona,
        resistance_level=args.resistance,
        chat_group=args.chat_group,
        customer_name=args.customer_name,
        asr_model_size=args.asr_model,
        realtime=args.realtime,
        save_artifacts=not args.no_save,
        output_dir=args.output_dir,
    )

    if not sim._asr.is_available:
        print("  [ERROR] ASR 模型加载失败，请检查 faster-whisper 安装")
        return 1

    print(f"  就绪。开始模拟对话...")
    print()

    # Ctrl+C 处理
    loop = asyncio.get_event_loop()
    shutdown_flag = False

    def shutdown():
        nonlocal shutdown_flag
        shutdown_flag = True
        print("\n  用户中断...")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: shutdown())

    # 运行
    try:
        # 用 callback 打印每轮结果
        original_run_single = sim._run_single_turn

        async def patched_run_single(turn_id):
            turn = await original_run_single(turn_id)
            if turn:
                print_turn(turn)
            return turn

        sim._run_single_turn = patched_run_single

        report = await sim.run(max_turns=args.max_turns)
        print_report(report)

    except asyncio.CancelledError:
        print("\n  模拟已取消")
    except Exception as e:
        logger.error(f"模拟异常: {e}", exc_info=args.verbose)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
