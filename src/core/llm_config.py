#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Fallback 配置管理
从环境变量读取配置，默认 mock 模式（无需 API key 即可开发测试）
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    provider: str = "mock"  # "openai" | "anthropic" | "ollama" | "mock"
    api_key: str = ""
    api_base: str = ""       # 可选自定义端点
    model: str = "gpt-4o"
    max_tokens: int = 256
    temperature: float = 0.7
    timeout_seconds: int = 10
    max_retries: int = 2
    max_llm_turns: int = 3   # LLM 最多连续对话轮数，超过后切回规则机

    # P15-H02: LLM 策略路由专用配置
    strategy_routing_model: str = ""       # 策略路由专用模型（空=用默认）
    strategy_routing_enabled: bool = True  # 总开关
    cache_ttl_seconds: int = 3600          # 策略缓存有效期（秒）

    @classmethod
    def from_env(cls, **overrides) -> "LLMConfig":
        # 自动检测 API key：优先 LLM_API_KEY，兜底 OPENAI_API_KEY / ANTHROPIC_AUTH_TOKEN
        api_key = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        # 自动检测 API base
        api_base = os.environ.get("LLM_API_BASE", "") or os.environ.get("OPENAI_BASE_URL", "")
        # 自动检测 provider：有 OPENAI_BASE_URL 或 deepseek 时默认 openai
        provider = os.environ.get("LLM_PROVIDER", "")
        if not provider:
            if api_key and api_base:
                provider = "openai"
            elif api_key:
                provider = "openai"
            else:
                provider = "mock"

        config = cls(
            provider=provider,
            api_key=api_key,
            api_base=api_base,
            model=os.environ.get("LLM_MODEL", "gpt-4o"),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "256")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            timeout_seconds=int(os.environ.get("LLM_TIMEOUT", "10")),
            max_retries=int(os.environ.get("LLM_MAX_RETRIES", "2")),
            max_llm_turns=int(os.environ.get("LLM_MAX_TURNS", "3")),
            strategy_routing_model=os.environ.get("LLM_STRATEGY_MODEL", ""),
            strategy_routing_enabled=os.environ.get("LLM_STRATEGY_ENABLED", "true").lower() == "true",
            cache_ttl_seconds=int(os.environ.get("LLM_STRATEGY_CACHE_TTL", "3600")),
        )
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    @property
    def is_available(self) -> bool:
        return self.provider == "mock" or bool(self.api_key)
