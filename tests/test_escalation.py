"""P15-B02: 承诺违约升级链单元测试"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.chatbot import CollectionChatBot, ChatState
from core.strategy_profile import StrategyProfile


def make_escalation_strategy(**overrides) -> StrategyProfile:
    """构造用于测试升级链的策略"""
    defaults = dict(
        segment_key="test", segment_name="test",
        approach="firm", tone="firm", push_intensity=3,
        max_objections=10, extension_fee_ratio=0.2,
        extension_priority=False, partial_payment_offered=False,
        max_push_rounds=3, consequence_emphasis=3,
        education_emphasis=False, relationship_emphasis=False,
        fallback_approach="",
    )
    defaults.update(overrides)
    return StrategyProfile(**defaults)


# ── push_round 计数器测试 ────────────────────────────────────────────

def test_push_round_starts_zero():
    bot = CollectionChatBot(chat_group="H2")
    assert bot.push_round == 0


def test_push_round_resets():
    bot = CollectionChatBot(chat_group="H2")
    bot.push_round = 3
    bot.reset()
    assert bot.push_round == 0


# ── 话术存在性测试 ──────────────────────────────────────────────────

def test_push_final_script_exists():
    bot = CollectionChatBot(chat_group="S0")
    script = bot._get_script("push_final")
    assert len(script) > 20


def test_escalate_to_supervisor_script_exists():
    bot = CollectionChatBot(chat_group="S0")
    script = bot._get_script("escalate_to_supervisor")
    assert len(script) > 20
    assert "supervisor" in script.lower() or "senior" in script.lower()


# ── 升级链集成测试（通过 process 模拟） ─────────────────────────────
# "iya" → confirm_identity intent, 不在 PUSH_FOR_TIME 的特定 intent
# 处理分支中，因此会落入 else 分支触发升级链

@pytest.mark.asyncio
async def test_push_round_increments_on_dodge():
    """用户推脱时 push_round 递增"""
    strat = make_escalation_strategy(max_push_rounds=3)
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    # "iya" → confirm_identity intent → else 分支
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.push_round == 1
    assert bot.state == ChatState.PUSH_FOR_TIME

    await bot.process(customer_input="iya", use_tts=False)
    assert bot.push_round == 2


@pytest.mark.asyncio
async def test_escalation_scripts_progressive():
    """验证 push_round 递进时使用不同级别话术"""
    strat = make_escalation_strategy(max_push_rounds=3)
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    # Round 1: push
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.push_round == 1

    # Round 2: push_hard
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.push_round == 2

    # Round 3: push_final
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.push_round == 3


@pytest.mark.asyncio
async def test_fallback_offer_extension():
    """push 耗尽时激活 offer_extension fallback"""
    strat = make_escalation_strategy(max_push_rounds=1, fallback_approach="offer_extension")
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    # Round 1: push (push_round = 0 → 1)
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.push_round == 1

    # Round 2: push_round(1) >= max_push_rounds(1) → fallback
    resp, _ = await bot.process(customer_input="iya", use_tts=False)
    assert bot.extension_discussed is True
    assert bot.state == ChatState.CONFIRM_EXTENSION
    assert "perpanjangan" in resp.lower()


@pytest.mark.asyncio
async def test_fallback_escalate_to_supervisor():
    """push 耗尽时 activate escalate fallback → FAILED"""
    strat = make_escalation_strategy(max_push_rounds=1, fallback_approach="escalate")
    bot = CollectionChatBot(chat_group="S0", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    await bot.process(customer_input="iya", use_tts=False)
    resp, _ = await bot.process(customer_input="iya", use_tts=False)

    assert "supervisor" in resp.lower() or "senior" in resp.lower()
    assert bot.state == ChatState.FAILED


@pytest.mark.asyncio
async def test_fallback_callback_later():
    """push 耗尽时 activate callback_later fallback → CLOSE"""
    strat = make_escalation_strategy(max_push_rounds=1, fallback_approach="callback_later")
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    await bot.process(customer_input="iya", use_tts=False)
    resp, _ = await bot.process(customer_input="iya", use_tts=False)

    assert bot.state == ChatState.CLOSE
    assert "hubungi" in resp.lower() or "telepon" in resp.lower()


@pytest.mark.asyncio
async def test_fallback_empty_goes_to_failed():
    """无 fallback 时保持原有 FAILED 行为"""
    strat = make_escalation_strategy(max_push_rounds=1, fallback_approach="")
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    await bot.process(customer_input="iya", use_tts=False)
    resp, _ = await bot.process(customer_input="iya", use_tts=False)

    assert bot.state == ChatState.FAILED
    assert resp == ""


@pytest.mark.asyncio
async def test_objection_count_safety_valve():
    """objection_count 先于 push_round 耗尽 → 直接 FAILED"""
    strat = make_escalation_strategy(max_push_rounds=10, max_objections=2)
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)

    await bot.process(use_tts=False)
    bot.state = ChatState.PUSH_FOR_TIME
    bot.conversation.append(type('Turn', (), {'agent': 'Kapan?', 'customer': ''})())

    # objection_count 从 0 开始，每次 else 分支都 +1
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.objection_count == 1
    await bot.process(customer_input="iya", use_tts=False)
    assert bot.objection_count == 2

    # 第三次: objection_count >= max_objections → FAILED
    resp, _ = await bot.process(customer_input="iya", use_tts=False)
    assert bot.state == ChatState.FAILED
    assert resp == ""
