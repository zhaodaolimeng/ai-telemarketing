#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P15-B01: 分阶段×分客群差异化策略配置

基于 P15-G02 调研数据：new_flag(新客0/新转老1/老客2) × chat_group(H1/H2/S0)
= 9 种策略组合。参数依据 806 条 gold case + 1,459 条 CSV 量化验证。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StrategyProfile:
    """催收策略参数集 — 一个客群×阶段组合对应一组参数"""

    # 元信息
    segment_key: str  # "nf=0_H2" 格式
    segment_name: str  # 中文标签

    # 核心行为参数
    approach: str  # educate / guide / maintain / light / firm / intervene
    tone: str      # soft / neutral / firm / urgent
    push_intensity: int  # 1-5，催促力度
    max_objections: int  # 最大异议轮次后升级

    # 财务策略
    extension_fee_ratio: float  # 展期费率 (0.2=20%)
    extension_priority: bool    # 优先推荐展期（而非全额）
    partial_payment_offered: bool  # 主动提示部分还款选项

    # 轮次管理
    max_push_rounds: int  # PUSH_FOR_TIME 最大轮次

    # 沟通风格
    consequence_emphasis: int  # 1-5，后果强调程度
    education_emphasis: bool   # 教育型话术（解释合同、义务）
    relationship_emphasis: bool  # 关系型话术（认可历史、熟客口吻）

    @property
    def tone_label(self) -> str:
        """将 tone 转为印尼语语气关键词"""
        return {
            "soft": "lembut & sabar",
            "neutral": "netral & profesional",
            "firm": "tegas & jelas",
            "urgent": "mendesak & serius",
        }.get(self.tone, "netral")


# ─── 9 种策略组合配置 ─────────────────────────────────────────────
# 参数来源：P15-G02 806 条 gold case + P15-B06 全维度分析

PROFILES: dict[str, StrategyProfile] = {
    # ═══ 新客 (new_flag=0)：教育为主，建立还款认知 ═══
    "nf=0_H1": StrategyProfile(
        segment_key="nf=0_H1",
        segment_name="新客·H1·教育引导型",
        approach="educate",
        tone="soft",
        push_intensity=2,
        max_objections=3,
        extension_fee_ratio=0.25,
        extension_priority=False,
        partial_payment_offered=False,
        max_push_rounds=3,
        consequence_emphasis=1,
        education_emphasis=True,
        relationship_emphasis=False,
    ),
    "nf=0_H2": StrategyProfile(
        segment_key="nf=0_H2",
        segment_name="新客·H2·教育引导型",
        approach="educate",
        tone="soft",
        push_intensity=2,
        max_objections=3,
        extension_fee_ratio=0.25,
        extension_priority=False,
        partial_payment_offered=False,
        max_push_rounds=3,
        consequence_emphasis=1,           # 新客H2不需要后果强调
        education_emphasis=True,
        relationship_emphasis=False,
    ),
    "nf=0_S0": StrategyProfile(
        segment_key="nf=0_S0",
        segment_name="新客·S0·降门槛引导型",
        approach="educate",               # 新客仍以教育为主，激进适得其反
        tone="firm",                      # S0需要严肃但不压迫
        push_intensity=3,                 # 适中，不过度施压
        max_objections=3,                 # 多给耐心
        extension_fee_ratio=0.15,         # 大幅降展期门槛
        extension_priority=True,          # 优先推展期
        partial_payment_offered=True,     # 主动提示部分还款
        max_push_rounds=3,
        consequence_emphasis=3,           # 中等后果强调
        education_emphasis=True,
        relationship_emphasis=False,
    ),

    # ═══ 新转老 (new_flag=1)：过渡型，认可历史 = ═══
    "nf=1_H1": StrategyProfile(
        segment_key="nf=1_H1",
        segment_name="新转老·H1·过渡引导型",
        approach="guide",
        tone="neutral",
        push_intensity=2,
        max_objections=3,
        extension_fee_ratio=0.25,
        extension_priority=False,
        partial_payment_offered=False,
        max_push_rounds=3,
        consequence_emphasis=2,
        education_emphasis=False,
        relationship_emphasis=True,       # 认可首次续贷
    ),
    "nf=1_H2": StrategyProfile(
        segment_key="nf=1_H2",
        segment_name="新转老·H2·关系维护型",
        approach="guide",                 # 引导但不教育（已有还款经验）
        tone="neutral",                   # tone×new_flag=1×1=+0.40
        push_intensity=2,                 # 与统一持平，避免被模型误判
        max_objections=4,
        extension_fee_ratio=0.30,
        extension_priority=False,
        partial_payment_offered=False,
        max_push_rounds=2,
        consequence_emphasis=1,
        education_emphasis=False,
        relationship_emphasis=True,
    ),
    "nf=1_S0": StrategyProfile(
        segment_key="nf=1_S0",
        segment_name="新转老·S0·方案优先型",
        approach="guide",                 # 引导为主，不硬推
        tone="firm",                      # firm works ok for nf=1 (tone×new_flag +0.397)
        push_intensity=3,                 # 适中
        max_objections=3,
        extension_fee_ratio=0.20,         # 降展期门槛
        extension_priority=True,          # 展期/部分还款优先
        partial_payment_offered=True,
        max_push_rounds=3,
        consequence_emphasis=3,
        education_emphasis=False,
        relationship_emphasis=True,       # 提及历史还款记录
    ),

    # ═══ 老客 (new_flag=2)：关系维护 or 强硬，两极分化 ═══
    "nf=2_H1": StrategyProfile(
        segment_key="nf=2_H1",
        segment_name="老客·H1·关系型",
        approach="maintain",
        tone="neutral",
        push_intensity=2,
        max_objections=4,
        extension_fee_ratio=0.30,
        extension_priority=False,
        partial_payment_offered=False,
        max_push_rounds=2,
        consequence_emphasis=2,
        education_emphasis=False,
        relationship_emphasis=True,       # 强调老客身份和信用
    ),
    "nf=2_H2": StrategyProfile(
        segment_key="nf=2_H2",
        segment_name="老客·H2·关系极轻型",
        approach="guide",                 # 引导确认，不教育
        tone="neutral",                   # tone×new_flag=1×2=+0.79
        push_intensity=2,                 # 与统一持平，差异化在关系维护
        max_objections=5,                 # 极宽容
        extension_fee_ratio=0.30,
        extension_priority=False,
        partial_payment_offered=False,
        max_push_rounds=2,                # 适度保留
        consequence_emphasis=1,
        education_emphasis=False,
        relationship_emphasis=True,
    ),
    "nf=2_S0": StrategyProfile(
        segment_key="nf=2_S0",
        segment_name="老客·S0·后果警示型",
        approach="guide",                 # 引导为主，避免 approach×stage 惩罚
        tone="firm",                      # tone×new_flag=2×2=+1.59 强正向
        push_intensity=4,
        max_objections=2,
        extension_fee_ratio=0.30,
        extension_priority=False,         # 优先全额，老客明知规则
        partial_payment_offered=True,
        max_push_rounds=4,
        consequence_emphasis=5,           # 保留最强后果强调（对老客有效）
        education_emphasis=False,
        relationship_emphasis=False,
    ),
}


def get_strategy_profile(
    new_flag: int,
    chat_group: str,
    dpd: Optional[int] = None,
) -> StrategyProfile:
    """
    获取客群×阶段×DPD 策略配置。

    Args:
        new_flag: 0=新客, 1=新转老, 2=老客
        chat_group: H1/H2/S0
        dpd: 可选，逾期天数，用于分档微调:
             ≤0: 宽限期内(97%还款率) → 减半 push, 纯提醒
             1-7: 轻度逾期(36%还款率) → 使用基准策略
             >7: 深度逾期(0.7%还款率) → 拉满后果强调

    Returns:
        StrategyProfile for the segment (DPD-adjusted copy if dpd provided)

    Raises:
        KeyError: 无效的 new_flag 或 chat_group
    """
    chat_group = chat_group.upper().strip()
    if chat_group not in ("H1", "H2", "S0"):
        raise KeyError(f"无效的 chat_group: {chat_group}，必须是 H1/H2/S0")

    if new_flag not in (0, 1, 2):
        raise KeyError(f"无效的 new_flag: {new_flag}，必须是 0/1/2")

    key = f"nf={new_flag}_{chat_group}"
    base = PROFILES.get(key)
    if base is None:
        raise KeyError(f"未找到策略配置: {key}")

    if dpd is None:
        return base

    # DPD 分档微调 (P15-B06 量化依据)
    if dpd <= 0:
        # 宽限期内: 97.1% 有效还款率, 轻推即可
        return StrategyProfile(
            segment_key=f"{key}_dpd0",
            segment_name=f"{base.segment_name}+DPD≤0",
            approach=base.approach,
            tone="soft",
            push_intensity=max(1, base.push_intensity // 2),
            max_objections=base.max_objections + 2,
            extension_fee_ratio=base.extension_fee_ratio,
            extension_priority=False,
            partial_payment_offered=False,
            max_push_rounds=max(1, base.max_push_rounds // 2),
            consequence_emphasis=1,
            education_emphasis=base.education_emphasis,
            relationship_emphasis=True,
        )
    elif dpd > 7:
        # 深度逾期: 0.7% 有效还款率, 重点在降门槛（展期/部分还款）
        # 不拉满push — 0.7%本身就很难催回，过度施压反而无效
        return StrategyProfile(
            segment_key=f"{key}_dpd7+",
            segment_name=f"{base.segment_name}+DPD>7",
            approach=base.approach,       # 保持基础的 approach
            tone="firm",
            push_intensity=min(base.push_intensity + 1, 4),
            max_objections=min(2, base.max_objections),
            extension_fee_ratio=max(0.10, base.extension_fee_ratio - 0.05),  # 降门槛
            extension_priority=True,
            partial_payment_offered=True,
            max_push_rounds=base.max_push_rounds,
            consequence_emphasis=5,       # 后果仍强调（对老客有效）
            education_emphasis=base.education_emphasis,
            relationship_emphasis=base.relationship_emphasis,
        )
    else:
        # DPD 1-7: 催收发挥空间, 使用基准策略
        return base


def get_strategy_summary() -> str:
    """返回 9 种策略的速查表"""
    lines = ["策略配置速查表", "=" * 80]
    for key in ["nf=0_H1", "nf=0_H2", "nf=0_S0",
                "nf=1_H1", "nf=1_H2", "nf=1_S0",
                "nf=2_H1", "nf=2_H2", "nf=2_S0"]:
        p = PROFILES[key]
        lines.append(
            f"{p.segment_name:20s} | approach={p.approach:10s} tone={p.tone:6s} "
            f"push={p.push_intensity} obj={p.max_objections} "
            f"ext_prio={str(p.extension_priority):5s} "
            f"edu={str(p.education_emphasis):5s} rel={str(p.relationship_emphasis):5s}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_strategy_summary())
