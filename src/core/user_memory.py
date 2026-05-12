#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P15-D01: 跨会话用户记忆

UserMemory: 用户历史会话摘要
UserMemoryStore: 从 DB 查询历史会话，构建 UserMemory
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UserMemory:
    """用户跨会话历史记忆"""
    phone: str
    total_sessions: int = 0
    successful_sessions: int = 0
    failed_sessions: int = 0
    last_session_date: Optional[str] = None
    last_session_result: Optional[str] = None  # "success" | "failed" | "abandoned"
    last_commit_time: Optional[str] = None
    avg_turns_per_session: float = 0.0

    # P15-H05: T3 跨通话轨迹
    trajectory_direction: Optional[str] = None
    trajectory_patterns: list = field(default_factory=list)
    trajectory_adjustments: Optional[dict] = None

    @property
    def promise_fulfillment_rate(self) -> float:
        if self.total_sessions <= 0:
            return 0.0
        return self.successful_sessions / self.total_sessions

    @property
    def has_previous_sessions(self) -> bool:
        return self.total_sessions > 0

    @property
    def previously_promised_but_failed(self) -> bool:
        """P15-B02: 上次承诺了时间但未还款"""
        return (
            self.last_session_result == "failed"
            and self.last_commit_time is not None
        )

    @property
    def is_low_trust(self) -> bool:
        """历史履约率低于 50%（至少 2 次会话才判定）"""
        return (
            self.total_sessions >= 2
            and self.promise_fulfillment_rate < 0.5
        )

    # P15-H05: T3 轨迹属性

    @property
    def has_trajectory(self) -> bool:
        return self.trajectory_direction is not None

    @property
    def trajectory_summary(self) -> str:
        if not self.has_trajectory:
            return ""
        patterns = ", ".join(self.trajectory_patterns) if self.trajectory_patterns else "none"
        return f"direction={self.trajectory_direction}, patterns=[{patterns}]"


class UserMemoryStore:
    """从数据库查询用户历史会话，构建 UserMemory"""

    def __init__(self, db):
        self.db = db

    def load(self, phone: str, compute_trajectory: bool = False) -> Optional[UserMemory]:
        """查询用户历史会话，构建记忆。无历史返回 None。

        Args:
            phone: 用户手机号
            compute_trajectory: 是否计算跨通话轨迹画像 (P15-H05 T3)
        """
        from src.api.database import ChatSession as DBChatSession

        sessions = (
            self.db.query(DBChatSession)
            .filter(DBChatSession.customer_phone == phone)
            .order_by(DBChatSession.created_at.asc())
            .all()
        )

        if not sessions:
            logger.debug(f"UserMemory: no history for phone={phone}")
            return None

        total = len(sessions)
        successful = sum(1 for s in sessions if s.is_successful)
        failed = sum(1 for s in sessions if s.is_finished and not s.is_successful)

        last = sessions[-1]  # 升序排列，最后一个是最新的

        memory = UserMemory(
            phone=phone,
            total_sessions=total,
            successful_sessions=successful,
            failed_sessions=failed,
            last_session_date=last.created_at,
            last_session_result=(
                "success" if last.is_successful
                else "failed" if last.is_finished
                else "abandoned"
            ),
            last_commit_time=last.commit_time,
            avg_turns_per_session=(
                sum(s.conversation_length or 0 for s in sessions) / total
            ),
        )

        # P15-H05: T3 跨通话轨迹分析
        if compute_trajectory and total >= 2:
            snapshots = self._build_snapshots(sessions)
            from .trajectory_analyzer import TrajectoryAnalyzer
            analyzer = TrajectoryAnalyzer()
            traj = analyzer.analyze(snapshots)
            memory.trajectory_direction = traj.direction
            memory.trajectory_patterns = traj.active_patterns
            memory.trajectory_adjustments = traj.adjustments.to_dict()
            logger.info(
                f"T3 trajectory: phone={phone}, {memory.trajectory_summary}"
            )

        logger.info(
            f"UserMemory loaded: phone={phone}, sessions={total}, "
            f"success_rate={memory.promise_fulfillment_rate:.0%}, "
            f"last_result={memory.last_session_result}"
        )
        return memory

    def _build_snapshots(self, sessions) -> list:
        """P15-H05: 将 DB ChatSession 列表转为 CallSnapshot 序列（升序）"""
        from .trajectory_analyzer import CallSnapshot

        snapshots = []
        for i, s in enumerate(sessions):
            result = (
                "success" if s.is_successful
                else "failed" if s.is_finished
                else "abandoned"
            )
            snapshots.append(CallSnapshot(
                call_index=i,
                call_date=s.created_at or "",
                new_flag=0,  # DB 未存储 new_flag，默认新客
                chat_group=s.chat_group or "H2",
                dpd=0,
                call_result=result,
                got_commitment=s.commit_time is not None,
                turns=s.conversation_length or 0,
                loan_no="",
            ))
        return snapshots
