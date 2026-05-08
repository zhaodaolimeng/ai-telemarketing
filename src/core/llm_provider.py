#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Provider - 多模型接口抽象
支持 OpenAI 兼容 API / Anthropic Messages API / Ollama / Mock
使用 httpx 异步调用，统一超时和重试
"""
import random
from typing import List, Dict, Any, Optional

from core.llm_config import LLMConfig

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class LLMUnavailableError(Exception):
    """LLM 不可用时抛出，上层降级处理"""


class LLMProvider:
    """多 provider LLM 接口"""

    # 系统提示模板
    SYSTEM_PROMPT_TEMPLATE = """Anda adalah petugas penagihan yang sopan dan profesional dari perusahaan pinjaman "Extra Uang" di Indonesia.

Peran Anda:
- Anda menelepon untuk menagih pinjaman yang sudah jatuh tempo
- Grup penagihan: {chat_group} ({stage_desc})
- Nama nasabah: {customer_name}

Aturan penting:
1. SELALU gunakan Bahasa Indonesia yang sopan dan profesional
2. JANGAN mengancam, menghina, atau berkata kasar
3. JANGAN menjanjikan penghapusan bunga/denda tanpa otorisasi
4. Tujuan utama: mendapatkan komitmen waktu pembayaran yang jelas (jam/tanggal)
5. Jika nasabah menyebutkan waktu pembayaran, catat dengan baik
6. Obrolan maksimal 2-3 kalimat per giliran
7. Jika nasabah menyebutkan alasan tidak bisa bayar, tawarkan opsi perpanjangan atau cicilan
8. JANGAN pernah mengaku sebagai polisi, OJK, atau instansi pemerintah
9. Akhiri setiap respon dengan pertanyaan tentang waktu pembayaran"""

    def __init__(self, config: LLMConfig):
        self.config = config
        if not HTTPX_AVAILABLE and not config.is_mock:
            raise ImportError("httpx 未安装，无法使用真实 LLM provider: pip install httpx")

    async def generate(
        self,
        conversation_history: List[Dict[str, str]],
        system_prompt: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """调用 LLM 生成回复"""
        context = context or {}

        if self.config.is_mock:
            return await self._mock_generate(conversation_history, context)

        if not system_prompt:
            system_prompt = self._build_system_prompt(context)

        messages = self._build_messages(system_prompt, conversation_history)

        for attempt in range(self.config.max_retries):
            try:
                if self.config.provider == "anthropic":
                    return await self._call_anthropic(messages, system_prompt)
                else:
                    return await self._call_openai_compatible(messages)
            except LLMUnavailableError:
                if attempt < self.config.max_retries - 1:
                    continue
                raise

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        chat_group = context.get("chat_group", "H2")
        stage_desc = {
            "H2": "jatuh tempo awal, pengingat lembut",
            "H1": "jatuh tempo menengah, dorongan lebih tegas",
            "S0": "jatuh tempo lanjut, harus segera diselesaikan",
        }.get(chat_group, "penagihan")
        return self.SYSTEM_PROMPT_TEMPLATE.format(
            chat_group=chat_group,
            stage_desc=stage_desc,
            customer_name=context.get("customer_name", "Pak/Bu"),
        )

    def _build_messages(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        recent = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        for turn in recent:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "agent":
                messages.append({"role": "assistant", "content": content})
            else:
                messages.append({"role": "user", "content": content})
        return messages

    async def _call_openai_compatible(self, messages: List[Dict]) -> str:
        base_url = self.config.api_base or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config.model,
                        "messages": messages,
                        "max_tokens": self.config.max_tokens,
                        "temperature": self.config.temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except httpx.TimeoutException:
                raise LLMUnavailableError("LLM 调用超时")
            except httpx.HTTPStatusError as e:
                raise LLMUnavailableError(f"LLM API 错误: {e.response.status_code}")
            except Exception as e:
                raise LLMUnavailableError(f"LLM 调用失败: {e}")

    async def _call_anthropic(self, messages: List[Dict], system_prompt: str) -> str:
        url = self.config.api_base or "https://api.anthropic.com/v1/messages"

        # Anthropic 格式：system 单独字段，messages 不含 system 角色
        user_assistant_msgs = [m for m in messages if m["role"] != "system"]

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "x-api-key": self.config.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config.model,
                        "system": system_prompt,
                        "messages": user_assistant_msgs,
                        "max_tokens": self.config.max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["content"][0]["text"].strip()
            except httpx.TimeoutException:
                raise LLMUnavailableError("LLM 调用超时")
            except httpx.HTTPStatusError as e:
                raise LLMUnavailableError(f"LLM API 错误: {e.response.status_code}")
            except Exception as e:
                raise LLMUnavailableError(f"LLM 调用失败: {e}")

    async def _mock_generate(
        self,
        conversation_history: List[Dict[str, str]],
        context: Dict[str, Any]
    ) -> str:
        """Mock LLM 回复 - 开发测试用"""
        chat_group = context.get("chat_group", "H2")
        name = context.get("customer_name", "Pak/Bu")

        if chat_group == "H2":
            responses = [
                f"Saya mengerti {name}, apakah bisa bayar besok jam 5?",
                f"Baik {name}, mari kita tentukan waktu yang cocok. Kapan kira-kira bisa bayar?",
                f"Terima kasih {name}, kapan kira-kira Anda bisa melakukan pembayaran?",
                f"Saya paham {name}, bisakah kita tentukan jam berapa Anda bisa transfer?",
            ]
        elif chat_group == "H1":
            responses = [
                f"{name}, kita harus selesaikan ini. Apakah jam 3 besok bisa?",
                f"Saya paham situasinya {name}, bisa kita tentukan waktu yang jelas?",
                f"{name}, tagihan ini sudah cukup lama. Bagaimana kalau kita sepakati waktunya?",
                f"Kami perlu kepastian {name}, kapan kira-kira Anda bisa melakukan pembayaran?",
            ]
        else:  # S0
            responses = [
                f"{name}, ini sudah cukup lama. Bagaimana kalau besok jam 2?",
                f"Kita butuh kepastian {name}, bisa bayar hari ini jam 5?",
                f"{name}, tagihan ini harus segera diselesaikan. Kapan Anda bisa bayar?",
                f"Saran saya {name}, mari kita selesaikan secepatnya. Jam berapa kira-kira?",
            ]

        return random.choice(responses)
