"""P15-H05: T3 跨通话轨迹分析单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.trajectory_analyzer import (
    TrajectoryAnalyzer, CallSnapshot, StrategyAdjustment, TrajectoryProfile
)


def make_cs(index: int, call_result: str = "failed", **overrides) -> CallSnapshot:
    """工厂：构造 CallSnapshot，零值默认"""
    defaults = dict(
        call_index=index,
        call_date=f"2026-05-{index+1:02d}",
        new_flag=0,
        chat_group="H2",
        dpd=0,
        call_result=call_result,
        objection_count=0,
        cooperation_signals=0,
        got_commitment=False,
        got_extension=False,
        turns=5,
        silence_count=0,
        push_count=0,
        loan_no="L001",
    )
    defaults.update(overrides)
    return CallSnapshot(**defaults)


# ═══════════════════════════════════════════════════════════════════
# 方向检测
# ═══════════════════════════════════════════════════════════════════

def test_direction_improving():
    """合作信号递增，异议递减 → improving"""
    snapshots = [
        make_cs(0, cooperation_signals=1, objection_count=3),
        make_cs(1, cooperation_signals=2, objection_count=2),
        make_cs(2, cooperation_signals=3, objection_count=1),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert profile.direction == "improving"


def test_direction_deteriorating():
    """异议递增 → deteriorating"""
    snapshots = [
        make_cs(0, cooperation_signals=3, objection_count=0),
        make_cs(1, cooperation_signals=2, objection_count=1),
        make_cs(2, cooperation_signals=1, objection_count=3),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert profile.direction == "deteriorating"


def test_direction_stable():
    """无明显变化 → stable"""
    snapshots = [
        make_cs(0, cooperation_signals=2, objection_count=1),
        make_cs(1, cooperation_signals=2, objection_count=1),
        make_cs(2, cooperation_signals=2, objection_count=1),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert profile.direction == "stable"


def test_direction_insufficient_data_empty():
    """0 通通话 → insufficient_data"""
    profile = TrajectoryAnalyzer().analyze([])
    assert profile.direction == "insufficient_data"
    assert profile.calls_analyzed == 0


def test_direction_insufficient_data_single():
    """1 通通话 → insufficient_data"""
    snapshots = [make_cs(0)]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert profile.direction == "insufficient_data"
    assert profile.calls_analyzed == 1


def test_direction_volatile():
    """coop 上升但 obj 也在上升 → 不是 improving/deteriorating/stable → volatile"""
    snapshots = [
        make_cs(0, cooperation_signals=0, objection_count=0),
        make_cs(1, cooperation_signals=0, objection_count=0),
        make_cs(2, cooperation_signals=0, objection_count=0),
        make_cs(3, cooperation_signals=1, objection_count=0),
        make_cs(4, cooperation_signals=1, objection_count=1),
        make_cs(5, cooperation_signals=1, objection_count=1),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert profile.direction == "volatile"


# ═══════════════════════════════════════════════════════════════════
# 模式识别
# ═══════════════════════════════════════════════════════════════════

def test_pattern_always_extends():
    """最近 3 通中 2+ 展期 → ALWAYS_EXTENDS"""
    snapshots = [
        make_cs(0, got_extension=True),
        make_cs(1, got_extension=False),
        make_cs(2, got_extension=True),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "ALWAYS_EXTENDS" in profile.active_patterns


def test_pattern_resistance_escalating():
    """异议从 1 增至 3 → RESISTANCE_ESCALATING"""
    snapshots = [
        make_cs(0, objection_count=0),
        make_cs(1, objection_count=1),
        make_cs(2, objection_count=3),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "RESISTANCE_ESCALATING" in profile.active_patterns


def test_pattern_silence_growing():
    """沉默从 0 增至 3 → SILENCE_GROWING"""
    snapshots = [
        make_cs(0, silence_count=0),
        make_cs(1, silence_count=1),
        make_cs(2, silence_count=3),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "SILENCE_GROWING" in profile.active_patterns


def test_pattern_consecutive_failure():
    """3 连续失败 → CONSECUTIVE_FAILURE"""
    snapshots = [
        make_cs(0, call_result="failed"),
        make_cs(1, call_result="failed"),
        make_cs(2, call_result="failed"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "CONSECUTIVE_FAILURE" in profile.active_patterns


def test_pattern_cycle_breaker():
    """曾有成功→最近失败 → CYCLE_BREAKER"""
    snapshots = [
        make_cs(0, call_result="success"),
        make_cs(1, call_result="failed"),
        make_cs(2, call_result="failed"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "CYCLE_BREAKER" in profile.active_patterns


def test_pattern_always_pays_after_push_3():
    """成功通话中 push_count >= 3 → ALWAYS_PAYS_AFTER_PUSH_3"""
    snapshots = [
        make_cs(0, call_result="success", push_count=3),
        make_cs(1, call_result="failed", push_count=1),
        make_cs(2, call_result="success", push_count=4),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "ALWAYS_PAYS_AFTER_PUSH_3" in profile.active_patterns


def test_pattern_post_extension_repeat():
    """展期后同 loan 再通话 → POST_EXTENSION_REPEAT"""
    snapshots = [
        make_cs(0, got_extension=True, loan_no="L001"),
        make_cs(1, got_extension=False, loan_no="L001"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    assert "POST_EXTENSION_REPEAT" in profile.active_patterns


# ═══════════════════════════════════════════════════════════════════
# 规则评估
# ═══════════════════════════════════════════════════════════════════

def test_rule_soften_for_deteriorating():
    """恶化 → tone=soft, push-1, max_push-1"""
    snapshots = [
        make_cs(0, cooperation_signals=3, objection_count=0),
        make_cs(1, cooperation_signals=1, objection_count=3),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.tone == "soft"
    assert adj.push_intensity_delta == -1
    assert adj.max_push_rounds_delta == -1


def test_rule_harden_for_consecutive_failure():
    """3 连败 → tone=firm, push+1, consequence+1"""
    snapshots = [
        make_cs(0, call_result="failed"),
        make_cs(1, call_result="failed"),
        make_cs(2, call_result="failed"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.tone == "firm"
    assert adj.push_intensity_delta == 1
    assert adj.consequence_emphasis_delta == 1


def test_rule_lead_with_extension():
    """ALWAYS_EXTENDS → extension_priority=True, fee-0.05"""
    snapshots = [
        make_cs(0, got_extension=True, loan_no="L001"),
        make_cs(1, got_extension=True, loan_no="L002"),
        make_cs(2, got_extension=False, loan_no="L003"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.extension_priority is True
    assert adj.extension_fee_ratio_delta == -0.05


def test_rule_soften_for_silence_growing():
    """沉默增长 → tone=soft, push-1, consequence-1"""
    snapshots = [
        make_cs(0, silence_count=0, call_result="failed"),
        make_cs(1, silence_count=1, call_result="success"),
        make_cs(2, silence_count=3, call_result="success"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.tone == "soft"
    assert adj.push_intensity_delta == -1
    assert adj.consequence_emphasis_delta == -1


def test_rule_cycle_breaker_neutral_extension():
    """CYCLE_BREAKER → tone=neutral, push-1, extension_priority=True"""
    snapshots = [
        make_cs(0, call_result="success"),
        make_cs(1, call_result="failed"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.tone == "neutral"
    assert adj.push_intensity_delta == -1
    assert adj.extension_priority is True


def test_rule_pressure_payer_high_push():
    """ALWAYS_PAYS_AFTER_PUSH_3 → push_rounds+1, push_intensity+1"""
    snapshots = [
        make_cs(0, call_result="success", push_count=3),
        make_cs(1, call_result="success", push_count=4),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.max_push_rounds_delta == 1
    assert adj.push_intensity_delta == 1


def test_rule_post_extension_no_more_extension():
    """POST_EXTENSION_REPEAT → extension_priority=False"""
    snapshots = [
        make_cs(0, got_extension=True, loan_no="L001"),
        make_cs(1, got_extension=False, loan_no="L001"),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.extension_priority is False


def test_rule_improving_reward():
    """改善 → push-1, relationship_emphasis=True"""
    snapshots = [
        make_cs(0, cooperation_signals=1, objection_count=2),
        make_cs(1, cooperation_signals=3, objection_count=0),
    ]
    profile = TrajectoryAnalyzer().analyze(snapshots)
    adj = profile.adjustments
    assert adj.push_intensity_delta == -1
    assert adj.relationship_emphasis is True


# ═══════════════════════════════════════════════════════════════════
# 安全边界
# ═══════════════════════════════════════════════════════════════════

def test_adjustment_bounds_valid():
    """StrategyAdjustment 字段值在合理范围内"""
    adj = StrategyAdjustment(
        tone="soft",
        push_intensity_delta=-1,
        max_push_rounds_delta=-1,
        consequence_emphasis_delta=1,
        extension_fee_ratio_delta=-0.05,
        extension_priority=True,
    )
    d = adj.to_dict()
    assert d["tone"] == "soft"
    assert d["push_intensity_delta"] == -1
    assert d["max_push_rounds_delta"] == -1
    assert d["consequence_emphasis_delta"] == 1
    assert d["extension_fee_ratio_delta"] == -0.05
    assert d["extension_priority"] is True


def test_adjustment_to_dict_excludes_zeros():
    """to_dict 排除零值和None"""
    adj = StrategyAdjustment()
    assert adj.to_dict() == {}
    assert not adj


def test_trajectory_summary_empty_for_no_trajectory():
    """无轨迹数据时 trajectory_summary 为空"""
    profile = TrajectoryProfile(direction="insufficient_data")
    assert profile.direction == "insufficient_data"
    assert profile.active_patterns == []
    assert not profile.adjustments
