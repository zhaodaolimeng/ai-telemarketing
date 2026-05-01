#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS引擎抽象层
支持多种TTS后端：Edge-TTS、Coqui-TTS等
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass
import time


@dataclass
class TTSResult:
    """TTS合成结果"""
    text: str
    audio_file: Optional[str] = None
    audio_data: Optional[bytes] = None
    duration: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    engine_name: str = ""


class TTSEngine(ABC):
    """TTS引擎抽象基类"""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_file: Optional[str] = None,
        voice: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        """
        合成语音

        Args:
            text: 要合成的文本
            output_file: 输出文件路径
            voice: 语音类型
            **kwargs: 其他参数

        Returns:
            TTS合成结果
        """
        pass

    @abstractmethod
    async def list_voices(self, locale: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出可用语音

        Args:
            locale: 语言区域

        Returns:
            语音列表
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        pass

    @abstractmethod
    def get_engine_name(self) -> str:
        """获取引擎名称"""
        pass


class EdgeTTSEngine(TTSEngine):
    """
    Edge-TTS引擎实现
    """

    def __init__(self, default_voice: str = "id-ID-ArdiNeural"):
        self.default_voice = default_voice
        self._available = False
        self._edge_tts = None

        try:
            import edge_tts
            self._edge_tts = edge_tts
            self._available = True
        except ImportError:
            print("警告: edge-tts未安装")

    async def synthesize(
        self,
        text: str,
        output_file: Optional[str] = None,
        voice: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        if not self._available:
            return TTSResult(
                text=text,
                success=False,
                error_message="Edge-TTS不可用",
                engine_name=self.get_engine_name()
            )

        start_time = time.time()
        voice = voice or self.default_voice

        try:
            if output_file is None:
                output_dir = Path("data/tts_output")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S_%f")
                output_file = str(output_dir / f"tts_{timestamp}.mp3")

            communicate = self._edge_tts.Communicate(text, voice)
            await communicate.save(output_file)

            duration = time.time() - start_time

            return TTSResult(
                text=text,
                audio_file=output_file,
                duration=duration,
                success=True,
                engine_name=self.get_engine_name()
            )

        except Exception as e:
            return TTSResult(
                text=text,
                success=False,
                error_message=str(e),
                engine_name=self.get_engine_name()
            )

    async def list_voices(self, locale: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._available:
            return []

        try:
            voices = await self._edge_tts.list_voices()
            if locale:
                voices = [v for v in voices if locale in v.get("Locale", "")]
            return voices
        except:
            return []

    def is_available(self) -> bool:
        return self._available

    def get_engine_name(self) -> str:
        return "edge_tts"


class CoquiTTSEngine(TTSEngine):
    """
    Coqui-TTS引擎实现
    """

    def __init__(self, model_name: str = "tts_models/id/css10/vits"):
        self.model_name = model_name
        self._available = False
        self._tts = None
        self._model = None

        try:
            import TTS
            self._tts = TTS
            self._available = True
            print("Coqui-TTS已加载")
        except ImportError:
            print("提示: Coqui-TTS未安装，使用pip install TTS安装")

    async def synthesize(
        self,
        text: str,
        output_file: Optional[str] = None,
        voice: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        if not self._available:
            return TTSResult(
                text=text,
                success=False,
                error_message="Coqui-TTS不可用",
                engine_name=self.get_engine_name()
            )

        start_time = time.time()

        try:
            # 延迟加载模型
            if self._model is None:
                from TTS.api import TTS as CoquiTTS
                self._model = CoquiTTS(model_name=self.model_name, progress_bar=False)

            if output_file is None:
                output_dir = Path("data/tts_output")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S_%f")
                output_file = str(output_dir / f"coqui_{timestamp}.wav")

            # 使用线程池执行同步操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._model.tts_to_file(text=text, file_path=output_file)
            )

            duration = time.time() - start_time

            return TTSResult(
                text=text,
                audio_file=output_file,
                duration=duration,
                success=True,
                engine_name=self.get_engine_name()
            )

        except Exception as e:
            return TTSResult(
                text=text,
                success=False,
                error_message=str(e),
                engine_name=self.get_engine_name()
            )

    async def list_voices(self, locale: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._available:
            return []

        try:
            models = self._tts.list_models()
            voices = []
            for model in models:
                if locale and locale not in model:
                    continue
                voices.append({
                    "Name": model,
                    "Locale": model.split("/")[1] if len(model.split("/")) > 1 else "",
                    "Model": model
                })
            return voices
        except:
            return []

    def is_available(self) -> bool:
        return self._available

    def get_engine_name(self) -> str:
        return "coqui_tts"


class TTSManager:
    """
    TTS管理器 - 支持多引擎切换
    """

    def __init__(self):
        self.engines: Dict[str, TTSEngine] = {}
        self.default_engine: Optional[str] = None

        # 注册默认引擎
        self._register_default_engines()

    def _register_default_engines(self):
        """注册默认引擎"""
        # Edge-TTS（优先）
        edge_engine = EdgeTTSEngine()
        if edge_engine.is_available():
            self.engines[edge_engine.get_engine_name()] = edge_engine
            if self.default_engine is None:
                self.default_engine = edge_engine.get_engine_name()

        # Coqui-TTS
        coqui_engine = CoquiTTSEngine()
        if coqui_engine.is_available():
            self.engines[coqui_engine.get_engine_name()] = coqui_engine
            if self.default_engine is None:
                self.default_engine = coqui_engine.get_engine_name()

    def register_engine(self, engine: TTSEngine, set_default: bool = False):
        """注册TTS引擎"""
        self.engines[engine.get_engine_name()] = engine
        if set_default or self.default_engine is None:
            self.default_engine = engine.get_engine_name()

    def get_engine(self, engine_name: Optional[str] = None) -> Optional[TTSEngine]:
        """获取TTS引擎"""
        if engine_name is None:
            engine_name = self.default_engine

        return self.engines.get(engine_name)

    async def synthesize(
        self,
        text: str,
        output_file: Optional[str] = None,
        voice: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs
    ) -> TTSResult:
        """合成语音（自动选择可用引擎）"""
        tts_engine = self.get_engine(engine)

        if tts_engine is None:
            return TTSResult(
                text=text,
                success=False,
                error_message="没有可用的TTS引擎"
            )

        return await tts_engine.synthesize(text, output_file, voice, **kwargs)

    def get_available_engines(self) -> List[str]:
        """获取可用引擎列表"""
        return [name for name, engine in self.engines.items() if engine.is_available()]


# 简单测试
if __name__ == "__main__":
    print("TTS引擎模块加载成功")

    manager = TTSManager()
    print(f"可用引擎: {manager.get_available_engines()}")
    print(f"默认引擎: {manager.default_engine}")
