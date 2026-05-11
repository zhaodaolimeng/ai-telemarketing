"""组件1: 对话特征提取器 — DialogueLog + UserProfile → 33维特征向量 (25 base + 8 interactions)"""
import zlib
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class UserProfile:
    """用户画像 — 来自 CSV 的高预测力字段"""
    new_flag: int = 0          # 0=新客, 1=新转老, 2=老客
    chat_group: str = "H2"     # H1/H2/S0
    repay_history: float = 0.5 # 历史还清率 [0-1]
    income_ratio: float = 1.0  # monthly_income / approved_amount
    product_name: str = ""     # UangNow/PinjamPro/DuitFast
    marital_status: str = ""   # married/single/divorced/widowed
    loan_seq: int = 1          # 借款次数
    call_hour: int = 12        # 通话时段 0-23
    seats_group: str = ""      # 坐席组 CTM-xxx

    # 以下为用中位值填充的默认值


class DialogueFeatureExtractor:
    """从对话日志 + 用户画像提取 33 维特征向量 (25 base + 8 interactions)"""

    # 枚举编码映射
    PRODUCT_MAP = {"UangNow": 0, "PinjamPro": 1, "DuitFast": 2}
    MARITAL_MAP = {"married": 0, "single": 1, "divorced": 2, "widowed": 3}
    CHAT_GROUP_MAP = {"H1": 0, "H2": 1, "S0": 2}
    APPROACH_MAP = {"educate": 0, "guide": 1, "maintain": 2, "light": 3, "firm": 4, "intervene": 5}
    TONE_MAP = {"soft": 0, "neutral": 1, "firm": 2, "urgent": 3}

    def __init__(self):
        self.missing_counts: dict[str, int] = {}  # 缺失字段统计

    def extract(
        self,
        dialogue_log: dict,
        user_profile: Optional[UserProfile] = None,
        strategy_params: Optional[dict] = None,
    ) -> np.ndarray:
        """
        Args:
            dialogue_log: {
                "turns": int, "push_count": int, "silence_count": int,
                "unknown_count": int, "extension_offered": bool,
                "got_commitment": bool, "commitment_turn": int,
                "objection_types": list[str], "final_state": str,
                "cooperation_signals": int,
            }
            user_profile: UserProfile or None (缺失填中位值)
            strategy_params: {
                "approach": str, "tone": str, "push_intensity": int,
                "extension_priority": bool, "max_push_rounds": int,
                "extension_fee_ratio": float,
            } or None (离线分析时传入)

        Returns:
            np.ndarray shape (33,) float32
        """
        if user_profile is None:
            user_profile = UserProfile()
            self._count_missing("user_profile")
        if strategy_params is None:
            strategy_params = {}
            self._count_missing("strategy_params")

        features = []

        # A. 对话行为特征 (10维)
        features.append(float(dialogue_log.get("turns", 0)))
        features.append(float(dialogue_log.get("push_count", 0)))
        features.append(float(dialogue_log.get("silence_count", 0)))
        features.append(float(dialogue_log.get("unknown_count", 0)))
        features.append(float(dialogue_log.get("extension_offered", False)))
        features.append(float(dialogue_log.get("got_commitment", False)))
        features.append(float(dialogue_log.get("commitment_turn", -1)))
        features.append(float(len(dialogue_log.get("objection_types", []))))
        features.append(float(dialogue_log.get("final_state", "") == "CLOSE"))
        features.append(float(dialogue_log.get("cooperation_signals", 0)))

        # B. 用户画像特征 (9维)
        features.append(float(user_profile.new_flag))
        features.append(float(self.CHAT_GROUP_MAP.get(user_profile.chat_group, 1)))
        features.append(float(user_profile.repay_history))
        features.append(float(user_profile.income_ratio))
        features.append(float(self.PRODUCT_MAP.get(user_profile.product_name, 3)))
        features.append(float(self.MARITAL_MAP.get(user_profile.marital_status, 4)))
        features.append(float(user_profile.loan_seq))
        features.append(float(user_profile.call_hour))
        features.append(float(zlib.adler32(user_profile.seats_group.encode()) % 27 if user_profile.seats_group else 0))

        # C. 策略参数特征 (6维)
        sp = strategy_params
        features.append(float(self.APPROACH_MAP.get(sp.get("approach", "educate"), 0)))
        features.append(float(self.TONE_MAP.get(sp.get("tone", "neutral"), 1)))
        features.append(float(sp.get("push_intensity", 2)))
        features.append(float(sp.get("extension_priority", False)))
        features.append(float(sp.get("max_push_rounds", 3)))
        features.append(float(sp.get("extension_fee_ratio", 0.25)))

        # D. 策略×上下文交互特征 (8维) — 捕获"策略是否匹配客群/对话状态"
        turn_count = float(dialogue_log.get("turns", 0))
        coop = float(dialogue_log.get("cooperation_signals", 0))
        obj_count = float(len(dialogue_log.get("objection_types", [])))
        silence = float(dialogue_log.get("silence_count", 0))
        got_commit = float(dialogue_log.get("got_commitment", False))
        ext_offered = float(dialogue_log.get("extension_offered", False))
        nf = float(user_profile.new_flag)
        cg = float(self.CHAT_GROUP_MAP.get(user_profile.chat_group, 1))

        features.append(float(sp.get("push_intensity", 2)) * coop)              # 25: push强度 × 配合度
        features.append(float(sp.get("push_intensity", 2)) * obj_count)         # 26: push强度 × 异议数
        features.append(float(sp.get("push_intensity", 2)) * silence)           # 27: push强度 × 沉默数
        features.append(float(self.TONE_MAP.get(sp.get("tone", "neutral"), 1)) * nf)         # 28: 语气 × 新客度
        features.append(float(sp.get("extension_priority", False)) * ext_offered) # 29: 展期优先 × 客户要展期
        features.append(float(self.APPROACH_MAP.get(sp.get("approach", "educate"), 0)) * cg) # 30: 策略 × 阶段
        features.append(float(sp.get("push_intensity", 2)) * got_commit)        # 31: push强度 × 已有承诺
        features.append(float(self.TONE_MAP.get(sp.get("tone", "neutral"), 1)) * coop)       # 32: 语气 × 配合度

        if dialogue_log.get("got_commitment") and dialogue_log.get("commitment_turn", -1) == -1:
            self._count_missing("commitment_turn_when_committed")

        return np.array(features, dtype=np.float32)

    def extract_batch(
        self, dialogue_logs: list[dict], user_profiles: list[Optional[UserProfile]],
        strategy_params: Optional[dict] = None,
    ) -> np.ndarray:
        """批量提取特征"""
        if len(dialogue_logs) != len(user_profiles):
            raise ValueError(
                f"Length mismatch: {len(dialogue_logs)} logs vs {len(user_profiles)} profiles"
            )
        return np.array([
            self.extract(log, profile, strategy_params)
            for log, profile in zip(dialogue_logs, user_profiles)
        ])

    @property
    def feature_names(self) -> list[str]:
        """33维特征名称列表 (25 base + 8 interactions)"""
        return [
            # A. 对话行为 (10)
            "turns", "push_count", "silence_count", "unknown_count",
            "extension_offered", "got_commitment", "commitment_turn",
            "objection_type_count", "is_close", "cooperation_signals",
            # B. 用户画像 (9)
            "new_flag", "chat_group_encoded", "repay_history",
            "income_ratio", "product_encoded", "marital_encoded",
            "loan_seq", "call_hour", "seats_encoded",
            # C. 策略参数 (6)
            "approach_encoded", "tone_encoded", "push_intensity",
            "extension_priority", "max_push_rounds", "extension_fee_ratio",
            # D. 策略×上下文交互 (8)
            "push_x_coop", "push_x_objections", "push_x_silence",
            "tone_x_newflag", "extension_x_requested", "approach_x_stage",
            "push_x_commit", "tone_x_coop",
        ]

    def _count_missing(self, field: str):
        self.missing_counts[field] = self.missing_counts.get(field, 0) + 1

    def reset_missing_counts(self):
        self.missing_counts.clear()

    def missing_report(self) -> dict:
        return dict(self.missing_counts)
