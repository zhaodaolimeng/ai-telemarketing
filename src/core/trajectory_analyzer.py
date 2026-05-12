#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P15-H05: T3 跨通话演化调度 — 行为轨迹分析引擎

根据用户多通通话的历史快照，识别行为演化方向，输出策略调整建议。
纯规则驱动，无 LLM 调用延迟。
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CallSnapshot:
    """单通通话的压缩摘要，用于轨迹分析"""
    call_index: int                    # 0-based
    call_date: str                     # ISO date
    new_flag: int
    chat_group: str
    dpd: int
    call_result: str                   # "success" | "failed" | "extended" | "abandoned"
    objection_count: int = 0
    cooperation_signals: int = 0
    got_commitment: bool = False
    got_extension: bool = False
    turns: int = 0
    silence_count: int = 0
    push_count: int = 0
    loan_no: str = ""


@dataclass
class StrategyAdjustment:
    """策略字段的增量调整"""
    approach: Optional[str] = None
    tone: Optional[str] = None
    push_intensity_delta: int = 0
    extension_priority: Optional[bool] = None
    extension_fee_ratio_delta: float = 0.0
    max_push_rounds_delta: int = 0
    consequence_emphasis_delta: int = 0
    education_emphasis: Optional[bool] = None
    relationship_emphasis: Optional[bool] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()
                if v is not None and v != 0 and v != 0.0}

    def __bool__(self) -> bool:
        return len(self.to_dict()) > 0


@dataclass
class TrajectoryProfile:
    """轨迹分析输出"""
    direction: str = "insufficient_data"
    active_patterns: list = field(default_factory=list)
    adjustments: StrategyAdjustment = field(default_factory=StrategyAdjustment)
    calls_analyzed: int = 0


class TrajectoryAnalyzer:
    """T3 跨通话轨迹分析器。纯函数：给定有序通话快照 → 输出轨迹画像和策略调整"""

    DIRECTION_WINDOW = 5

    def analyze(self, snapshots: list[CallSnapshot]) -> TrajectoryProfile:
        if not snapshots:
            return TrajectoryProfile()

        if len(snapshots) < 2:
            return TrajectoryProfile(direction="insufficient_data",
                                     calls_analyzed=len(snapshots))

        recent = snapshots[-min(len(snapshots), self.DIRECTION_WINDOW):]
        profile = TrajectoryProfile(calls_analyzed=len(snapshots))

        profile.direction = self._detect_direction(recent)
        profile.active_patterns = self._detect_patterns(snapshots)
        profile.adjustments = self._apply_rules(snapshots, profile)

        return profile

    def _detect_direction(self, recent: list[CallSnapshot]) -> str:
        n = len(recent)
        if n < 2:
            return "insufficient_data"

        mid = n // 2
        first_half = recent[:mid]
        second_half = recent[mid:]

        def mean_coop(seq):
            return sum(s.cooperation_signals for s in seq) / max(len(seq), 1)

        def mean_obj(seq):
            return sum(s.objection_count for s in seq) / max(len(seq), 1)

        coop_delta = mean_coop(second_half) - mean_coop(first_half)
        obj_delta = mean_obj(second_half) - mean_obj(first_half)

        if abs(coop_delta) <= 0.5 and abs(obj_delta) <= 0.5:
            return "stable"
        if coop_delta > 0.5 and obj_delta <= 0:
            return "improving"
        if coop_delta < -0.5 or obj_delta > 1.0:
            return "deteriorating"
        return "volatile"

    def _detect_patterns(self, snapshots: list[CallSnapshot]) -> list[str]:
        patterns = []
        recent = snapshots[-3:]

        if sum(1 for s in recent if s.got_extension) >= 2:
            patterns.append("ALWAYS_EXTENDS")

        objs = [s.objection_count for s in recent]
        if len(objs) >= 2 and objs[-1] - objs[0] >= 2:
            patterns.append("RESISTANCE_ESCALATING")

        silences = [s.silence_count for s in recent]
        if len(silences) >= 2 and silences[-1] - silences[0] >= 2:
            patterns.append("SILENCE_GROWING")

        if len(snapshots) >= 3 and all(
            s.call_result != "success" for s in snapshots[-3:]
        ):
            patterns.append("CONSECUTIVE_FAILURE")

        prev_success = any(s.call_result == "success" for s in snapshots[:-1])
        if prev_success and snapshots[-1].call_result != "success":
            patterns.append("CYCLE_BREAKER")

        successes = [s for s in snapshots if s.call_result == "success"]
        if len(successes) >= 2 and all(s.push_count >= 3 for s in successes):
            patterns.append("ALWAYS_PAYS_AFTER_PUSH_3")

        if len(snapshots) >= 2 and snapshots[-2].got_extension:
            if snapshots[-1].loan_no == snapshots[-2].loan_no:
                patterns.append("POST_EXTENSION_REPEAT")

        return patterns

    def _apply_rules(
        self, snapshots: list[CallSnapshot], profile: TrajectoryProfile
    ) -> StrategyAdjustment:
        adj = StrategyAdjustment()

        # R1: 恶化 → 软化
        if profile.direction == "deteriorating" or "RESISTANCE_ESCALATING" in profile.active_patterns:
            adj.tone = "soft"
            adj.push_intensity_delta = -1
            adj.max_push_rounds_delta = -1

        # R2: 改善 → 奖励
        if profile.direction == "improving" and "RESISTANCE_ESCALATING" not in profile.active_patterns:
            adj.push_intensity_delta = -1
            adj.relationship_emphasis = True

        # R3: 习惯于展期 → 主动提供
        if "ALWAYS_EXTENDS" in profile.active_patterns:
            adj.extension_priority = True
            adj.extension_fee_ratio_delta = -0.05

        # R4: 刚展期过同笔借款 → 别再推展期
        if "POST_EXTENSION_REPEAT" in profile.active_patterns:
            adj.extension_priority = False

        # R5: 沉默增长 → 缓和
        if "SILENCE_GROWING" in profile.active_patterns:
            adj.tone = "soft"
            adj.push_intensity_delta = -1
            adj.consequence_emphasis_delta = -1

        # R6: 连续失败 3+ → 升级
        if "CONSECUTIVE_FAILURE" in profile.active_patterns:
            adj.tone = "firm"
            adj.push_intensity_delta = 1
            adj.consequence_emphasis_delta = 1

        # R7: 曾履约→最近违约 → 中性+展期
        if "CYCLE_BREAKER" in profile.active_patterns:
            adj.tone = "neutral"
            adj.push_intensity_delta = -1
            adj.extension_priority = True

        # R8: 需要压力才还 → 多推
        if "ALWAYS_PAYS_AFTER_PUSH_3" in profile.active_patterns:
            adj.max_push_rounds_delta = 1
            adj.push_intensity_delta = 1

        return adj
