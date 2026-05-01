#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音活动检测 (VAD) 模块
用于检测音频流中的语音活动
"""
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import time


class VADState(Enum):
    """VAD状态"""
    SILENCE = "silence"
    VOICE = "voice"
    UNKNOWN = "unknown"


@dataclass
class VADResult:
    """VAD检测结果"""
    state: VADState
    confidence: float
    timestamp: float
    duration: float = 0.0


class SimpleEnergyVAD:
    """
    基于能量的简单VAD检测器
    适用于实时语音活动检测
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        energy_threshold: float = 0.01,
        silence_frames: int = 10,
        voice_frames: int = 3
    ):
        """
        初始化VAD检测器

        Args:
            sample_rate: 采样率 (Hz)
            frame_duration_ms: 帧长度 (毫秒)
            energy_threshold: 能量阈值
            silence_frames: 连续静音帧数才判定为静音
            voice_frames: 连续语音帧数才判定为语音
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.energy_threshold = energy_threshold
        self.silence_frames = silence_frames
        self.voice_frames = voice_frames

        self.state = VADState.UNKNOWN
        self.silence_counter = 0
        self.voice_counter = 0
        self.start_time = None

    def _calculate_energy(self, audio_frame: np.ndarray) -> float:
        """
        计算音频帧的能量

        Args:
            audio_frame: 音频帧数据

        Returns:
            能量值
        """
        if len(audio_frame) == 0:
            return 0.0

        # 归一化
        max_val = np.max(np.abs(audio_frame))
        if max_val > 0:
            audio_frame = audio_frame / max_val

        # 计算能量
        energy = np.mean(audio_frame ** 2)
        return energy

    def process_frame(self, audio_frame: np.ndarray) -> VADResult:
        """
        处理单个音频帧

        Args:
            audio_frame: 音频帧数据

        Returns:
            VAD检测结果
        """
        energy = self._calculate_energy(audio_frame)
        timestamp = time.time()

        if energy > self.energy_threshold:
            self.voice_counter += 1
            self.silence_counter = 0

            if self.voice_counter >= self.voice_frames:
                if self.state != VADState.VOICE:
                    self.start_time = timestamp
                self.state = VADState.VOICE
        else:
            self.silence_counter += 1
            self.voice_counter = 0

            if self.silence_counter >= self.silence_frames:
                if self.state == VADState.VOICE and self.start_time:
                    duration = timestamp - self.start_time
                else:
                    duration = 0.0
                self.state = VADState.SILENCE
                self.start_time = None

        # 计算置信度
        if self.state == VADState.VOICE:
            confidence = min(1.0, energy / (self.energy_threshold * 2))
        elif self.state == VADState.SILENCE:
            confidence = min(1.0, (self.energy_threshold - energy) / self.energy_threshold)
        else:
            confidence = 0.5

        duration = timestamp - self.start_time if self.start_time else 0.0

        return VADResult(
            state=self.state,
            confidence=confidence,
            timestamp=timestamp,
            duration=duration
        )

    def reset(self):
        """重置VAD状态"""
        self.state = VADState.UNKNOWN
        self.silence_counter = 0
        self.voice_counter = 0
        self.start_time = None


class VADAnalyzer:
    """
    VAD分析器 - 用于分析完整音频文件
    """

    def __init__(self, vad: Optional[SimpleEnergyVAD] = None):
        self.vad = vad or SimpleEnergyVAD()

    def analyze_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> List[Tuple[float, float, VADState]]:
        """
        分析完整音频数据

        Args:
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            语音活动片段列表 [(start_time, end_time, state)]
        """
        frame_size = self.vad.frame_size
        segments = []
        current_state = VADState.UNKNOWN
        segment_start = 0.0

        num_frames = len(audio_data) // frame_size

        for i in range(num_frames):
            start_idx = i * frame_size
            end_idx = start_idx + frame_size
            frame = audio_data[start_idx:end_idx]

            result = self.vad.process_frame(frame)
            timestamp = i * self.vad.frame_duration_ms / 1000.0

            if result.state != current_state:
                if current_state != VADState.UNKNOWN:
                    segments.append((segment_start, timestamp, current_state))
                current_state = result.state
                segment_start = timestamp

        # 添加最后一个片段
        if current_state != VADState.UNKNOWN:
            end_time = num_frames * self.vad.frame_duration_ms / 1000.0
            segments.append((segment_start, end_time, current_state))

        return segments

    def get_voice_segments(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> List[Tuple[float, float]]:
        """
        获取语音活动片段

        Args:
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            语音片段列表 [(start_time, end_time)]
        """
        segments = self.analyze_audio(audio_data, sample_rate)
        return [(s, e) for s, e, state in segments if state == VADState.VOICE]

    def calculate_speech_ratio(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> float:
        """
        计算语音占比

        Args:
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            语音占比 (0.0 - 1.0)
        """
        segments = self.analyze_audio(audio_data, sample_rate)
        total_duration = len(audio_data) / sample_rate

        if total_duration == 0:
            return 0.0

        speech_duration = sum(e - s for s, e, state in segments if state == VADState.VOICE)
        return speech_duration / total_duration


# 简单测试
if __name__ == "__main__":
    print("VAD模块加载成功")

    # 创建VAD检测器
    vad = SimpleEnergyVAD()
    print(f"采样率: {vad.sample_rate}")
    print(f"帧大小: {vad.frame_size}")
    print(f"能量阈值: {vad.energy_threshold}")

    # 测试静音帧
    print("\n--- 测试静音帧 ---")
    silence_frame = np.zeros(vad.frame_size, dtype=np.float32)
    result = vad.process_frame(silence_frame)
    print(f"状态: {result.state}, 置信度: {result.confidence:.2f}")

    # 测试语音帧（模拟噪声）
    print("\n--- 测试语音帧 ---")
    voice_frame = np.random.randn(vad.frame_size).astype(np.float32) * 0.1
    result = vad.process_frame(voice_frame)
    print(f"状态: {result.state}, 置信度: {result.confidence:.2f}")

    print("\nVAD模块测试完成")
