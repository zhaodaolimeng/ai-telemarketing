#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Fallback 触发检测器
从 V4 原型提取并增强，检测何时需要 LLM 介入
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any


@dataclass
class FallbackTrigger:
    name: str
    condition: Callable[[Any], bool]
    description: str


class FallbackDetector:
    """检测是否需要触发 LLM Fallback"""

    def __init__(self):
        self.triggers: List[FallbackTrigger] = []
        self._register_default_triggers()

    def _register_default_triggers(self):
        """注册 5 种默认触发条件，任一满足即触发"""

        # 1. 连续 unknown 意图（核心触发条件）
        def too_many_unknowns(bot) -> bool:
            if not hasattr(bot, "user_history_intents"):
                return False
            intents = getattr(bot, "user_history_intents", [])
            if len(intents) < 2:
                return False
            return intents[-2:] == ["unknown", "unknown"]
        self.triggers.append(FallbackTrigger(
            name="too_many_unknowns",
            condition=too_many_unknowns,
            description="连续2次无法识别用户意图"
        ))

        # 2. 客户回复不相关/转移话题
        def irrelevant_response(bot) -> bool:
            if not hasattr(bot, "conversation") or len(bot.conversation) < 2:
                return False
            last_turn = bot.conversation[-1]
            customer_text = getattr(last_turn, "customer", None) or ""
            if not customer_text:
                return False
            divert_keywords = [
                "cuaca", "makan", "lagu", "film", "olahraga",
                "bicara nanti", "tidak ingin bicara", "ngapain telepon",
                "jangan ganggu", "saya sibuk sekali", "stop telepon saya"
            ]
            return any(kw in customer_text.lower() for kw in divert_keywords)
        self.triggers.append(FallbackTrigger(
            name="irrelevant_response",
            condition=irrelevant_response,
            description="客户回复不相关/转移话题"
        ))

        # 3. 客户提出多种抗拒理由
        def complex_resistance(bot) -> bool:
            if not hasattr(bot, "conversation") or len(bot.conversation) < 2:
                return False
            last_turn = bot.conversation[-1]
            customer_text = getattr(last_turn, "customer", None) or ""
            if not customer_text:
                return False
            keywords_combo = ["tidak punya uang", "sakit", "kehilangan pekerjaan",
                              "belum gajian", "ada masalah keluarga", "kena musibah",
                              "dipecat", "usaha bangkrut", "anak sakit", "orang tua meninggal"]
            count = sum(1 for kw in keywords_combo if kw in customer_text.lower())
            return count >= 2
        self.triggers.append(FallbackTrigger(
            name="complex_resistance",
            condition=complex_resistance,
            description="客户提出多种抗拒理由"
        ))

        # 4. 沉默/回复过短
        def too_silent(bot) -> bool:
            if not hasattr(bot, "conversation") or len(bot.conversation) < 3:
                return False
            silent_count = 0
            for turn in reversed(bot.conversation[-3:]):
                customer_text = getattr(turn, "customer", None) or ""
                if len(customer_text.strip()) < 3 or customer_text.strip() in ["...", "", "iya", "ya", "ok"]:
                    silent_count += 1
            return silent_count >= 3
        self.triggers.append(FallbackTrigger(
            name="too_silent",
            condition=too_silent,
            description="客户多次沉默/回复过短"
        ))

        # 5. 追问次数过多（替代 object 计数方式）
        def too_many_pushes(bot) -> bool:
            objection_count = getattr(bot, "objection_count", 0)
            max_objections = getattr(bot, "max_objections", 3)
            return objection_count >= max_objections - 1
        self.triggers.append(FallbackTrigger(
            name="too_many_pushes",
            condition=too_many_pushes,
            description="已多次追问未获得承诺时间"
        ))

    def check(self, bot) -> tuple:
        """检查是否触发 LLM Fallback，返回 (是否触发, 触发的 trigger 或 None)"""
        for trigger in self.triggers:
            try:
                if trigger.condition(bot):
                    return True, trigger
            except Exception:
                continue
        return False, None
