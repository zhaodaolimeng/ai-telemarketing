#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Fallback 功能测试脚本
覆盖场景：正常流程、unknown 触发、时间检测切回、超时降级、不可用降级、合规过滤
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, ChatState
from core.llm_config import LLMConfig


def print_sep(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


async def test_1_normal_rule_flow():
    """场景 1: 正常规则流程不受 LLM fallback 影响"""
    print_sep("场景 1: 正常规则流程")
    bot = CollectionChatBot("H2", "Pak Budi")
    bot.enable_llm_fallback()  # mock 模式

    responses = ["Halo", "Iya", "Oh ya", "Jam 5", "Iya"]
    resp_idx = 0

    agent_says, _ = await bot.process()
    print(f"  AGENT: {agent_says}")

    while not bot.is_finished() and resp_idx < len(responses):
        customer = responses[resp_idx]
        resp_idx += 1
        print(f"  CUSTOMER: {customer}")
        agent_says, _ = await bot.process(customer)
        if agent_says:
            tag = " [LLM]" if bot.llm_used_this_turn else ""
            print(f"  AGENT: {agent_says}{tag}")

    assert bot.is_successful(), "应该成功获取还款时间"
    assert not any(turn for turn in bot.conversation if hasattr(turn, 'is_llm_fallback')), \
        "正常流程不应触发 LLM"
    print(f"  ✓ 通过: 成功={bot.is_successful()}, commit_time={bot.commit_time}")


async def test_2_unknown_triggers_llm():
    """场景 2: 连续 unknown 触发 LLM fallback"""
    print_sep("场景 2: 连续 unknown 触发 LLM fallback")
    bot = CollectionChatBot("H2", "Pak Andi")
    bot.enable_llm_fallback()

    # 客户回复难以理解的内容
    responses = ["Halo", "iya...", "mmm gak tau", "entah lah pokoknya susah"]
    resp_idx = 0

    agent_says, _ = await bot.process()
    print(f"  AGENT: {agent_says}")

    llm_triggered = False
    while not bot.is_finished() and resp_idx < len(responses):
        customer = responses[resp_idx]
        resp_idx += 1
        print(f"  CUSTOMER: {customer}")
        agent_says, _ = await bot.process(customer)
        if agent_says:
            tag = " [LLM]" if bot.llm_used_this_turn else ""
            if bot.llm_used_this_turn:
                llm_triggered = True
            print(f"  AGENT: {agent_says}{tag}")

    assert llm_triggered, "连续 unknown 应触发 LLM fallback"
    print(f"  ✓ 通过: LLM fallback 已触发")


async def test_3_llm_detects_time():
    """场景 3: LLM 获取到时间后切回规则机"""
    print_sep("场景 3: LLM 获取到时间后切回规则机")
    bot = CollectionChatBot("S0", "Pak Candra")
    bot.enable_llm_fallback()

    responses = ["Halo", "iya", "saya lagi susah, belum punya uang, anak sakit",
                 "iya deh, nanti jam 4 saya coba bayar"]
    resp_idx = 0

    agent_says, _ = await bot.process()
    print(f"  AGENT: {agent_says}")

    llm_used = False
    while not bot.is_finished() and resp_idx < len(responses):
        customer = responses[resp_idx]
        resp_idx += 1
        print(f"  CUSTOMER: {customer}")
        agent_says, _ = await bot.process(customer)
        if agent_says:
            tag = " [LLM]" if bot.llm_used_this_turn else ""
            if bot.llm_used_this_turn:
                llm_used = True
            print(f"  AGENT: {agent_says}{tag}")

    assert llm_used, "应该触发过 LLM"
    print(f"  ✓ 通过: LLM 已触发, commit_time={bot.commit_time}, success={bot.is_successful()}")


async def test_4_llm_unavailable_degradation():
    """场景 4: LLM 不可用时的降级"""
    print_sep("场景 4: LLM 不可用降级")
    bot = CollectionChatBot("H2", "Pak Degradasi")
    # 使用 mock 但手动禁用 provider 模拟不可用
    bot.enable_llm_fallback()
    bot.llm_provider = None  # 模拟 LLM 不可用

    responses = ["Halo", "iya", "gak ngerti", "apa ya", "jam 5"]
    resp_idx = 0

    agent_says, _ = await bot.process()
    print(f"  AGENT: {agent_says}")

    while not bot.is_finished() and resp_idx < len(responses):
        customer = responses[resp_idx]
        resp_idx += 1
        print(f"  CUSTOMER: {customer}")
        agent_says, _ = await bot.process(customer)
        if agent_says:
            tag = " [LLM]" if bot.llm_used_this_turn else ""
            print(f"  AGENT: {agent_says}{tag}")

    # 即使 LLM 不可用，对话也不应崩溃
    print(f"  ✓ 通过: 对话未崩溃, state={bot.state.name}, finished={bot.is_finished()}")


async def test_5_compliance_filter_blocks_output():
    """场景 5: 合规过滤测试"""
    print_sep("场景 5: 合规后置过滤")
    from core.compliance_checker import get_compliance_checker

    checker = get_compliance_checker()

    # 测试高风险内容被过滤
    bad_text = "Anjing! Kamu harus bayar sekarang atau saya akan datang ke rumah kamu!"
    filtered, violations = checker.post_filter(bad_text)
    assert filtered is None, "高风险内容应返回 None"
    print(f"  ✓ 高风险过滤: violations={[v['rule_id'] for v in violations]}")

    # 测试正常内容通过
    good_text = "Baik Pak, terima kasih. Kapan kira-kira Anda bisa melakukan pembayaran?"
    filtered, violations = checker.post_filter(good_text)
    assert filtered is not None, "正常内容应通过"
    print(f"  ✓ 正常内容通过: '{filtered[:50]}...'")

    # 测试中风险内容（记录但放行）
    medium_text = "Kenapa tidak jawab telepon malam hari? Saya akan telepon kamu lagi nanti."
    filtered, violations = checker.post_filter(medium_text)
    assert filtered is not None, "中风险内容应放行"
    print(f"  ✓ 中风险放行: violations={[v['rule_id'] for v in violations]} (allowed)")


async def test_6_mock_mode_full_chain():
    """场景 6: Mock 模式全链路"""
    print_sep("场景 6: Mock 模式完整链路验证")
    config = LLMConfig.from_env()
    assert config.is_mock, "默认应为 mock 模式"
    print(f"  ✓ Provider: {config.provider}")

    bot = CollectionChatBot("H1", "Pak Test")
    success = bot.enable_llm_fallback()
    assert success, "LLM fallback 应成功启用"
    assert bot.llm_enabled, "llm_enabled 应为 True"
    assert bot.fallback_detector is not None, "fallback_detector 不应为 None"
    assert bot.llm_provider is not None, "llm_provider 不应为 None"
    print(f"  ✓ LLM Fallback 启用成功")


async def test_7_llm_disabled_by_default():
    """场景 7: LLM fallback 默认不启用，不影响现有功能"""
    print_sep("场景 7: LLM 默认不启用")
    bot = CollectionChatBot("H2", "Pak Default")
    assert not bot.llm_enabled, "默认不应启用 LLM"
    assert bot.fallback_detector is None, "fallback_detector 应为 None"

    # 正常对话流程不受影响
    responses = ["Halo", "Iya", "Oh ya", "Jam 5", "Iya"]
    resp_idx = 0

    agent_says, _ = await bot.process()
    while not bot.is_finished() and resp_idx < len(responses):
        agent_says, _ = await bot.process(responses[resp_idx])
        resp_idx += 1

    assert bot.is_successful(), "未启用 LLM 时正常流程应成功"
    print(f"  ✓ 通过: 默认不启用, 正常流程不受影响")


async def main():
    print("LLM Fallback 功能测试")
    print("=" * 60)

    tests = [
        test_1_normal_rule_flow,
        test_2_unknown_triggers_llm,
        test_3_llm_detects_time,
        test_4_llm_unavailable_degradation,
        test_5_compliance_filter_blocks_output,
        test_6_mock_mode_full_chain,
        test_7_llm_disabled_by_default,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"结果: {passed} 通过, {failed} 失败 (共 {len(tests)} 项)")
    print('='*60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
