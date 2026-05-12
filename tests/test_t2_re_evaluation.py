"""P15-H04: T2 会话中策略再评估单元测试"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.chatbot import CollectionChatBot, ChatState
from core.strategy_profile import StrategyProfile


def make_strategy(**overrides) -> StrategyProfile:
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


# ── ASK_TIME 边界测试 ──────────────────────────────────────────────────

def test_re_evaluate_extends_max_objections_on_cooperation():
    """用户有合作信号 → 放宽 objection 阈值"""
    bot = CollectionChatBot(chat_group="H2")
    bot.objection_count = 2
    bot.max_objections = 3
    bot.user_history_intents = ["agree_to_pay", "no_money", "confirm_time"]
    bot._re_evaluate_strategy("ask_time")
    assert bot.max_objections == 4
    assert bot.strategy.max_objections == 4


def test_re_evaluate_no_change_without_signal():
    """无合作信号 → 不调整"""
    bot = CollectionChatBot(chat_group="H2")
    bot.objection_count = 2
    bot.max_objections = 3
    bot.user_history_intents = ["unknown", "silence", "dont_know"]
    bot._re_evaluate_strategy("ask_time")
    assert bot.max_objections == 3


def test_re_evaluate_hostile_user_ask_time():
    """敌对用户不应放宽"""
    bot = CollectionChatBot(chat_group="S0")
    bot.objection_count = 2
    bot.max_objections = 3
    bot.user_history_intents = ["refuse_to_pay", "threaten"]
    bot._re_evaluate_strategy("ask_time")
    assert bot.max_objections == 3


def test_re_evaluate_repeated_no_money_enables_extension():
    """反复 no_money → extension_priority = True"""
    bot = CollectionChatBot(chat_group="H2")
    bot.no_money_count = 2
    bot.strategy.extension_priority = False
    bot._re_evaluate_strategy("ask_time")
    assert bot.strategy.extension_priority is True


# ── PUSH_FOR_TIME 边界测试 ─────────────────────────────────────────────

def test_re_evaluate_flips_fallback_on_partial_payment():
    """用户提过部分还款 → fallback 切换为 partial_payment"""
    bot = CollectionChatBot(chat_group="S0")
    bot.push_round = 2
    bot.strategy.max_push_rounds = 3
    bot.strategy.fallback_approach = "escalate"
    bot.partial_payment_discussed = True
    bot._re_evaluate_strategy("push_for_time")
    assert bot.strategy.fallback_approach == "partial_payment"


def test_re_evaluate_offers_extension_when_not_discussed():
    """用户从未被提供展期 → fallback 切换为 offer_extension"""
    bot = CollectionChatBot(chat_group="S0")
    bot.push_round = 2
    bot.strategy.max_push_rounds = 3
    bot.strategy.fallback_approach = ""
    bot.extension_discussed = False
    bot._re_evaluate_strategy("push_for_time")
    assert bot.strategy.fallback_approach == "offer_extension"


def test_re_evaluate_extends_push_rounds_for_engaged_user():
    """用户在参与且合作 → 多给 push 机会"""
    bot = CollectionChatBot(chat_group="H2")
    bot.push_round = 2
    bot.strategy.max_push_rounds = 3
    bot.user_history_intents = ["agree_to_pay", "confirm_time"]
    bot.conversation = [type('T', (), {})() for _ in range(6)]
    bot._re_evaluate_strategy("push_for_time")
    assert bot.strategy.max_push_rounds == 4


def test_re_evaluate_hardship_no_hostility_flips_fallback():
    """困难信号 + 非敌对 → fallback 切换为 partial_payment"""
    bot = CollectionChatBot(chat_group="H2")
    bot.push_round = 2
    bot.strategy.max_push_rounds = 3
    bot.strategy.fallback_approach = "escalate"
    bot.user_history_intents = ["no_money", "complain_high_interest"]
    bot._re_evaluate_strategy("push_for_time")
    assert bot.strategy.fallback_approach == "partial_payment"


def test_re_evaluate_hostile_user_push_time():
    """敌对用户 push_for_time 不调整"""
    bot = CollectionChatBot(chat_group="S0")
    bot.push_round = 2
    bot.strategy.max_push_rounds = 3
    bot.strategy.fallback_approach = "escalate"
    bot.user_history_intents = ["refuse_to_pay", "threaten"]
    bot.extension_discussed = False
    bot._re_evaluate_strategy("push_for_time")
    # 敌对用户不应切换为 offer_extension
    assert bot.strategy.fallback_approach == "escalate"
    assert bot.strategy.max_push_rounds == 3


# ── 集成测试：_re_evaluate_strategy 在 process 中被调用 ─────────────────

@pytest.mark.asyncio
async def test_re_evaluate_called_at_ask_time_boundary():
    """验证 ASK_TIME 边界处 _re_evaluate_strategy 被触发"""
    from core.strategy_profile import get_strategy_profile

    strat = get_strategy_profile(0, "H2")
    bot = CollectionChatBot(chat_group="H2", strategy_profile=strat)
    await bot.process(use_tts=False)

    # 状态切换到 ASK_TIME 并设置 near-limit objection_count
    bot.state = ChatState.ASK_TIME
    bot.objection_count = bot.max_objections - 1
    bot.user_history_intents = ["agree_to_pay", "confirm_time"]

    # "iya" → confirm_identity → else 分支 → re_evaluate 触发
    bot.conversation.append(type('Turn', (), {'agent': 'Bayar kapan?', 'customer': ''})())
    await bot.process(customer_input="iya", use_tts=False)
    # max_objections 从 3 变成 4（合作信号放宽了）
    assert bot.max_objections == 4
