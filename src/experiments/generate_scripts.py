#!/usr/bin/env python3
"""
LLM 批量话术生成工具 (P15-H01)

流水线: LLM生成 → JSON输出 → 人工审核 → 导入script_lib

用法:
    # 生成所有49个类别的话术变体（每个类别20条）
    python3 -m src.experiments.generate_scripts --all --count 20

    # 生成指定类别
    python3 -m src.experiments.generate_scripts --categories push,ask_time,greeting --count 20

    # 预览模式：只打印prompt不调用API
    python3 -m src.experiments.generate_scripts --categories silence_engage --dry-run

    # 指定输出文件
    python3 -m src.experiments.generate_scripts --all --count 20 --output data/scripts_generated.json

环境变量:
    OPENAI_API_KEY  - LLM API key
    OPENAI_BASE_URL - LLM API base URL（默认 https://api.openai.com/v1）
    LLM_MODEL       - 模型名称（默认 gpt-4o）
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

from src.core.chatbot import CollectionChatBot


# ============================================================
# 话术类别元数据
# ============================================================

CATEGORY_META = {
    # ── 开场与身份确认 ──
    "greeting": {
        "purpose": "开场问候语，接通电话后的第一句话",
        "groups": ["H2", "H1", "S0"],
        "vars": [],
        "max_words": 8,
        "tone": "H2: 轻松友好 | H1: 礼貌中性 | S0: 正式干脆",
        "notes": "仅问候，不涉及任何业务信息"
    },
    "identity_verify": {
        "purpose": "确认对方是否为借款人本人",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}"],
        "max_words": 25,
        "tone": "H2: 温和礼貌 | H1: 礼貌直接 | S0: 正式坚定",
        "notes": "必须提及公司名Extra Uang和借款人名字"
    },

    # ── 核心流程 ──
    "purpose": {
        "purpose": "告知来电目的：账单已逾期，需要还款",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}", "{amount}", "{days}"],
        "max_words": 30,
        "tone": "H2: 提醒为主 | H1: 强调紧迫 | S0: 严肃告知",
        "notes": "需包含金额和逾期天数。H2不施压，H1暗示后果，S0强调严重性"
    },
    "ask_time": {
        "purpose": "询问用户何时能还款",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}", "{amount}"],
        "max_words": 20,
        "tone": "H2: 开放式友好 | H1: 引导式催促 | S0: 要求式追问",
        "notes": "核心转化点。H2可温和开放，S0需施加时间压力"
    },
    "push": {
        "purpose": "催促用户给出具体的还款时间点",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}"],
        "max_words": 15,
        "tone": "H2: 温和提醒 | H1: 认真追问 | S0: 坚定施压",
        "notes": "追问具体时间（jam berapa/hari apa），不给用户模糊空间"
    },
    "push_time_unknown": {
        "purpose": "用户给的时间模糊/不明确时的追问",
        "groups": ["*"],
        "vars": [],
        "max_words": 18,
        "tone": "礼貌但坚持",
        "notes": "用户说了nanti/besok等模糊词后的追问，要求精确到具体时间"
    },
    "commit_time": {
        "purpose": "确认用户的还款时间承诺",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}", "{time}"],
        "max_words": 18,
        "tone": "H2: 肯定鼓励 | H1: 确认记录 | S0: 严肃确认",
        "notes": "复述用户承诺的时间，表示已记录，建立心理锚定"
    },
    "confirm_commit": {
        "purpose": "要求用户再次确认还款承诺",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}", "{time}"],
        "max_words": 20,
        "tone": "H2: 友好确认 | H1: 认真确认 | S0: 重申重要性",
        "notes": "二次确认以加固承诺，降低虚假承诺概率"
    },
    "wait": {
        "purpose": "告知等待用户还款的过渡语",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{time}"],
        "max_words": 18,
        "tone": "礼貌期待",
        "notes": "接在commit_time之后，过渡到结束语"
    },

    # ── 结束语 ──
    "closing": {
        "purpose": "正常结束对话（拿到还款承诺后）",
        "groups": ["H2", "H1", "S0"],
        "vars": [],
        "max_words": 20,
        "tone": "H2: 温暖感谢 | H1: 礼貌期待 | S0: 正式提醒",
        "notes": "感谢接听+期待还款+祝福语"
    },
    "closing_busy": {
        "purpose": "用户忙/不方便说话时的结束语",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "理解+约定后续",
        "notes": "不强迫，给用户台阶下，约定稍后联系"
    },
    "closing_wrong_number": {
        "purpose": "打错电话/非本人时的结束语",
        "groups": ["*"],
        "vars": [],
        "max_words": 15,
        "tone": "礼貌道歉",
        "notes": "简短道歉并结束，不纠缠"
    },
    "close_agree_pay": {
        "purpose": "用户口头同意后确认等待的结束语",
        "groups": ["*"],
        "vars": [],
        "max_words": 15,
        "tone": "确认+感谢",
        "notes": "简短确认等待付款"
    },
    "close_general": {
        "purpose": "通用结束语",
        "groups": ["*"],
        "vars": [],
        "max_words": 20,
        "tone": "中性礼貌",
        "notes": "适用于非标准路径的温和收尾"
    },
    "unknown_too_many": {
        "purpose": "多次无法理解用户输入后的结束语",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "抱歉+留联系方式",
        "notes": "不是用户的错，是系统无法理解。留CS联系方式"
    },

    # ── 异议处理 ──
    "objection_general": {
        "purpose": "用户拒绝还款时的通用应对话术",
        "groups": ["H2", "H1", "S0"],
        "vars": ["{name}", "{amount}"],
        "max_words": 30,
        "tone": "H2: 理解+引导 | H1: 共情+方案 | S0: 严肃+后果",
        "notes": "不纠缠拒绝理由，直接提供解决方案或告知后果"
    },
    "handle_no_money": {
        "purpose": "用户说没钱时的首次应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "共情+提供展期/部分还款选项",
        "notes": "首次说没钱：理解→提供选项→询问意愿"
    },
    "handle_no_money_repeat": {
        "purpose": "用户多次说没钱时的重复应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "更柔和的引导",
        "notes": "第2+次说没钱后使用，用更柔和的语气避免对抗"
    },
    "handle_threat": {
        "purpose": "用户威胁（报警/OJK/投诉）时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "冷静专业，不争论",
        "notes": "合规红线：不挑衅、不争论、不退让，直接结束对话"
    },
    "handle_user_abuse": {
        "purpose": "用户辱骂时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 20,
        "tone": "冷静礼貌，结束对话",
        "notes": "不回骂，不解释，礼貌结束通话"
    },
    "handle_dont_know": {
        "purpose": "用户说不知道/不了解情况时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "耐心解释，不责备",
        "notes": "假设用户真的不知道，重新说明来意"
    },
    "handle_wrong_number": {
        "purpose": "用户声称打错了时的应对话术",
        "groups": ["*"],
        "vars": ["{name}"],
        "max_words": 20,
        "tone": "礼貌确认后结束",
        "notes": "简单道歉后结束，不做二次核验（避免骚扰感）"
    },

    # ── 展期与协商 ──
    "explain_extension": {
        "purpose": "介绍展期方案",
        "groups": ["*"],
        "vars": ["{extension_fee}"],
        "max_words": 35,
        "tone": "帮助性介绍，不push",
        "notes": "说明展期费用和流程，引导用户确认"
    },
    "confirm_extension": {
        "purpose": "确认用户同意展期方案",
        "groups": ["*"],
        "vars": ["{extension_fee}"],
        "max_words": 25,
        "tone": "确认+鼓励",
        "notes": "用户同意展期后确认费用和时间"
    },
    "confirm_extension_repeat": {
        "purpose": "用户多次讨论展期后的再次确认话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "简洁确认不重复介绍",
        "notes": "已讨论过展期，简短确认即可"
    },
    "handle_partial_payment": {
        "purpose": "用户想部分还款时的应对话术",
        "groups": ["*"],
        "vars": ["{amount}"],
        "max_words": 35,
        "tone": "灵活协商",
        "notes": "确认可接受部分还款，询问具体金额和时间"
    },
    "partial_payment_repeat": {
        "purpose": "用户多次讨论部分还款后的简洁回应",
        "groups": ["*"],
        "vars": [],
        "max_words": 20,
        "tone": "直接推进到金额和时间",
        "notes": "已讨论过部分还款，直接问金额和时间"
    },
    "handle_short_extension_request": {
        "purpose": "用户要求短期延期（1-3天）的应对话术",
        "groups": ["*"],
        "vars": ["{max_days}"],
        "max_words": 25,
        "tone": "理解但设定期限",
        "notes": "说明最多可延期天数，要求在此期限内还款"
    },
    "handle_interest_reduction_request": {
        "purpose": "用户要求减免利息的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "解释无法减免但不激化矛盾",
        "notes": "合规红线：不能自行承诺减免利息/罚款"
    },
    "handle_high_interest_complaint": {
        "purpose": "用户抱怨利率太高的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "共情解释，不争论利率",
        "notes": "承认用户的感受，将焦点转回解决当前问题"
    },

    # ── 信息查询应答 ──
    "answer_amount": {
        "purpose": "回答用户询问的欠款金额",
        "groups": ["*"],
        "vars": ["{amount}"],
        "max_words": 20,
        "tone": "清楚告知",
        "notes": "简明报出金额，可追加一句说明"
    },
    "answer_fee": {
        "purpose": "回答用户询问费用构成",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "透明解释",
        "notes": "说明费用按合同约定，不过度辩护"
    },
    "answer_identity": {
        "purpose": "回答用户对公司身份的质疑",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "自信专业",
        "notes": "简短说明公司身份，不陷入争论"
    },
    "answer_payment_method": {
        "purpose": "回答用户询问还款方式",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "清晰指引",
        "notes": "说明可通过App/银行转账还款"
    },
    "handle_consequence_inquiry": {
        "purpose": "回答用户询问逾期后果",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "如实告知但不恐吓",
        "notes": "如实说明征信影响和滞纳金，语气客观不威胁"
    },
    "handle_identity_verification_request": {
        "purpose": "用户要求验证公司身份合法性时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "自信提供验证方式",
        "notes": "指引用户通过App内信息或官方网站验证"
    },

    # ── 边缘场景 ──
    "handle_already_paid": {
        "purpose": "用户说已经还了时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "温和确认后结束",
        "notes": "不做争论，指引用户查看App确认，礼貌结束"
    },
    "handle_third_party": {
        "purpose": "第三方（非本人）接听电话时的应对话术",
        "groups": ["*"],
        "vars": ["{name}"],
        "max_words": 25,
        "tone": "礼貌请求转达",
        "notes": "不透露债务细节给第三方，仅请求转达回电"
    },
    "handle_transfer_in_process_response": {
        "purpose": "用户说正在转账中时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 20,
        "tone": "确认等待+感谢",
        "notes": "相信用户，确认后结束等待到账"
    },
    "handle_settlement_proof_request": {
        "purpose": "用户要求开具结清证明时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 30,
        "tone": "指引申请流程",
        "notes": "说明还清后可通过App申请结清证明"
    },
    "handle_app_uninstalled_problem": {
        "purpose": "用户说已卸载App时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "引导重新安装或替代方式",
        "notes": "提供替代还款方式"
    },
    "handle_borrowing_money_response": {
        "purpose": "用户说正在借钱来还时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 25,
        "tone": "理解+约定明确时间",
        "notes": "表示理解，但追问具体能还款的时间"
    },
    "handle_payment_reminder_request": {
        "purpose": "用户要求发送还款提醒时的应对话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 20,
        "tone": "同意发送+确认接收方式",
        "notes": "确认将通过短信/App推送发送提醒"
    },
    "handle_unknown": {
        "purpose": "无法理解用户输入时的通用回退话术",
        "groups": ["*"],
        "vars": [],
        "max_words": 15,
        "tone": "礼貌请求重复",
        "notes": "简短的'请重复'类话术，不超过2句"
    },

    # ── 沉默处理 ──
    "silence_engage": {
        "purpose": "沉默第1级：超低门槛破冰，只需回答'ya'",
        "groups": ["*"],
        "vars": ["{name}"],
        "max_words": 15,
        "tone": "鼓励性，不给压力",
        "notes": "是非题/单字确认类问题。降低回应门槛是第一优先级"
    },
    "silence_level_1": {
        "purpose": "沉默第2级：确认通话质量和用户在线状态",
        "groups": ["*"],
        "vars": ["{name}"],
        "max_words": 18,
        "tone": "温和确认",
        "notes": "用户在线但沉默→确认能否听见"
    },
    "silence_level_2": {
        "purpose": "沉默第3级：主动介绍账单信息，降低信息不对称",
        "groups": ["*"],
        "vars": ["{name}", "{amount}", "{days}"],
        "max_words": 35,
        "tone": "主动告知，不给压力",
        "notes": "不等用户回应，主动提供信息，末尾加简单确认"
    },
    "silence_level_3": {
        "purpose": "沉默第4级：给三选一选项，用选择框架引导开口",
        "groups": ["*"],
        "vars": ["{name}", "{amount}", "{extension_fee}"],
        "max_words": 35,
        "tone": "提供具体选项，简化决策",
        "notes": "选项：(1) lunas (2) cicil separuh (3) perpanjangan。只需说数字"
    },
    "silence_level_4": {
        "purpose": "沉默第5级：告知后果+留联系方式+礼貌挂断",
        "groups": ["*"],
        "vars": [],
        "max_words": 50,
        "tone": "正式告知，不威胁，预留回头路",
        "notes": "最后一步：告知后果→留CS联系方式→礼貌结束。不威胁不辱骂"
    },
}


# ============================================================
# Prompt 构建
# ============================================================

SYSTEM_PROMPT = """Anda adalah ahli penagihan (debt collection) Bahasa Indonesia untuk perusahaan pinjaman online "Extra Uang".

Keahlian Anda:
- Menulis skrip percakapan penagihan yang sopan, profesional, dan efektif
- Memahami nuansa bahasa Indonesia lisan (colloquial), bukan bahasa buku
- Memahami psikologi nasabah dan teknik persuasi verbal
- Mampu menghasilkan variasi kalimat yang berbeda secara struktur, bukan hanya ganti kata

ATURAN BAHASA:
1. Gunakan Bahasa Indonesia lisan yang ALAMI, bukan bahasa formal/tulisan
2. Gunakan sapaan "Bapak/Ibu" atau "{name}" — JANGAN gunakan "Anda" berlebihan
3. Gunakan kata-kata seperti: "ya", "sih", "dong", "nih", "deh" secukupnya untuk naturalness
4. Hindari terjemahan kaku dari bahasa Inggris
5. Variasikan struktur kalimat: tanya dulu baru info, info dulu baru tanya, singkat, sedikit panjang, dsb
6. Setiap skrip HARUS berbeda secara struktur kalimat, bukan hanya sinonim kata

ATURAN KONTEN:
1. JANGAN mengancam, menghina, atau menggunakan kata kasar
2. JANGAN mengaku sebagai polisi, OJK, atau instansi pemerintah
3. JANGAN menjanjikan penghapusan bunga/denda tanpa otorisasi
4. Profesional dan sopan dalam situasi apapun"""


def build_category_prompt(cat_name: str, meta: dict, examples: list[str]) -> str:
    """为单个话术类别构建生成prompt"""
    groups_str = ", ".join(meta["groups"])
    vars_str = ", ".join(meta["vars"]) if meta["vars"] else "（无变量）"
    max_words = meta["max_words"]

    examples_str = "\n".join(f"  {i+1}. {ex}" for i, ex in enumerate(examples[:5]))

    prompt = f"""KATEGORI: {cat_name}
FUNGSI: {meta["purpose"]}
TAHAP PENAGIHAN: {groups_str}
VARIABEL: {vars_str}
MAKSIMAL KATA: {max_words} kata per skrip
NADA: {meta["tone"]}
CATATAN: {meta["notes"]}

CONTOH SKRIP SAAT INI:
{examples_str}

TUGAS:
Hasilkan 20 variasi skrip Bahasa Indonesia untuk kategori "{cat_name}".

PENTING:
- Setiap skrip HARUS berbeda secara STRUKTUR kalimat, bukan hanya ganti sinonim
- Jika ada variabel (misal {{name}}, {{amount}}), gunakan PERSIS seperti yang tertulis
- Variasikan: panjang kalimat, urutan informasi, tingkat formalitas, kata pembuka
- Patuhi batas maksimal {max_words} kata
- Nada sesuai ketentuan: {meta["tone"]}
- Minimal 18 skrip, maksimal 22 skrip

OUTPUT FORMAT (JSON array of strings):
["skrip 1", "skrip 2", ...]"""

    return prompt


# ============================================================
# LLM 调用
# ============================================================

async def call_llm(system_prompt: str, user_prompt: str, model: str = "gpt-4o") -> list[str]:
    """调用 LLM 生成话术变体，自动检测 Anthropic 或 OpenAI 格式"""
    import httpx

    # 优先检测 Anthropic 格式（DeepSeek / Claude）
    anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    anthropic_base = os.environ.get("ANTHROPIC_BASE_URL", "")

    if anthropic_key:
        return await _call_anthropic(system_prompt, user_prompt, model, anthropic_key, anthropic_base)

    # 回退到 OpenAI 格式
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise RuntimeError("请设置 ANTHROPIC_AUTH_TOKEN 或 OPENAI_API_KEY 环境变量")
    if not base_url:
        raise RuntimeError("请设置 OPENAI_BASE_URL 或 ANTHROPIC_BASE_URL 环境变量")

    return await _call_openai(system_prompt, user_prompt, model, api_key, base_url)


async def _call_anthropic(system_prompt: str, user_prompt: str, model: str,
                          api_key: str, base_url: str) -> list[str]:
    """通过 Anthropic Messages API 调用"""
    import httpx

    url = f"{base_url}/v1/messages" if not base_url.endswith("/v1/messages") else base_url
    timeout = int(os.environ.get("API_TIMEOUT_MS", "600000")) // 1000

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "max_tokens": 16384,  # reasoning 模型 thinking 消耗大，需更高 quota
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"API HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        raise RuntimeError(f"API 调用失败: {e}")

    # 兼容 reasoning 模型（thinking + text 混合 content）
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text = block["text"].strip()
            break
    if not text:
        raise RuntimeError(f"LLM 未返回文本（可能 thinking 消耗了全部 token）。原始 content 类型: {[b.get('type') for b in data.get('content', [])]}")
    if not text and data.get("content"):
        text = str(data["content"][0]).strip()

    return _parse_script_list(text)


async def _call_openai(system_prompt: str, user_prompt: str, model: str,
                       api_key: str, base_url: str) -> list[str]:
    """通过 OpenAI Chat Completions API 调用"""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.9,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"API HTTP {e.response.status_code}: {e.response.text[:500]}")
    except Exception as e:
        raise RuntimeError(f"API 调用失败: {e}")

    content = data["choices"][0]["message"]["content"]
    return _parse_script_list(content)


def _parse_script_list(content: str) -> list[str]:
    """从 LLM 输出中解析话术列表（JSON 数组或按行列表）"""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if len(lines) > 2 else lines[-1]
        content = content.strip()

    try:
        scripts = json.loads(content)
        if isinstance(scripts, list):
            return scripts
    except json.JSONDecodeError:
        pass

    # 按行解析（处理 LLM 未输出纯 JSON 的情况）
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() and (". " in line or ") " in line)):
            line = line.split(". ", 1)[-1] if ". " in line else line.split(") ", 1)[-1]
        if line and len(line) > 5:
            line = line.strip('", ')
            lines.append(line)

    if len(lines) >= 10:
        return lines

    raise RuntimeError(f"无法解析 LLM 输出为话术列表。原始输出:\n{content[:500]}")


# ============================================================
# 主流程
# ============================================================

def get_existing_scripts(bot, cat_name: str) -> list[str]:
    """获取某个类别的现存话术"""
    category_scripts = bot.script_lib.get(cat_name, {})
    all_scripts = []
    for group, scripts in category_scripts.items():
        all_scripts.extend(scripts)
    return all_scripts


async def generate_category(
    bot,
    cat_name: str,
    count: int,
    model: str,
    dry_run: bool = False,
) -> dict:
    """为单个类别生成话术变体"""
    meta = CATEGORY_META.get(cat_name)
    if not meta:
        print(f"  ⚠️ {cat_name}: 无元数据，跳过")
        return {"category": cat_name, "scripts": [], "error": "no metadata"}

    examples = get_existing_scripts(bot, cat_name)
    user_prompt = build_category_prompt(cat_name, meta, examples)

    if dry_run:
        print(f"\n{'='*60}")
        print(f"CATEGORY: {cat_name}")
        print(f"{'='*60}")
        print(user_prompt)
        print(f"\n[DRY RUN] 将生成 {count} 条变体")
        return {"category": cat_name, "scripts": [], "dry_run": True}

    print(f"  🤖 调用 LLM 生成 {cat_name} ({len(examples)} existing → {count} new)...")
    try:
        scripts = await call_llm(SYSTEM_PROMPT, user_prompt, model)
        # 去重并限制数量
        seen = set()
        unique = []
        for s in scripts:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        unique = unique[:count]
        print(f"     ✅ 生成 {len(unique)} 条唯一话术")
        return {"category": cat_name, "scripts": unique}
    except Exception as e:
        print(f"     ❌ 失败: {e}")
        return {"category": cat_name, "scripts": [], "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="LLM 批量话术生成工具")
    parser.add_argument("--all", action="store_true", help="生成所有类别")
    parser.add_argument("--categories", type=str, help="逗号分隔的类别列表")
    parser.add_argument("--count", type=int, default=20, help="每个类别生成的变体数量（默认20）")
    parser.add_argument("--output", type=str, default=None, help="输出JSON文件路径")
    parser.add_argument("--model", type=str,
                        default=os.environ.get("ANTHROPIC_MODEL") or os.environ.get("LLM_MODEL", "gpt-4o"),
                        help="LLM 模型名称")
    parser.add_argument("--dry-run", action="store_true", help="仅打印prompt不调用API")
    parser.add_argument("--delay", type=float, default=1.0, help="API调用间隔秒数（默认1.0）")
    args = parser.parse_args()

    # 确定要生成的类别
    all_categories = sorted(CATEGORY_META.keys())

    if args.all:
        categories = all_categories
    elif args.categories:
        categories = [c.strip() for c in args.categories.split(",")]
        invalid = set(categories) - set(all_categories)
        if invalid:
            print(f"❌ 未知类别: {invalid}")
            print(f"   可用类别: {', '.join(all_categories)}")
            sys.exit(1)
    else:
        print("请指定 --all 或 --categories")
        print(f"可用类别 ({len(all_categories)}):")
        for i, cat in enumerate(all_categories):
            meta = CATEGORY_META[cat]
            print(f"  {i+1:2d}. {cat:40s} | {meta['purpose'][:60]}")
        sys.exit(1)

    print(f"📋 将处理 {len(categories)} 个类别")
    if args.dry_run:
        print("🔍 DRY RUN 模式 — 仅打印prompt，不调用API")
    print()

    # 初始化 bot 以读取现存的 scripts
    bot = CollectionChatBot("H2", "Test")

    # 逐个生成
    results = []
    success_count = 0
    fail_count = 0

    for i, cat_name in enumerate(categories):
        print(f"[{i+1}/{len(categories)}] {cat_name}")
        result = await generate_category(
            bot, cat_name, args.count, args.model, dry_run=args.dry_run
        )
        results.append(result)
        if result.get("error"):
            fail_count += 1
        elif not result.get("dry_run"):
            success_count += 1

        # API 调用间隔
        if not args.dry_run and i < len(categories) - 1:
            await asyncio.sleep(args.delay)

    # 生成输出
    if not args.dry_run:
        output_path = args.output or f"data/scripts_generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        output = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "model": args.model,
                "categories_total": len(categories),
                "categories_success": success_count,
                "categories_failed": fail_count,
                "target_count_per_category": args.count,
            },
            "categories": results,
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ 完成! {success_count}/{len(categories)} 成功, {fail_count} 失败")
        print(f"📄 输出: {output_path}")
        print(f"\n下一步: 人工审核 → 通过后运行 scripts/import_scripts.py 导入")


if __name__ == "__main__":
    asyncio.run(main())
