#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge-TTS 语音合成测试
验证印尼语语音合成功能
"""
import asyncio
import edge_tts
from pathlib import Path
import sys


async def list_indonesian_voices():
    """列出所有印尼语可用的语音"""
    print("正在获取可用语音列表...")
    voices = await edge_tts.list_voices()

    indonesian_voices = [v for v in voices if v["Locale"] in ["id-ID", "id"]]
    print(f"\n找到 {len(indonesian_voices)} 个印尼语语音:")
    for v in indonesian_voices:
        print(f"  - {v['ShortName']} ({v['Gender']})")

    return indonesian_voices


async def text_to_speech(text: str, voice: str = "id-ID-ArdiNeural", output_file: str = "output.mp3"):
    """文本转语音"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return output_file


async def test_collection_scripts():
    """测试催收话术的语音合成"""
    # 测试用的催收话术（来自话术库）
    test_scripts = [
        "Halo?",
        "Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra.",
        "Untuk pinjaman ya Pak/Bu.",
        "Kapan bisa bayar Pak/Bu?",
        "Oke, jam 5 ya Pak/Bu.",
        "Ya, ya, ya.",
        "Saya tunggu ya. Terima kasih.",
        "Jam berapa tepatnya?",
        "Besok jam 2 ya?",
        "Saya tunggu jam 5."
    ]

    voice = "id-ID-ArdiNeural"
    output_dir = Path("data/tts_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n开始测试语音合成，使用语音: {voice}")
    print(f"输出目录: {output_dir.absolute()}")

    for i, script in enumerate(test_scripts, 1):
        output_file = output_dir / f"test_{i:02d}.mp3"
        print(f"\n[{i}/{len(test_scripts)}] 正在合成: {script}")

        try:
            await text_to_speech(script, voice, str(output_file))
            print(f"    ✓ 已保存: {output_file}")
        except Exception as e:
            print(f"    ✗ 失败: {e}")

    # 测试长文本
    long_text = "Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra. Untuk pinjaman ya Pak/Bu. Kapan bisa bayar Pak/Bu? Oke, jam 5 ya Pak/Bu. Ya, ya, ya. Saya tunggu ya. Terima kasih."
    output_file = output_dir / "full_conversation.mp3"
    print(f"\n测试完整对话: {long_text}")
    await text_to_speech(long_text, voice, str(output_file))
    print(f"✓ 已保存: {output_file}")


async def test_with_chatbot():
    """结合对话机器人测试TTS"""
    from collection_chatbot_v2 import CollectionChatBot

    print("\n" + "="*70)
    print("测试对话机器人 + TTS")
    print("="*70)

    bot = CollectionChatBot("H2")
    output_dir = Path("data/chatbot_tts")
    output_dir.mkdir(parents=True, exist_ok=True)
    voice = "id-ID-ArdiNeural"

    # 运行对话
    print("\n机器人发言:")
    responses = []

    # 第一轮
    resp1 = bot.process()
    print(f"AGENT: {resp1}")
    responses.append(resp1)

    # 第二轮
    resp2 = bot.process("Halo.")
    print(f"AGENT: {resp2}")
    responses.append(resp2)

    # 第三轮
    resp3 = bot.process("Ya.")
    print(f"AGENT: {resp3}")
    responses.append(resp3)

    # 第四轮
    resp4 = bot.process("Oh ya.")
    print(f"AGENT: {resp4}")
    responses.append(resp4)

    # 第五轮
    resp5 = bot.process("Jam 5.")
    print(f"AGENT: {resp5}")
    responses.append(resp5)

    # 第六轮
    resp6 = bot.process("Iya.")
    print(f"AGENT: {resp6}")
    responses.append(resp6)

    # 第七轮
    resp7 = bot.process("Iya.")
    print(f"AGENT: {resp7}")
    responses.append(resp7)

    # 合成每个回复
    print(f"\n正在合成 {len(responses)} 个回复...")
    for i, resp in enumerate(responses, 1):
        if resp:
            output_file = output_dir / f"bot_response_{i:02d}.mp3"
            await text_to_speech(resp, voice, str(output_file))
            print(f"  [{i}] {resp} -> {output_file.name}")

    # 合成完整对话
    full_text = " ".join([r for r in responses if r])
    output_file = output_dir / "bot_full_conversation.mp3"
    await text_to_speech(full_text, voice, str(output_file))
    print(f"\n完整对话已保存: {output_file}")


async def main():
    print("="*70)
    print("Edge-TTS 印尼语语音合成测试")
    print("="*70)

    # 1. 列出可用语音
    voices = await list_indonesian_voices()

    if not voices:
        print("\n警告: 未找到印尼语语音，将尝试使用默认语音")

    # 2. 测试催收话术
    await test_collection_scripts()

    # 3. 结合对话机器人测试
    try:
        await test_with_chatbot()
    except Exception as e:
        print(f"\n对话机器人测试跳过: {e}")

    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)
    print("\n请检查以下目录的音频文件:")
    print(f"  - data/tts_test/")
    print(f"  - data/chatbot_tts/")


if __name__ == "__main__":
    # 确保输出编码正确
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    asyncio.run(main())
