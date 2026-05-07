#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频I/O模块
麦克风录音、扬声器播放、音频缓冲区管理，与VAD联动
"""
import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """音频片段"""
    data: np.ndarray
    sample_rate: int = 16000
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def duration(self) -> float:
        return len(self.data) / self.sample_rate

    @property
    def rms(self) -> float:
        """RMS能量"""
        return float(np.sqrt(np.mean(self.data ** 2)))


class RingBuffer:
    """线程安全的环形缓冲区"""

    def __init__(self, max_duration: float = 10.0, sample_rate: int = 16000):
        self.max_samples = int(max_duration * sample_rate)
        self.sample_rate = sample_rate
        self._buffer = np.zeros(self.max_samples, dtype=np.float32)
        self._write_pos = 0
        self._read_pos = 0
        self._lock = threading.Lock()

    def write(self, data: np.ndarray):
        with self._lock:
            n = len(data)
            if n > self.max_samples:
                data = data[-self.max_samples:]
                n = self.max_samples

            end = self._write_pos + n
            if end <= self.max_samples:
                self._buffer[self._write_pos:end] = data
            else:
                split = self.max_samples - self._write_pos
                self._buffer[self._write_pos:] = data[:split]
                self._buffer[:end - self.max_samples] = data[split:]
            self._write_pos = end % self.max_samples

    def read(self, duration: float = None) -> np.ndarray:
        """读取指定时长的最新数据"""
        with self._lock:
            if self._write_pos == self._read_pos:
                return np.array([], dtype=np.float32)

            if duration is not None:
                n = int(duration * self.sample_rate)
            else:
                n = self._write_pos - self._read_pos
                if n < 0:
                    n += self.max_samples

            n = min(n, self.max_samples)
            data = np.zeros(n, dtype=np.float32)
            end = self._write_pos
            start = end - n
            if start >= 0:
                data = self._buffer[start:end].copy()
            else:
                data[:(-start)] = self._buffer[start:]
                data[(-start):] = self._buffer[:end]

            self._read_pos = self._write_pos
            return data

    def read_all(self) -> np.ndarray:
        """读取并清空缓冲区"""
        return self.read()

    def clear(self):
        with self._lock:
            self._read_pos = self._write_pos

    def __len__(self) -> int:
        with self._lock:
            if self._write_pos >= self._read_pos:
                return self._write_pos - self._read_pos
            return self.max_samples - self._read_pos + self._write_pos


class AudioInput:
    """
    麦克风录音输入
    基于 sounddevice.InputStream 的非阻塞录音
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        block_size: int = 1600,
        device: Optional[int] = None,
        ring_buffer_duration: float = 10.0,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.device = device
        self.buffer = RingBuffer(max_duration=ring_buffer_duration, sample_rate=sample_rate)
        self._stream = None
        self._running = False
        self._recording = False
        self._recorded_chunks: list = []

    def _audio_callback(self, indata, frames, timestamp, status):
        """sounddevice 回调"""
        if status:
            logger.warning(f"Audio input status: {status}")
        audio = indata[:, 0].copy() if indata.shape[1] > 0 else indata.flatten().copy()
        self.buffer.write(audio)
        if self._recording:
            self._recorded_chunks.append(AudioChunk(data=audio, sample_rate=self.sample_rate))

    def start(self):
        """启动录音流"""
        try:
            import sounddevice as sd
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                device=self.device,
                callback=self._audio_callback,
                dtype=np.float32,
            )
            self._stream.start()
            self._running = True
            logger.info(f"Audio input started: {self.sample_rate}Hz, {self.channels}ch")
        except ImportError:
            logger.error("sounddevice not installed")
        except Exception as e:
            logger.error(f"Failed to start audio input: {e}")

    def stop(self):
        """停止录音流"""
        self._running = False
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("Audio input stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def start_recording(self):
        """开始累积录音（用于完整语音段保存）"""
        self._recorded_chunks.clear()
        self._recording = True

    def stop_recording(self) -> np.ndarray:
        """停止录音，返回累积的音频"""
        self._recording = False
        if not self._recorded_chunks:
            return np.array([], dtype=np.float32)
        audio = np.concatenate([c.data for c in self._recorded_chunks])
        self._recorded_chunks.clear()
        return audio

    def read(self, duration: float = None) -> np.ndarray:
        """从缓冲区读取最新音频"""
        return self.buffer.read(duration)

    def read_all(self) -> np.ndarray:
        """读取并清空缓冲区"""
        return self.buffer.read_all()

    def current_rms(self) -> float:
        """当前缓冲区的RMS能量"""
        data = self.buffer.read()
        if len(data) == 0:
            return 0.0
        return float(np.sqrt(np.mean(data ** 2)))

    @staticmethod
    def list_devices():
        """列出可用音频设备"""
        try:
            import sounddevice as sd
            return sd.query_devices()
        except ImportError:
            return "sounddevice not installed"


class AudioOutput:
    """
    扬声器播放输出
    播放TTS生成的音频文件
    """

    def __init__(self, sample_rate: int = 16000, device: Optional[int] = None):
        self.sample_rate = sample_rate
        self.device = device
        self._playing = False
        self._stream = None
        self._stop_requested = False
        self._play_thread: Optional[threading.Thread] = None

    def play_file(self, file_path: str, blocking: bool = False) -> bool:
        """
        播放音频文件

        Args:
            file_path: 音频文件路径 (.wav, .mp3)
            blocking: 是否阻塞直到播放完成

        Returns:
            是否成功开始播放
        """
        try:
            import soundfile as sf
            data, sr = sf.read(file_path, dtype='float32')
            if data.ndim > 1:
                data = data[:, 0]
            return self.play_array(data, sr, blocking)
        except ImportError:
            logger.warning("soundfile not installed, trying scipy")
            try:
                from scipy.io import wavfile
                sr, data = wavfile.read(file_path)
                data = data.astype(np.float32) / 32768.0
                if data.ndim > 1:
                    data = data[:, 0]
                return self.play_array(data, sr, blocking)
            except ImportError:
                logger.error("Neither soundfile nor scipy available")
                return False

    def play_array(self, data: np.ndarray, sample_rate: int = None, blocking: bool = False) -> bool:
        """
        播放numpy音频数组

        Args:
            data: float32 array
            sample_rate: 采样率，默认使用实例的sample_rate
            blocking: 是否阻塞

        Returns:
            是否成功
        """
        sr = sample_rate or self.sample_rate
        data = data.astype(np.float32)

        if blocking:
            return self._play_blocking(data, sr)

        self._stop_requested = False
        self._play_thread = threading.Thread(
            target=self._play_blocking,
            args=(data, sr),
            daemon=True,
        )
        self._play_thread.start()
        return True

    def _play_blocking(self, data: np.ndarray, sample_rate: int) -> bool:
        try:
            import sounddevice as sd
            self._playing = True

            chunk_size = 1024
            pos = 0
            while pos < len(data) and not self._stop_requested:
                end = min(pos + chunk_size, len(data))
                sd.play(data[pos:end], samplerate=sample_rate, device=self.device, blocking=True)
                pos = end

            if self._stop_requested:
                sd.stop()

            self._playing = False
            return True
        except ImportError:
            logger.error("sounddevice not installed")
            return False
        except Exception as e:
            logger.error(f"Playback error: {e}")
            self._playing = False
            return False

    def stop(self):
        """停止播放"""
        self._stop_requested = True
        try:
            import sounddevice as sd
            sd.stop()
        except ImportError:
            pass

    @property
    def is_playing(self) -> bool:
        return self._playing

    def wait_done(self, timeout: float = None):
        """等待播放完成"""
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout)

    @staticmethod
    def list_devices():
        try:
            import sounddevice as sd
            return sd.query_devices()
        except ImportError:
            return "sounddevice not installed"
