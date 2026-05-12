"""P15-H02: LLM 策略路由器单元测试"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from core.llm_config import LLMConfig
from core.llm_strategy_router import (
    LlmStrategyRouter,
    static_fallback,
    _cache_key,
    _cache_get,
    _cache_set,
    _CACHE,
)
from core.strategy_profile import StrategyProfile


@pytest.fixture(autouse=True)
def clear_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


def make_config(**kwargs) -> LLMConfig:
    defaults = {"provider": "mock", "strategy_routing_enabled": False}
    defaults.update(kwargs)
    return LLMConfig(**defaults)


# ── JSON 解析测试 ────────────────────────────────────────────────────

def test_parse_valid_json():
    router = LlmStrategyRouter(make_config())
    raw = '{"approach":"guide","tone":"neutral","push_intensity":3,"extension_priority":false,"max_push_rounds":3,"consequence_emphasis":2,"education_emphasis":true,"relationship_emphasis":false,"avoid_tactics":[],"fallback_approach":"offer_extension"}'
    data = router._parse_response(raw)
    assert data["approach"] == "guide"
    assert data["push_intensity"] == 3
    assert data["avoid_tactics"] == []


def test_parse_markdown_wrapped_json():
    router = LlmStrategyRouter(make_config())
    raw = '```json\n{"approach":"firm","tone":"firm","push_intensity":4,"extension_priority":true,"max_push_rounds":4,"consequence_emphasis":5,"education_emphasis":false,"relationship_emphasis":false,"avoid_tactics":["shaming"],"fallback_approach":"escalate"}\n```'
    data = router._parse_response(raw)
    assert data["approach"] == "firm"
    assert data["extension_priority"] is True


def test_parse_plain_markdown_block():
    router = LlmStrategyRouter(make_config())
    raw = 'Here is the strategy:\n```\n{"approach":"educate","tone":"soft","push_intensity":2,"extension_priority":false,"max_push_rounds":2,"consequence_emphasis":1,"education_emphasis":true,"relationship_emphasis":true,"avoid_tactics":[],"fallback_approach":"callback_later"}\n```'
    data = router._parse_response(raw)
    assert data["approach"] == "educate"


def test_parse_json_with_extra_text():
    router = LlmStrategyRouter(make_config())
    raw = 'Based on the profile, the optimal strategy is:\n\n{"approach":"maintain","tone":"neutral","push_intensity":2,"extension_priority":false,"max_push_rounds":2,"consequence_emphasis":2,"education_emphasis":false,"relationship_emphasis":true,"avoid_tactics":["aggressive_push"],"fallback_approach":"accept_promise"}'
    data = router._parse_response(raw)
    assert data["approach"] == "maintain"


def test_parse_invalid_json_raises():
    router = LlmStrategyRouter(make_config())
    with pytest.raises(ValueError, match="无法从 LLM 响应中提取 JSON"):
        router._parse_response("Not a JSON response at all, just some text.")


# ── 字段校验测试 ────────────────────────────────────────────────────

def test_validate_valid_data():
    router = LlmStrategyRouter(make_config())
    data = {"approach": "guide", "tone": "neutral", "push_intensity": 3, "max_push_rounds": 3, "consequence_emphasis": 2}
    assert router._validate(data) == []


def test_validate_invalid_approach():
    router = LlmStrategyRouter(make_config())
    errors = router._validate({"approach": "aggressive", "tone": "neutral", "push_intensity": 2, "max_push_rounds": 3, "consequence_emphasis": 2})
    assert len(errors) == 1
    assert "approach" in errors[0]


def test_validate_invalid_tone():
    router = LlmStrategyRouter(make_config())
    errors = router._validate({"approach": "guide", "tone": "angry", "push_intensity": 2, "max_push_rounds": 3, "consequence_emphasis": 2})
    assert len(errors) == 1
    assert "tone" in errors[0]


def test_validate_push_intensity_out_of_range():
    router = LlmStrategyRouter(make_config())
    errors = router._validate({"approach": "guide", "tone": "neutral", "push_intensity": 6, "max_push_rounds": 3, "consequence_emphasis": 2})
    assert len(errors) == 1
    assert "push_intensity" in errors[0]

    errors2 = router._validate({"approach": "guide", "tone": "neutral", "push_intensity": 0, "max_push_rounds": 3, "consequence_emphasis": 2})
    assert len(errors2) == 1


def test_validate_consequence_emphasis_out_of_range():
    router = LlmStrategyRouter(make_config())
    errors = router._validate({"approach": "guide", "tone": "neutral", "push_intensity": 3, "max_push_rounds": 3, "consequence_emphasis": 10})
    assert len(errors) == 1


# ── 缓存测试 ─────────────────────────────────────────────────────────

def test_cache_set_and_get():
    profile = static_fallback({"new_flag": 0, "chat_group": "H2"})
    key = _cache_key({"new_flag": 0, "chat_group": "H2"})
    _cache_set(key, profile)
    cached = _cache_get(key, ttl=3600)
    assert cached is not None
    assert cached.approach == profile.approach


def test_cache_ttl_expiry():
    profile = static_fallback({"new_flag": 0, "chat_group": "H2"})
    key = _cache_key({"new_flag": 0, "chat_group": "H2"})
    _cache_set(key, profile)
    # TTL=0 means immediate expiry
    cached = _cache_get(key, ttl=0)
    assert cached is None


def test_cache_key_different_profiles():
    k1 = _cache_key({"new_flag": 0, "chat_group": "H2"})
    k2 = _cache_key({"new_flag": 2, "chat_group": "S0"})
    assert k1 != k2


# ── Fallback 测试 ────────────────────────────────────────────────────

def test_static_fallback_basic():
    result = static_fallback({"new_flag": 0, "chat_group": "H2"})
    assert isinstance(result, StrategyProfile)
    assert result.approach == "educate"
    assert result.segment_key == "nf=0_H2"


def test_static_fallback_with_dpd_zero():
    result = static_fallback({"new_flag": 0, "chat_group": "H2", "dpd": 0})
    assert result.tone == "soft"
    assert result.push_intensity <= 2


def test_static_fallback_with_dpd_deep():
    result = static_fallback({"new_flag": 2, "chat_group": "S0", "dpd": 10})
    assert result.tone == "firm"
    assert result.extension_priority is True
    assert result.consequence_emphasis == 5


def test_static_fallback_invalid_chat_group():
    with pytest.raises(KeyError):
        static_fallback({"new_flag": 0, "chat_group": "INVALID"})


# ── 路由集成测试（均走 fallback，无需 LLM） ─────────────────────────

def test_route_mock_config():
    router = LlmStrategyRouter(make_config(provider="mock"))
    result = router.route({"new_flag": 0, "chat_group": "H2", "dpd": 3})
    assert isinstance(result, StrategyProfile)
    assert result.segment_key == "nf=0_H2"


def test_route_disabled():
    router = LlmStrategyRouter(make_config(strategy_routing_enabled=False))
    result = router.route({"new_flag": 2, "chat_group": "S0"})
    assert isinstance(result, StrategyProfile)


def test_route_no_api_key():
    config = LLMConfig(provider="openai", api_key="", strategy_routing_enabled=True)
    router = LlmStrategyRouter(config)
    result = router.route({"new_flag": 1, "chat_group": "H1"})
    assert isinstance(result, StrategyProfile)


def test_route_result_is_usable_as_strategy():
    """验证路由结果可以被 chatbot 当作 StrategyProfile 使用"""
    router = LlmStrategyRouter(make_config(strategy_routing_enabled=False))
    result = router.route({"new_flag": 1, "chat_group": "H2"})
    # chatbot 访问的字段都应该可用
    assert hasattr(result, "approach")
    assert hasattr(result, "tone")
    assert hasattr(result, "push_intensity")
    assert hasattr(result, "extension_priority")
    assert hasattr(result, "max_push_rounds")
    assert hasattr(result, "consequence_emphasis")
    assert hasattr(result, "education_emphasis")
    assert hasattr(result, "relationship_emphasis")
    assert hasattr(result, "max_objections")
    assert hasattr(result, "extension_fee_ratio")
    assert hasattr(result, "avoid_tactics")
    assert hasattr(result, "fallback_approach")


# ── Prompt 构造测试 ──────────────────────────────────────────────────

def test_build_user_prompt():
    config = LLMConfig(provider="openai", api_key="sk-test", strategy_routing_enabled=True)
    router = LlmStrategyRouter(config)
    prompt = router._build_user_prompt({
        "new_flag": 2, "chat_group": "S0", "dpd": 10,
        "repay_history": 0.3, "approved_amount": 2000000,
        "income_ratio": 0.8, "product_name": "PinjamPro",
        "marital_status": "married", "loan_seq": 4, "call_hour": 14,
    })
    assert "new_flag: 2" in prompt
    assert "nasabah lama" in prompt
    assert "chat_group: S0" in prompt
    assert "dpd: 10" in prompt
    assert "repay_history: 0.3" in prompt
    assert "PinjamPro" in prompt
    assert "loan_seq: 4" in prompt


def test_system_prompt_contains_key_elements():
    from core.llm_strategy_router import SYSTEM_PROMPT
    assert "approach" in SYSTEM_PROMPT
    assert "tone" in SYSTEM_PROMPT
    assert "push_intensity" in SYSTEM_PROMPT
    assert "new_flag" in SYSTEM_PROMPT
    assert "chat_group" in SYSTEM_PROMPT
    assert "DPD" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT
