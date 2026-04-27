#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控指标模块
用于收集和展示系统运行指标
"""
import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json
from pathlib import Path


@dataclass
class MetricValue:
    """指标值"""
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """指标摘要"""
    name: str
    count: int
    min: float
    max: float
    avg: float
    sum: float
    latest: Optional[float] = None
    tags: Dict[str, List[str]] = field(default_factory=dict)


class MetricsCollector:
    """
    指标收集器
    """

    def __init__(self, max_history: int = 10000):
        self._metrics: Dict[str, List[MetricValue]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._timers: Dict[str, float] = {}
        self._max_history = max_history
        self._start_time = time.time()

    def increment(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """
        增加计数器

        Args:
            name: 指标名称
            value: 增加值
            tags: 标签
        """
        self._counters[name] += value
        self.record(name, float(self._counters[name]), tags)

    def decrement(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """
        减少计数器

        Args:
            name: 指标名称
            value: 减少值
            tags: 标签
        """
        self._counters[name] -= value
        self.record(name, float(self._counters[name]), tags)

    def record(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        记录指标值

        Args:
            name: 指标名称
            value: 指标值
            tags: 标签
        """
        metric = MetricValue(
            value=value,
            timestamp=time.time(),
            tags=tags or {}
        )

        history = self._metrics[name]
        history.append(metric)

        # 限制历史长度
        if len(history) > self._max_history:
            self._metrics[name] = history[-self._max_history:]

    def start_timer(self, name: str) -> str:
        """
        开始计时器

        Args:
            name: 计时器名称

        Returns:
            计时器ID
        """
        timer_id = f"{name}_{int(time.time() * 1000)}"
        self._timers[timer_id] = time.time()
        return timer_id

    def stop_timer(self, timer_id: str, tags: Optional[Dict[str, str]] = None) -> float:
        """
        停止计时器并记录

        Args:
            timer_id: 计时器ID
            tags: 标签

        Returns:
            耗时（秒）
        """
        if timer_id not in self._timers:
            return 0.0

        duration = time.time() - self._timers[timer_id]
        del self._timers[timer_id]

        self.record(f"{timer_id.split('_')[0]}_duration", duration, tags)
        return duration

    def get_counter(self, name: str) -> int:
        """获取计数器值"""
        return self._counters.get(name, 0)

    def get_metric_names(self) -> List[str]:
        """获取所有指标名称"""
        return list(self._metrics.keys())

    def get_summary(self, name: str, since: Optional[float] = None) -> Optional[MetricSummary]:
        """
        获取指标摘要

        Args:
            name: 指标名称
            since: 从何时开始（时间戳）

        Returns:
            指标摘要
        """
        if name not in self._metrics:
            return None

        values = self._metrics[name]

        if since:
            values = [v for v in values if v.timestamp >= since]

        if not values:
            return None

        numeric_values = [v.value for v in values]

        # 收集标签
        tags = defaultdict(list)
        for v in values:
            for k, vv in v.tags.items():
                if vv not in tags[k]:
                    tags[k].append(vv)

        return MetricSummary(
            name=name,
            count=len(numeric_values),
            min=min(numeric_values),
            max=max(numeric_values),
            avg=sum(numeric_values) / len(numeric_values),
            sum=sum(numeric_values),
            latest=values[-1].value,
            tags=dict(tags)
        )

    def get_all_summaries(self, since: Optional[float] = None) -> Dict[str, MetricSummary]:
        """获取所有指标摘要"""
        summaries = {}
        for name in self._metrics.keys():
            summary = self.get_summary(name, since)
            if summary:
                summaries[name] = summary
        return summaries

    def get_uptime(self) -> float:
        """获取运行时间（秒）"""
        return time.time() - self._start_time

    def reset(self):
        """重置所有指标"""
        self._metrics.clear()
        self._counters.clear()
        self._timers.clear()
        self._start_time = time.time()


# 全局指标收集器实例
collector = MetricsCollector()


class ConversationMetrics:
    """
    对话相关指标
    """

    @staticmethod
    def on_session_start(chat_group: str):
        """会话开始"""
        collector.increment("sessions_total", tags={"chat_group": chat_group})
        collector.increment("sessions_active", tags={"chat_group": chat_group})

    @staticmethod
    def on_session_end(chat_group: str, success: bool):
        """会话结束"""
        collector.decrement("sessions_active", tags={"chat_group": chat_group})
        if success:
            collector.increment("sessions_successful", tags={"chat_group": chat_group})
        else:
            collector.increment("sessions_failed", tags={"chat_group": chat_group})

    @staticmethod
    def on_turn(chat_group: str, state: str):
        """对话回合"""
        collector.increment("turns_total", tags={"chat_group": chat_group, "state": state})

    @staticmethod
    def on_tts_request():
        """TTS请求"""
        collector.increment("tts_requests_total")

    @staticmethod
    def on_interruption():
        """打断事件"""
        collector.increment("interruptions_total")


class PerformanceMetrics:
    """
    性能相关指标
    """

    @staticmethod
    def start_api_call(endpoint: str) -> str:
        """开始API调用计时"""
        return collector.start_timer(f"api_{endpoint}")

    @staticmethod
    def end_api_call(timer_id: str, endpoint: str, success: bool):
        """结束API调用计时"""
        collector.stop_timer(timer_id, tags={"endpoint": endpoint, "success": str(success)})
        if success:
            collector.increment("api_calls_success", tags={"endpoint": endpoint})
        else:
            collector.increment("api_calls_error", tags={"endpoint": endpoint})

    @staticmethod
    def record_latency(endpoint: str, latency_ms: float):
        """记录延迟"""
        collector.record(f"api_latency_ms", latency_ms, tags={"endpoint": endpoint})


def get_system_metrics() -> Dict[str, Any]:
    """
    获取系统指标

    Returns:
        系统指标字典
    """
    uptime = collector.get_uptime()
    summaries = collector.get_all_summaries()

    # 基本信息
    metrics = {
        "uptime_seconds": uptime,
        "uptime_formatted": str(int(uptime // 3600)).zfill(2) + ":" +
                          str(int((uptime % 3600) // 60)).zfill(2) + ":" +
                          str(int(uptime % 60)).zfill(2),
        "counters": dict(collector._counters),
        "summaries": {}
    }

    # 摘要信息
    for name, summary in summaries.items():
        metrics["summaries"][name] = {
            "count": summary.count,
            "min": summary.min,
            "max": summary.max,
            "avg": round(summary.avg, 3),
            "sum": summary.sum,
            "latest": summary.latest
        }

    return metrics


if __name__ == "__main__":
    print("监控指标模块加载成功")

    # 测试指标收集
    collector.increment("test_counter")
    collector.increment("test_counter")
    collector.record("test_metric", 10.5)
    collector.record("test_metric", 20.5)

    print(f"计数器值: {collector.get_counter('test_counter')}")
    print(f"指标名称: {collector.get_metric_names()}")

    summary = collector.get_summary("test_metric")
    if summary:
        print(f"指标摘要: count={summary.count}, avg={summary.avg}, min={summary.min}, max={summary.max}")

    print("系统指标:", json.dumps(get_system_metrics(), indent=2, ensure_ascii=False))
