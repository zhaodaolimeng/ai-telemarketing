#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P15-H02: LLM 策略路由（T1 对话前调度）

对话开始前用 LLM 分析用户画像 → 输出策略参数。
缓存 + fallback 保证可用性，LLM 不可用时回退到静态策略。
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import Optional

from .llm_config import LLMConfig
from .strategy_profile import (
    StrategyProfile,
    get_strategy_profile,
    profile_to_dict,
)

logger = logging.getLogger(__name__)

# ─── Prompt 模板（印尼语） ─────────────────────────────────────────────

SYSTEM_PROMPT = """Anda adalah ahli strategi penagihan senior untuk perusahaan pinjaman mikro "Extra Uang" di Indonesia.

Tugas Anda: Menganalisis profil nasabah dan menentukan strategi penagihan yang optimal SEBELUM percakapan dimulai.

## Kerangka Segmentasi
Nasabah dikelompokkan berdasarkan:
1. **new_flag**: 0=nasabah baru (pinjaman pertama), 1=baru jadi nasabah lama (pinjaman ke-2), 2=nasabah lama (3+ pinjaman)
2. **chat_group**: H2=jatuh tempo awal (sekitar due date, risiko rendah), H1=jatuh tempo menengah, S0=jatuh tempo lanjut (NPL, risiko tinggi)

## Parameter Strategi (Output)

1. **approach** (string): pendekatan utama
   - "educate": edukasi tentang kewajiban pembayaran (nasabah baru)
   - "guide": pandu dan ingatkan dengan ramah (nasabah berpengalaman)
   - "maintain": jaga hubungan, nada ringan (nasabah lama riwayat baik)
   - "light": sangat ringan, hampir hanya pengingat
   - "firm": tegas dan jelas tentang konsekuensi
   - "intervene": intervensi kuat, tekanan maksimal

2. **tone** (string): nada komunikasi
   - "soft": lembut dan sabar
   - "neutral": netral dan profesional
   - "firm": tegas dan jelas
   - "urgent": mendesak dan serius

3. **push_intensity** (integer 1-5): intensitas dorongan (1=sangat ringan, 5=sangat kuat)

4. **extension_priority** (boolean): prioritaskan tawaran perpanjangan (true) atau pembayaran penuh (false)

5. **max_push_rounds** (integer 1-5): maksimum ronde dorongan sebelum menyerah

6. **consequence_emphasis** (integer 1-5): penekanan konsekuensi (1=tidak disebut, 5=sangat ditekankan)

7. **education_emphasis** (boolean): tekankan edukasi kontrak dan kewajiban

8. **relationship_emphasis** (boolean): tekankan hubungan baik dan riwayat pembayaran

9. **avoid_tactics** (array of strings): taktik yang HARUS DIHINDARI
   Contoh: ["legal_threats", "aggressive_push", "shaming", "family_mention", "public_embarrassment"]

10. **fallback_approach** (string): strategi cadangan jika pendekatan utama gagal
    Contoh: "offer_extension", "escalate", "partial_payment", "callback_later", "accept_promise"

## Aturan Berdasarkan new_flag
- **new_flag=0 (nasabah baru)**: Prioritaskan EDUKASI, nada lembut-sedang (soft/neutral). Hindari tekanan tinggi (push_intensity ≤ 3).
- **new_flag=1 (transisi)**: Seimbang antara edukasi dan hubungan. Akui riwayat pembayaran pertama.
- **new_flag=2 (nasabah lama)**: H1/H2 → jaga hubungan (relationship_emphasis=true). S0 → bisa lebih tegas (push_intensity 3-4).

## Aturan Berdasarkan chat_group
- **H2 (awal)**: Pengingat lembut, hindari ancaman. Fokus mendapatkan komitmen waktu.
- **H1 (menengah)**: Lebih tegas, sebutkan konsekuensi. Tawarkan solusi (perpanjangan/pembayaran sebagian).
- **S0 (lanjut/NPL)**: Serius, prioritaskan penyelesaian. Tawarkan perpanjangan atau pembayaran sebagian.

## Aturan Berdasarkan DPD (days past due)
- **DPD ≤ 0** (masa tenggang): Sangat ringan, hanya pengingat. push_intensity ≤ 2.
- **DPD 1-7** (ringan): Gunakan parameter standar sesuai segmen.
- **DPD > 7** (dalam): Lebih tegas, prioritaskan solusi (perpanjangan/pembayaran sebagian). extension_priority=true.

## Aturan Tambahan
- **repay_history > 0.7**: Nasabah baik, jaga hubungan. Kurangi push_intensity, tambah relationship_emphasis.
- **repay_history < 0.3**: Waspada, lebih tegas. Tapi tetap profesional.
- **loan_seq ≥ 3**: Nasabah berpengalaman, kurangi education_emphasis.
- **income_ratio < 0.5**: Nasabah dengan beban berat, prioritaskan perpanjangan/pembayaran sebagian.

## Format Output WAJIB
HANYA output JSON object, TANPA markdown code block, TANPA teks lain:
{"approach":"<string>","tone":"<string>","push_intensity":<int>,"extension_priority":<bool>,"max_push_rounds":<int>,"consequence_emphasis":<int>,"education_emphasis":<bool>,"relationship_emphasis":<bool>,"avoid_tactics":["<string>",...],"fallback_approach":"<string>","reasoning":"<string max 100 chars>"}"""

USER_PROMPT_TEMPLATE = """Analisis profil nasabah berikut dan tentukan strategi penagihan yang optimal:

- new_flag: {new_flag} ({new_flag_desc})
- chat_group: {chat_group} ({chat_group_desc})
- dpd: {dpd} hari
- approved_amount: Rp {approved_amount}
- repay_history: {repay_history} (riwayat pelunasan, 0-1)
- income_ratio: {income_ratio} (rasio pendapatan/pinjaman)
- product_name: {product_name}
- marital_status: {marital_status}
- loan_seq: {loan_seq} (jumlah pinjaman)
- call_hour: {call_hour}:00

Tentukan strategi yang optimal."""

NEW_FLAG_DESC = {0: "nasabah baru, pinjaman pertama", 1: "transisi, pinjaman ke-2", 2: "nasabah lama, 3+ pinjaman"}
CHAT_GROUP_DESC = {"H2": "jatuh tempo awal, risiko rendah", "H1": "jatuh tempo menengah", "S0": "jatuh tempo lanjut, NPL, risiko tinggi"}

# ─── 缓存 ──────────────────────────────────────────────────────────────

_CACHE: dict = {}  # {(profile_hash): (StrategyProfile, timestamp)}


def _cache_key(profile: dict) -> str:
    """计算画像缓存键"""
    raw = json.dumps(profile, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_get(key: str, ttl: int) -> Optional[StrategyProfile]:
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[1]) < ttl:
        return entry[0]
    if entry:
        del _CACHE[key]
    return None


def _cache_set(key: str, profile: StrategyProfile):
    _CACHE[key] = (profile, time.time())


# ─── 核心路由器 ─────────────────────────────────────────────────────────

class LlmStrategyRouter:
    """LLM 策略路由器 — 分析用户画像，输出催收策略参数"""

    VALID_APPROACHES = {"educate", "guide", "maintain", "light", "firm", "intervene"}
    VALID_TONES = {"soft", "neutral", "firm", "urgent"}

    def __init__(self, config: LLMConfig):
        self.config = config

    # ── 公共入口 ──────────────────────────────────────────────────────

    def route(self, user_profile: dict) -> StrategyProfile:
        """同步入口：查缓存 → 调 LLM → 解析 → fallback

        Args:
            user_profile: 用户画像字典，至少包含 new_flag, chat_group
        Returns:
            StrategyProfile (LLM 生成或静态 fallback)
        """
        # 检查是否启用
        if not self.config.strategy_routing_enabled:
            logger.info("LLM strategy routing disabled, using static fallback")
            return static_fallback(user_profile)

        # 检查 API key（优先用 config，兜底用环境变量）
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        if self.config.is_mock or not api_key:
            logger.info("LLM not available (mock/no-api-key), using static fallback")
            return static_fallback(user_profile)

        # 查缓存
        key = _cache_key(user_profile)
        cached = _cache_get(key, self.config.cache_ttl_seconds)
        if cached is not None:
            logger.debug(f"LLM strategy cache hit: {key}")
            return cached

        # 调 LLM
        try:
            result = asyncio.run(self._call_llm(user_profile))
        except Exception as e:
            logger.warning(f"LLM strategy routing failed: {e}, using static fallback")
            return static_fallback(user_profile)

        # 解析 + 校验
        try:
            data = self._parse_response(result["raw_text"])
            errors = self._validate(data)
            if errors:
                logger.warning(f"LLM response validation failed: {errors}, using static fallback")
                return static_fallback(user_profile)

            profile = self._dict_to_profile(data, user_profile, result.get("model", ""))
            _cache_set(key, profile)
            return profile
        except Exception as e:
            logger.warning(f"LLM response parse error: {e}, using static fallback")
            return static_fallback(user_profile)

    # ── LLM 调用 ──────────────────────────────────────────────────────

    async def _call_llm(self, user_profile: dict) -> dict:
        """异步 LLM API 调用

        Returns:
            {"raw_text": str, "model": str, "tokens": int}
        """
        import httpx

        api_key = self.config.api_key
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

        base_url = self.config.api_base or os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
        if "deepseek" in base_url.lower():
            base_url = base_url.rstrip("/v1").rstrip("/")

        model = self.config.strategy_routing_model or os.environ.get("LLM_STRATEGY_MODEL", "deepseek-chat")
        timeout = min(self.config.timeout_seconds, 15)

        user_prompt = self._build_user_prompt(user_profile)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"].strip()
            tokens = data.get("usage", {}).get("total_tokens", 0)

            logger.info(f"LLM strategy routing: model={model}, tokens={tokens}")
            return {"raw_text": raw_text, "model": model, "tokens": tokens}

    # ── Prompt 构造 ────────────────────────────────────────────────────

    def _build_user_prompt(self, profile: dict) -> str:
        nf = int(profile.get("new_flag", 0))
        cg = str(profile.get("chat_group", "H2")).upper()
        dpd = int(profile.get("dpd", profile.get("overdue_days", 0)))

        return USER_PROMPT_TEMPLATE.format(
            new_flag=nf,
            new_flag_desc=NEW_FLAG_DESC.get(nf, "tidak diketahui"),
            chat_group=cg,
            chat_group_desc=CHAT_GROUP_DESC.get(cg, "tidak diketahui"),
            dpd=dpd,
            approved_amount=f"{int(profile.get('approved_amount', 500000)):,}",
            repay_history=float(profile.get("repay_history", 0.5)),
            income_ratio=float(profile.get("income_ratio", 1.0)),
            product_name=str(profile.get("product_name", "tidak diketahui")),
            marital_status=str(profile.get("marital_status", "tidak diketahui")),
            loan_seq=int(profile.get("loan_seq", 1)),
            call_hour=int(profile.get("call_hour", 12)),
        )

    # ── 响应解析 ──────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 代码块
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
        if m:
            return json.loads(m.group(1).strip())

        # 尝试提取 { ... } 块
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))

        raise ValueError(f"无法从 LLM 响应中提取 JSON: {raw[:200]}")

    # ── 字段校验 ──────────────────────────────────────────────────────

    def _validate(self, data: dict) -> list[str]:
        errors = []
        if data.get("approach") not in self.VALID_APPROACHES:
            errors.append(f"invalid approach: {data.get('approach')}")
        if data.get("tone") not in self.VALID_TONES:
            errors.append(f"invalid tone: {data.get('tone')}")
        pi = data.get("push_intensity")
        if not isinstance(pi, int) or pi < 1 or pi > 5:
            errors.append(f"push_intensity out of range: {pi}")
        mpr = data.get("max_push_rounds")
        if not isinstance(mpr, int) or mpr < 1 or mpr > 5:
            errors.append(f"max_push_rounds out of range: {mpr}")
        ce = data.get("consequence_emphasis")
        if not isinstance(ce, int) or ce < 1 or ce > 5:
            errors.append(f"consequence_emphasis out of range: {ce}")
        return errors

    # ── Dict → StrategyProfile ─────────────────────────────────────────

    def _dict_to_profile(self, data: dict, user_profile: dict, model: str) -> StrategyProfile:
        segment_key = f"llm_nf={user_profile.get('new_flag', 0)}_{user_profile.get('chat_group', 'H2')}"
        return StrategyProfile(
            segment_key=segment_key,
            segment_name=f"LLM-Routed ({model})",
            approach=data.get("approach", "guide"),
            tone=data.get("tone", "neutral"),
            push_intensity=int(data.get("push_intensity", 2)),
            max_objections=int(data.get("max_objections", 3)),
            extension_fee_ratio=float(data.get("extension_fee_ratio", 0.25)),
            extension_priority=bool(data.get("extension_priority", False)),
            partial_payment_offered=bool(data.get("partial_payment_offered", False)),
            max_push_rounds=int(data.get("max_push_rounds", 3)),
            consequence_emphasis=int(data.get("consequence_emphasis", 2)),
            education_emphasis=bool(data.get("education_emphasis", False)),
            relationship_emphasis=bool(data.get("relationship_emphasis", False)),
            avoid_tactics=list(data.get("avoid_tactics", [])),
            fallback_approach=str(data.get("fallback_approach", "")),
        )


# ─── 静态 Fallback ──────────────────────────────────────────────────────

def static_fallback(user_profile: dict) -> StrategyProfile:
    """从用户画像提取字段，回退到静态策略查表"""
    nf = int(user_profile.get("new_flag", 0))
    cg = str(user_profile.get("chat_group", "H2")).upper()
    dpd = user_profile.get("dpd", user_profile.get("overdue_days", None))
    if dpd is not None:
        dpd = int(dpd)
    return get_strategy_profile(nf, cg, dpd=dpd)


# ─── 便捷函数 ───────────────────────────────────────────────────────────

async def resolve_strategy_profile(
    user_profile: dict,
    llm_config: Optional[LLMConfig] = None,
) -> StrategyProfile:
    """异步便捷函数：根据用户画像解析策略配置

    先尝试 LLM 路由，失败则回退到静态策略。
    """
    if llm_config is None:
        llm_config = LLMConfig.from_env()

    router = LlmStrategyRouter(llm_config)
    return router.route(user_profile)
