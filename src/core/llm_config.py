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

    @classmethod
    def from_env(cls, **overrides) -> "LLMConfig":
        config = cls(
            provider=os.environ.get("LLM_PROVIDER", "mock"),
            api_key=os.environ.get("LLM_API_KEY", ""),
            api_base=os.environ.get("LLM_API_BASE", ""),
            model=os.environ.get("LLM_MODEL", "gpt-4o"),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "256")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            timeout_seconds=int(os.environ.get("LLM_TIMEOUT", "10")),
            max_retries=int(os.environ.get("LLM_MAX_RETRIES", "2")),
            max_llm_turns=int(os.environ.get("LLM_MAX_TURNS", "3")),
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
