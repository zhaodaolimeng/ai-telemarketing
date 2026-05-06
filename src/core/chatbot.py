#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能催收对话机器人 - 语音版本 (v3)
集成TTS功能，完善状态机，支持变量替换
基于246条对话分析
"""
import random
import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime
import sys
import io

# 确保输出编码正确
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import edge_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("警告: edge-tts未安装，TTS功能不可用")


class ChatState(Enum):
    """对话状态枚举"""
    INIT = auto()
    GREETING = auto()
    IDENTITY_VERIFY = auto()  # 身份确认
    PURPOSE = auto()  # 说明来意
    HANDLE_OBJECTION = auto()  # 处理用户异议
    ASK_TIME = auto()  # 询问还款时间
    PUSH_FOR_TIME = auto()  # 催促确认时间
    COMMIT_TIME = auto()  # 确认用户还款时间
    CONFIRM_EXTENSION = auto()  # 确认展期
    HANDLE_BUSY = auto()  # 处理用户忙碌情况
    HANDLE_WRONG_NUMBER = auto()  # 处理错号情况
    CLOSE = auto()
    FAILED = auto()


@dataclass
class ChatTurn:
    """对话回合"""
    agent: str
    customer: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    latency_ms: Optional[float] = None


@dataclass
class ConversationLog:
    """对话日志"""
    session_id: str
    chat_group: str
    customer_info: Dict
    turns: List[ChatTurn] = field(default_factory=list)
    success: bool = False
    commit_time: Optional[str] = None
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None


class TextToSpeech:
    """TTS封装类"""

    def __init__(self, voice: str = "id-ID-ArdiNeural"):
        self.voice = voice
        self.available = TTS_AVAILABLE

    async def synthesize(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
        """合成语音"""
        if not self.available or not text:
            return None

        if output_file is None:
            output_dir = Path("data/tts_output")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_file = str(output_dir / f"tts_{timestamp}.mp3")

        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_file)
            return output_file
        except Exception as e:
            print(f"TTS错误: {e}")
            return None

    async def list_voices(self, locale: str = "id-ID") -> List[Dict]:
        """列出可用语音"""
        if not self.available:
            return []
        voices = await edge_tts.list_voices()
        return [v for v in voices if locale in v["Locale"]]


class VariableReplacer:
    """话术模板变量替换器"""

    def __init__(self):
        self.default_vars = {
            "time": "nanti",
            "name": "Pak/Bu",
            "amount": "pinjaman",
            "date": "hari ini"
        }

    def replace(self, text: str, **kwargs) -> str:
        """替换变量"""
        vars = {**self.default_vars, **kwargs}
        try:
            return text.format(**vars)
        except KeyError as e:
            print(f"警告: 变量缺失 {e}")
            for key in e.args:
                text = text.replace(f"{{{key}}}", vars.get(key, f"{{{key}}}"))
            return text


class TimeDetector:
    """时间检测器 - 增强版，支持复杂口语化时间表达"""

    # 时间模式，按优先级排序：具体时间 > 相对时间 > 模糊时间
    TIME_PATTERNS = [
        # 具体点钟
        ("jam 12", ["jam 12", "12 siang", "jam dua belas", "siang jam 12", "tengah hari"]),
        ("jam 11", ["jam 11", "jam sebelas", "11 siang", "11 pagi"]),
        ("jam 10", ["jam 10", "jam sepuluh", "10 pagi", "10 siang"]),
        ("jam 9", ["jam 9", "jam sembilan", "9 pagi", "9 siang"]),
        ("jam 8", ["jam 8", "jam delapan", "8 pagi", "8 siang"]),
        ("jam 7", ["jam 7", "jam tujuh", "7 pagi"]),
        ("jam 6", ["jam 6", "jam enam", "6 pagi"]),
        ("jam 5", ["jam 5", "jam lima", "5 sore", "5 pagi"]),
        ("jam 4", ["jam 4", "jam empat", "4 sore", "4 pagi"]),
        ("jam 3", ["jam 3", "jam tiga", "3 sore", "3 pagi"]),
        ("jam 2", ["jam 2", "jam dua", "2 sore", "2 siang"]),
        ("jam 1", ["jam 1", "jam satu", "1 siang", "1 pagi"]),
        # 半点和刻钟表达
        ("jam 2.30", ["setengah 3", "setengah tiga", "jam 2 kurang 30", "3 kurang setengah"]),
        ("jam 1.30", ["setengah 2", "setengah dua", "jam 1 kurang 30", "2 kurang setengah"]),
        ("jam 3.30", ["setengah 4", "setengah empat", "jam 3 kurang 30", "4 kurang setengah"]),
        ("jam 2.45", ["jam 3 kurang 15", "seperempat jam 3"]),
        ("jam 2.15", ["seperempat lewat 2", "jam 2 lebih 15"]),
        # 时间段
        ("pagi hari", ["pagi", "pagi hari", "nanti pagi", "pagi ini", "besok pagi"]),
        ("siang hari", ["siang", "siang hari", "nanti siang", "siang ini", "tengah hari"]),
        ("sore hari", ["sore", "sore hari", "nanti sore", "sore ini", "petang"]),
        ("malam hari", ["malam", "malam hari", "nanti malam", "malam ini", "besok malam"]),
        # 具体日期
        ("hari ini", ["hari ini", "sekarang", "hari ini siang", "hari ini sore", "hari ini pagi", "sekarang juga", "nanti hari ini", "hari ini malam"]),
        ("besok", ["besok", "besok pagi", "besok siang", "besok sore", "besok malam", "hari besok", "esok"]),
        ("lusa", ["lusa", "hari lusa", "besok lusa"]),
        # 星期
        ("hari senin", ["senin", "hari senin", "minggu ini senin"]),
        ("hari selasa", ["selasa", "hari selasa", "minggu ini selasa"]),
        ("hari rabu", ["rabu", "hari rabu", "minggu ini rabu"]),
        ("hari kamis", ["kamis", "hari kamis", "minggu ini kamis"]),
        ("hari jumat", ["jumat", "hari jumat", "jum'at", "minggu ini jumat"]),
        ("hari sabtu", ["sabtu", "hari sabtu", "minggu ini sabtu"]),
        ("hari minggu", ["minggu", "hari minggu", "minggu ini minggu"]),
        # 相对时间
        ("minggu ini", ["minggu ini", "pekan ini"]),
        ("minggu depan", ["minggu depan", "pekan depan"]),
        ("akhir minggu", ["akhir minggu", "weekend", "akhir pekan"]),
        ("awal bulan", ["awal bulan", "awal bulan depan"]),
        ("akhir bulan", ["akhir bulan", "akhir bulan depan", "menjelang gaji", "pas gaji"]),
        ("nanti", ["nanti", "sebentar lagi", "beberapa saat lagi", "satu jam lagi", "dua jam lagi", "nanti ya", "nanti dulu"]),
        ("beberapa hari lagi", ["beberapa hari lagi", "dua hari lagi", "tiga hari lagi", "beberapa hari lagi ya"]),
    ]

    @classmethod
    def detect(cls, text: str) -> Optional[str]:
        """检测时间，优先返回更具体的时间表达，支持组合时间提取"""
        if not text:
            return None

        text_lower = text.lower()
        detected_times = []

        # 先检测所有匹配的时间
        for time_value, patterns in cls.TIME_PATTERNS:
            for pattern in patterns:
                if pattern in text_lower:
                    # 权重：匹配长度越大概率越具体
                    detected_times.append((len(pattern), time_value))

        # 检测通用jam + 数字模式
        import re
        jam_matches = re.findall(r'jam\s+(\d+)', text_lower)
        if jam_matches:
            for jam in jam_matches:
                detected_times.append((4, f"jam {jam}"))  # 长度4作为权重

        # 检测具体日期模式：tanggal + 数字
        tgl_matches = re.findall(r'(tanggal|tgl)\s+(\d+)', text_lower)
        if tgl_matches:
            for _, tgl in tgl_matches:
                detected_times.append((7, f"tanggal {tgl}"))

        # 如果检测到多个时间，尝试组合日期+时间
        if len(detected_times) >= 2:
            date_words = ["besok", "lusa", "hari ini", "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu"]
            dates = []
            times = []
            for _, val in detected_times:
                if val in date_words or val.startswith("tanggal") or val.startswith("hari"):
                    dates.append(val)
                elif val.startswith("jam") or val in ["pagi hari", "siang hari", "sore hari", "malam hari"]:
                    times.append(val)

            # 如果同时有日期和时间，组合起来返回
            if dates and times:
                return f"{dates[0]} {times[0]}"

        # 否则返回最长匹配（最具体）的那个
        if detected_times:
            # 按匹配长度降序排序，取最长的
            detected_times.sort(reverse=True, key=lambda x: x[0])
            return detected_times[0][1]

        return None


class ASRCorrector:
    """印尼语ASR错误纠正器 - 基于常见错误映射"""

    # 印尼语ASR常见错误修正映射，从batch_annotate.py迁移并扩展
    ASR_CORRECTIONS = {
        "nasian": "lunas",
        "puluh nasian": "penuh lunas",
        "tempat": "tempo",
        "Hajianya": "tagihan Anda",
        "Ufah Nau": "Uang",
        "Kuala": "Nanti lah",
        "kemaren": "hari ini",
        "tunggu": "bayar",
        "Jalan waktu itu": "Baik, jam 10 ya",
        "Extra Uang": "Uang Extra",
        "Uang extra": "Uang Extra",
        "uang extra": "Uang Extra",
        "tagihan nya": "tagihan Anda",
        "tagihan mu": "tagihan Anda",
        "bapak nya": "bapak Anda",
        "ibu nya": "ibu Anda",
        "saya nya": "saya",
        "dia nya": "dia",
        "kita nya": "kita",
        "mereka nya": "mereka",
        "nggak": "tidak",
        "gak": "tidak",
        "ga": "tidak",
        "tdk": "tidak",
        "ya": "ya",
        "iya": "iya",
        "iiya": "iya",
        "iyya": "iya",
        "yaa": "ya",
        "yaa": "ya",
        "ngga": "tidak",
        "gaga": "tidak",
        "saya": "saya",
        "sayaa": "saya",
        "sya": "saya",
        "sy": "saya",
        "kamu": "kamu",
        "km": "kamu",
        "anda": "Anda",
        "Anda": "Anda",
        "kd": "Anda",
        "jp": "jam",
        "jp.": "jam",
        "rp": "Rp",
        "rupiah": "rupiah",
        "rb": "ribu",
        "juta": "juta",
        "jt": "juta",
    }

    @classmethod
    def correct(cls, text: str) -> str:
        """纠正ASR识别错误"""
        if not text:
            return text

        corrected_text = text.strip()
        # 按错误字符串长度从长到短排序，避免短的错误先被替换掉
        sorted_corrections = sorted(cls.ASR_CORRECTIONS.items(), key=lambda x: len(x[0]), reverse=True)
        for error, correct in sorted_corrections:
            # 全字匹配替换
            corrected_text = corrected_text.replace(error, correct)

        return corrected_text


class IntentDetector:
    """用户意图识别器 - 规则式，按照优先级顺序匹配，越靠前优先级越高"""

    # 注意顺序：越具体的意图越靠前，避免被更通用的意图匹配覆盖
    INTENT_PATTERNS = [
        ("deny_identity", [r"\bbukan\b", r"\bsalah nomor\b", r"\banda salah orang\b", r"\bsaya tidak kenal\b", r"\bini bukan nomornya\b", r"\bsalah orang\b", r"\bbukan orang yang anda cari\b"]),
        ("busy_later", [r"\bsibuk\b", r"\bnanti ya\b", r"\bsaya lagi diluar\b", r"\bnanti saya hubungi balik\b", r"\bsebentar lagi\b", r"\bsaya lagi mengemudi\b", r"\bsaya sedang rapat\b", r"\bnanti saya telepon kembali\b", r"\bsaya tidak bisa bicara sekarang\b"]),
        ("threaten", [r"\bsaya akan laporkan ke ojk\b", r"\bsaya akan lapor polisi\b", r"\banda ancam saya\b", r"\bsaya akan lapor ke pihak berwenang\b", r"\bsaya akan komplain\b", r"\bancam\b", r"\blapor\b"]),
        ("ask_extension", [r"\bperpanjang\b", r"\bperpanjangan\b", r"\bbisa nggak diperpanjang\b", r"\bextension\b", r"\btunda bayar\b", r"\bbisa ditunda ya\b", r"\bsaya mau perpanjang\b", r"\bberapa hari bisa ditunda\b", r"\bnanti minggu depan baru bisa bayar\b"]),
        ("ask_amount", [r"\bberapa\b", r"\bjumlahnya berapa\b", r"\btagihan berapa\b", r"\bbesarnya berapa\b", r"\bberapa nominalnya\b", r"\bbesar tagihan\b", r"\bberapa bayarnya\b"]),
        ("question_identity", [r"\bsiapa kamu\b", r"\banda dari mana\b", r"\bmana buktinya\b", r"\bsaya tidak percaya\b", r"\bpenipuan\b", r"\bapakah ini penipuan\b", r"\banda siapa\b", r"\bsaya tidak pinjam\b", r"\btidak pernah pinjam\b"]),
        ("no_money", [r"\btidak ada duit\b", r"\bsaya tidak punya uang\b", r"\blagi susah\b", r"\belum ada uang\b", r"\bsaya sedang kesulitan keuangan\b", r"\buang saya belum masuk\b", r"\bgaji belum cair\b", r"\bsulit\b", r"\bkesulitan\b", r"\bkeberatan\b", r"\btidak mampu\b", r"\belum mampu\b"]),
        ("confirm_time", [r"\bjam [0-9]+", r"\bjp [0-9]+", r"\bhari ini\b", r"\bbesok\b", r"\blinggu ini\b", r"\bsaya bayar jam [0-9]+", r"\bnanti jam [0-9]+", r"\bjam [0-9]+ ya\b", r"\bsore hari\b", r"\bpagi hari\b", r"\bsiang hari\b", r"\bnanti sore\b", r"\bnanti pagi\b", r"\bjam berapa\b", r"\btanggal berapa\b", r"\bhari apa\b", r"\bnanti sore\b"]),
        ("agree_to_pay", [r"\bsiap bayar\b", r"\bolehan\b", r"\bbisa\b", r"\bok\b", r"\bsetuju\b", r"\bsaya akan bayar\b", r"\bsaya bayar nanti\b", r"\bnanti saya transfer\b", r"\bsaya bayar besok\b", r"\bsaya proses sekarang\b", r"\bsaya bayar hari ini\b", r"\baiya, saya bayar\b", r"\bbaik, saya bayar\b", r"\bsaya bayar\b", r"\btransfer segera\b"]),
        ("refuse_to_pay", [r"\btidak mau bayar\b", r"\bgak bayar\b", r"\bsaya tidak akan bayar\b", r"\bsaya tidak mau membayar\b", r"\btidak usah ditagih\b", r"\bsaya tidak bayar\b", r"\btidak bayar\b"]),
        ("greeting", [r"\bhalo\b", r"\bhai\b", r"\bpagi\b", r"\bsiang\b", r"\bsore\b", r"\bselamat pagi\b", r"\bselamat siang\b", r"\bselamat sore\b", r"\bselamat malam\b", r"\bapa kabar\b", r"\bhi\b", r"\bhello\b"]),
        ("confirm_identity", [r"\biya\b", r"\betul\b", r"\bya\b", r"\baiya benar\b", r"\bsaya adalah\b", r"\baiya ini\b", r"\bbetul saya\b", r"\bbaik\b", r"\biya, ini saya\b", r"\benar, saya yang\b", r"\benar\b", r"\biya betul\b"]),
        ("ask_fee", [r"\bbunga berapa\b", r"\bdenda berapa\b", r"\bbiaya admin berapa\b", r"\bkenapa begitu besar\b", r"\bbiaya berapa\b"]),
        ("ask_payment_method", [r"\btransfer kemana\b", r"\brekening mana\b", r"\bnomor rekening\b", r"\bbayar kemana\b", r"\bagaimana cara bayar\b"]),
        ("already_paid", [r"\bsudah bayar\b", r"\bsudah transfer\b", r"\bsaya sudah bayar\b", r"\btadi sudah bayar\b", r"\bsudah dibayar\b"]),
        ("partial_payment", [r"\bmau bayar berapa\b", r"\bbisa bayar setengah dulu\b", r"\bbayar sebagian\b", r"\bcicil\b", r"\bayar sedikit dulu\b"]),
        ("third_party", [r"\bkeluarga dia\b", r"\borang tua dia\b", r"\banak dia\b", r"\bsaudara dia\b", r"\bdia tidak ada\b", r"\bsaya bukan orang yang anda cari\b", r"\bdia sedang keluar\b"]),
        ("dont_know", [r"\btidak tahu\b", r"\bsaya tidak tahu\b", r"\btidak mengerti\b", r"\btidak paham\b", r"\bsaya tidak paham\b"]),
    ]

    @classmethod
    def detect(cls, text: str) -> str:
        """识别用户意图，按照优先级顺序匹配"""
        if not text:
            return "unknown"

        text_lower = text.lower()

        for intent, patterns in cls.INTENT_PATTERNS:
            for pattern in patterns:
                import re
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return intent

        return "unknown"


class CollectionChatBot:
    """催收对话机器人 - 增强版"""

    def __init__(self, chat_group: str = "H2", customer_name: Optional[str] = None,
                 overdue_amount: int = 500000, overdue_days: int = 5):
        self.chat_group = chat_group
        self.customer_name = customer_name or "Pak/Bu"
        self.overdue_amount = overdue_amount  # 欠款金额，默认500k
        self.overdue_days = overdue_days  # 逾期天数，默认5天
        self.extension_fee = int(overdue_amount * 0.3)  # 展期费用默认30%
        self.state: ChatState = ChatState.INIT
        self.conversation: List[ChatTurn] = []
        self.commit_time: Optional[str] = None
        self.extension_agreed: bool = False
        self.objection_count: int = 0
        self.max_objections: int = 3
        self.user_intent: str = ""

        # 组件
        self.tts = TextToSpeech()
        self.var_replacer = VariableReplacer()
        self.time_detector = TimeDetector()
        self.intent_detector = IntentDetector()
        self.asr_corrector = ASRCorrector()

        # 会话ID
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 话术库 - 扩展版
        self._init_script_lib()

    def _init_script_lib(self):
        """初始化话术库"""
        self.script_lib = {
            "greeting": {
                "H2": ["Halo?", "Halo.", "Halo, selamat pagi.", "Halo, apa kabar?"],
                "H1": ["Halo?", "Halo, selamat pagi.", "Halo, selamat siang.", "Halo, apa kabar?"],
                "S0": ["Halo?", "Halo.", "Halo, selamat sore.", "Halo, apa kabar?"]
            },
            "identity_verify": {
                "H2": [
                    "Halo, selamat pagi {name}. Saya dari aplikasi Extra Uang, bisa bicara dengan {name} sendiri?",
                    "Halo {name}, saya dari Extra Uang. Apakah saya berbicara dengan {name} yang punya pinjaman di aplikasi kami ya?",
                    "Halo, selamat pagi. Saya petugas dari Extra Uang, bisa bicara dengan Bapak/Ibu {name}?"
                ],
                "H1": [
                    "Halo, selamat siang {name}. Saya dari aplikasi Extra Uang, apakah ini benar dengan {name}?",
                    "Halo {name}, saya dari Extra Uang. Saya menelpon tentang tagihan pinjaman Anda yang sudah jatuh tempo ya.",
                    "Selamat siang, saya petugas dari Extra Uang. Apakah ini Bapak/Ibu {name}?"
                ],
                "S0": [
                    "Halo, selamat sore {name}. Saya dari aplikasi Extra Uang, apakah saya berbicara dengan {name}?",
                    "Halo {name}, saya dari Extra Uang. Saya menelpon tentang tagihan pinjaman Anda yang sudah lama jatuh tempo ya.",
                    "Selamat sore, saya petugas dari Extra Uang. Bisakah saya bicara dengan Bapak/Ibu {name}?"
                ]
            },
            "purpose": {
                "H2": [
                    "Saya menelpon untuk memberitahu bahwa tagihan pinjaman {name} sebesar Rp {amount} sudah jatuh tempo selama {days} hari ya.",
                    "Tentang pinjaman Anda di Extra Uang, sekarang sudah jatuh tempo {days} hari dengan total tagihan Rp {amount} ya.",
                    "Saya ingin memberitahu bahwa tagihan pinjaman Anda sebesar Rp {amount} sudah harus dibayar sekarang ya."
                ],
                "H1": [
                    "Saya dari Extra Uang, ingin memberitahu bahwa tagihan {name} sebesar Rp {amount} sudah jatuh tempo lebih dari 30 hari ya.",
                    "Tentang pinjaman Anda, sudah lebih dari 30 hari jatuh tempo dengan total tagihan Rp {amount}. Kami perlu segera menyelesaikan ini ya.",
                    "Saya menelpon tentang tagihan pinjaman Anda yang sudah lewat jatuh tempo lebih dari sebulan, totalnya Rp {amount} ya."
                ],
                "S0": [
                    "Kita bicara tentang pinjaman {name} yang sudah jatuh tempo lebih dari 90 hari ya, jumlahnya Rp {amount}.",
                    "Pinjaman Anda di Extra Uang sudah jatuh tempo lebih dari 3 bulan dengan total tagihan Rp {amount}. Kita harus segera cari solusi ya.",
                    "Saya menelpon tentang tagihan pinjaman Anda yang sudah lama tidak dibayar, totalnya Rp {amount} ya."
                ]
            },
            "ask_time": {
                "H2": [
                    "Kira-kira kapan {name} bisa melunasi tagihan ini ya?",
                    "Ada rencana bayar jam berapa ya?",
                    "Kapan Bapak/Ibu bisa melakukan pembayaran untuk tagihan ini ya?",
                    "Untuk tagihan Rp {amount} ini, kira-kira bisa dibayar kapan ya?"
                ],
                "H1": [
                    "Kapan {name} bisa melakukan pembayaran tagihan ini?",
                    "Jam berapa tepatnya bisa bayar?",
                    "Kira-kira hari apa Bapak/Ibu bisa membayar tagihan ini ya?",
                    "Untuk tagihan yang sudah jatuh tempo ini, ada rencana bayar kapan ya?"
                ],
                "S0": [
                    "Bagaimana rencana pembayaran {name} untuk tagihan ini ya?",
                    "Kapan bisa bayar ya?",
                    "Kira-kira kapan Bapak/Ibu bisa menyelesaikan tagihan ini ya?",
                    "Untuk tagihan yang sudah lama ini, kita harus segera selesaikan. Kira-kira bisa bayar kapan ya?"
                ]
            },
            "push": {
                "H2": [
                    "Jam berapa tepatnya ya {name}?",
                    "Hari ini jam berapa bisa bayar?",
                    "Bisa kasih tahu jam berapa pasti bisa bayar ya?",
                    "Untuk hari ini, kira-kira jam berapa ya Bapak/Ibu bisa transfer?"
                ],
                "H1": [
                    "Jam berapa tepatnya {name} bisa bayar?",
                    "Besok jam berapa ya?",
                    "Bisa kasih kepastian jam berapa ya?",
                    "Kita butuh kepastian waktu pembayaran ya, kira-kira jam berapa?"
                ],
                "S0": [
                    "Jam berapa tepatnya ya?",
                    "Hari apa bisa bayar ya?",
                    "Bisa kasih tahu pasti hari apa dan jam berapa ya?",
                    "Kita harus segera selesaikan ini, bisa kasih tahu kapan pastinya bisa bayar?"
                ]
            },
            "commit_time": {
                "H2": [
                    "Oke, saya catat ya {name} akan bayar {time}.",
                    "Baik, saya catat bahwa Anda akan membayar pada {time} ya.",
                    "Oke, saya tunggu pembayaran Anda pada {time} ya."
                ],
                "H1": [
                    "Ya, ya. Oke, {time} ya {name}, saya tunggu pembayarannya.",
                    "Baik, saya catat jadwal pembayaran Anda pada {time} ya.",
                    "Oke, saya akan tunggu pembayaran Anda sampai {time} ya."
                ],
                "S0": [
                    "Ya, ya, ya. Oke, {time} ya {name}.",
                    "Baik, saya catat bahwa Anda akan membayar pada {time} ya.",
                    "Oke, saya harap Anda benar-benar akan membayar pada {time} ya."
                ]
            },
            "confirm_commit": {
                "H2": [
                    "Jadi {name} setuju akan membayar tagihan sebesar Rp {amount} pada {time} ya?",
                    "Untuk konfirmasi, Bapak/Ibu akan membayar tagihan Rp {amount} pada {time} ya?",
                    "Jadi kesepakatannya Anda akan membayar pada {time} ya?"
                ],
                "H1": [
                    "Apakah benar {name} akan membayar tagihan ini pada {time} ya?",
                    "Untuk memastikan, Bapak/Ibu benar-benar akan membayar pada {time} ya?",
                    "Jadi Anda setuju untuk membayar tagihan ini pada {time} ya?"
                ],
                "S0": [
                    "Jadi kesepakatannya {name} akan membayar tagihan ini pada {time} ya?",
                    "Untuk konfirmasi terakhir, Anda akan membayar tagihan ini pada {time} ya?",
                    "Jadi Anda benar-benar akan membayar pada {time} ya?"
                ]
            },
            "wait": {
                "H2": [
                    "Saya tunggu pembayarannya ya {name}.",
                    "Saya tunggu sampai {time} ya.",
                    "Saya harap Anda benar-benar akan membayar pada {time} ya.",
                    "Terima kasih atas kerjasamanya, saya tunggu pembayarannya ya."
                ],
                "H1": [
                    "Saya tunggu pembayarannya ya {name}.",
                    "Saya akan menunggu sampai {time} ya.",
                    "Saya harap Anda memenuhi janji untuk membayar pada {time} ya."
                ],
                "S0": [
                    "Saya tunggu ya {name}.",
                    "Saya harap Anda benar-benar akan membayar pada {time} ya.",
                    "Terima kasih atas kesediaannya untuk menyelesaikan tagihan ini."
                ]
            },
            "closing": {
                "H2": [
                    "Terima kasih atas kerjasamanya {name}. Selamat pagi.",
                    "Terima kasih {name}, sampai jumpa.",
                    "Sukses selalu untuk Anda ya, terima kasih.",
                    "Selamat tinggal, semoga hari Anda menyenangkan."
                ],
                "H1": [
                    "Terima kasih {name}. Selamat siang.",
                    "Terima kasih atas kerjasamanya.",
                    "Sukses selalu untuk Anda ya, terima kasih.",
                    "Selamat tinggal, semoga hari Anda menyenangkan."
                ],
                "S0": [
                    "Terima kasih {name}. Selamat sore.",
                    "Terima kasih atas perhatiannya.",
                    "Sukses selalu untuk Anda ya, terima kasih.",
                    "Selamat tinggal, semoga masalah keuangan Anda segera selesai."
                ]
            },
            "closing_wrong_number": {
                "*": [
                    "Mohon maaf atas ketidaknyamanannya ya, sepertinya saya salah nomor. Terima kasih.",
                    "Maaf ya, sepertinya saya menghubungi nomor yang salah. Mohon maaf atas gangguannya.",
                    "Saya minta maaf, sepertinya saya salah nomor. Terima kasih atas waktunya."
                ]
            },
            "closing_busy": {
                "*": [
                    "Baik {name}, saya akan hubungi kembali nanti ya. Terima kasih.",
                    "Oke, kalau sedang sibuk saya akan telepon lagi nanti ya. Terima kasih.",
                    "Saya mengerti Anda sedang sibuk, saya akan hubungi kembali besok ya. Terima kasih."
                ]
            },
            # 异议处理话术
            "answer_amount": {
                "*": [
                    "Tagihan {name} sebesar Rp {amount} ya, itu termasuk pokok pinjaman dan biaya administrasi.",
                    "Total tagihan Anda adalah Rp {amount}, termasuk pokok pinjaman dan biaya layanan ya.",
                    "Jumlah yang harus Anda bayar adalah Rp {amount} ya, itu sudah termasuk semua biaya."
                ]
            },
            "explain_extension": {
                "*": [
                    "Jika {name} mengalami kesulitan untuk membayar penuh, kami menyediakan opsi perpanjangan dengan biaya administrasi sebesar Rp {extension_fee} saja ya. Dengan itu, tanggal jatuh tempo akan diundur 30 hari lagi.",
                    "Kalau Anda tidak bisa membayar penuh sekarang, kami punya opsi perpanjangan dengan biaya tambahan Rp {extension_fee} saja. Jadi Anda punya waktu 30 hari lagi untuk membayar ya.",
                    "Untuk mengurangi beban Anda, kami menawarkan opsi perpanjangan dengan biaya administrasi Rp {extension_fee}. Dengan itu, Anda bisa membayar nanti 30 hari lagi ya."
                ]
            },
            "confirm_extension": {
                "*": [
                    "Apakah {name} setuju untuk mengambil opsi perpanjangan ini ya? Jika setuju, saya akan proses sekarang.",
                    "Jadi Anda memilih opsi perpanjangan ya? Kalau setuju saya akan segera proses untuk Anda.",
                    "Anda setuju untuk mengambil opsi perpanjangan dengan biaya Rp {extension_fee} ya? Kalau ya saya akan proses sekarang."
                ]
            },
            "answer_identity": {
                "*": [
                    "Saya adalah petugas penagihan dari aplikasi Extra Uang ya {name}. Saya menelpon tentang tagihan pinjaman {name} yang sudah jatuh tempo.",
                    "Saya dari tim penagihan Extra Uang ya, menelpon tentang tagihan pinjaman Anda yang sudah jatuh tempo.",
                    "Perkenalkan saya Budi dari Extra Uang, saya menelpon tentang tagihan pinjaman Anda yang sudah lewat jatuh tempo ya."
                ]
            },
            "handle_no_money": {
                "*": [
                    "Saya mengerti {name} sedang mengalami kesulitan keuangan. Apakah {name} bisa membayar sebagian dulu, atau mengambil opsi perpanjangan yang biayanya lebih ringan?",
                    "Saya paham sedang sulit uang ya. Apakah Anda bisa membayar sebagian dulu, atau mau ambil opsi perpanjangan yang cicilannya lebih kecil?",
                    "Saya mengerti kondisinya. Tapi kita harus cari solusi ya. Apakah Anda bisa membayar sedikit dulu, atau mau ambil opsi perpanjangan?"
                ]
            },
            "handle_threat": {
                "*": [
                    "Mohon maaf jika ada yang tidak berkenan ya {name}. Saya hanya ingin membantu menyelesaikan masalah tagihan ini dengan baik.",
                    "Maaf jika Anda merasa terganggu ya. Tujuan saya hanya ingin membantu mencari solusi terbaik untuk masalah tagihan Anda.",
                    "Saya minta maaf jika ada perkataan yang tidak berkenan. Mari kita bicara baik-baik untuk mencari solusi ya."
                ]
            },
            "handle_user_abuse": {
                "*": [
                    "Mohon bicara yang baik ya Bapak/Ibu. Saya di sini hanya ingin membantu menyelesaikan masalah tagihan Anda.",
                    "Saya mengerti Anda emosi, tapi mari kita bicara dengan baik ya. Tujuan saya hanya ingin mencari solusi terbaik untuk Anda.",
                    "Maaf jika Anda merasa kesal, tapi tolong bicara yang sopan ya. Saya di sini untuk membantu Anda menyelesaikan masalah tagihan."
                ]
            },
            "handle_wrong_number": {
                "*": [
                    "Mohon maaf ya, sepertinya saya salah nomor. Terima kasih atas waktunya.",
                    "Maaf ya, saya mencari Bapak/Ibu {name}. Sepertinya ini nomor yang salah. Mohon maaf atas gangguannya.",
                    "Saya minta maaf, sepertinya saya menghubungi nomor yang salah. Terima kasih."
                ]
            },
            "objection_general": {
                "H2": [
                    "Saya mengerti {name} keberatan, tapi kita harus selesaikan tagihan ini ya. Kira-kira kapan bisa bayar?",
                    "Paham, tapi bagaimana rencana pembayarannya ya?",
                    "Saya mengerti kondisinya, tapi tagihan ini harus segera diselesaikan ya. Kira-kira ada rencana bayar kapan?",
                    "Paham, mari kita cari solusi terbaik ya. Kira-kira kapan Anda bisa membayar tagihan ini?"
                ],
                "H1": [
                    "Saya mengerti kondisinya {name}, tapi tagihan ini harus segera diselesaikan ya. Kapan bisa bayar?",
                    "Saya paham Anda punya alasan, tapi kita harus selesaikan tagihan ini ya. Kira-kira bisa bayar kapan?",
                    "Saya mengerti, tapi tagihan ini sudah lama jatuh tempo ya. Kita harus segera cari solusi. Kira-kira kapan bisa bayar?"
                ],
                "S0": [
                    "Paham, tapi kita harus cari solusi untuk tagihan ini ya. Bagaimana rencananya?",
                    "Saya mengerti, tapi tagihan ini sudah lebih dari 3 bulan jatuh tempo ya. Kita harus segera selesaikan. Bagaimana rencana pembayarannya?",
                    "Paham, tapi ini sudah terlalu lama ya. Mari kita cari solusi yang terbaik untuk kedua pihak ya. Bagaimana rencana Anda?"
                ]
            }
        }

    def _get_script(self, category: str, **kwargs) -> str:
        """获取话术并替换变量"""
        # 先尝试获取对应催收阶段的话术，如果没有则用通配符"*"的话术
        category_scripts = self.script_lib.get(category, {})
        scripts = category_scripts.get(self.chat_group, [])
        if not scripts:
            scripts = category_scripts.get("*", [])

        script = random.choice(scripts) if scripts else ""

        # 合并变量，包括用户信息、欠款信息等
        vars = {
            "name": self.customer_name,
            "amount": f"{self.overdue_amount:,}",
            "days": str(self.overdue_days),
            "extension_fee": f"{self.extension_fee:,}"
        }
        vars.update(kwargs)

        return self.var_replacer.replace(script, **vars)

    async def process(
        self,
        customer_input: Optional[str] = None,
        use_tts: bool = False
    ) -> Tuple[str, Optional[str]]:
        """
        处理用户输入，返回回复
        返回: (文本回复, 音频文件路径)
        """
        start_time = datetime.now()

        # 初始状态，机器人先说话
        if self.state == ChatState.INIT:
            self.state = ChatState.IDENTITY_VERIFY
            identity_verify = self._get_script("identity_verify")
            self.conversation.append(ChatTurn(agent=identity_verify))
            audio_file = await self._tts_speak(identity_verify, use_tts)
            return identity_verify, audio_file

        # 记录用户输入
        if customer_input:
            # 先纠正ASR错误
            corrected_input = self.asr_corrector.correct(customer_input)
            self.conversation[-1].customer = corrected_input
            # 识别用户意图
            self.user_intent = self.intent_detector.detect(corrected_input)

        response = ""
        next_state = self.state

        # 状态机逻辑
        if self.state == ChatState.IDENTITY_VERIFY:
            # 先检查用户是否已经确认身份（即使同时表达了其他意图）
            identity_confirmed = False
            confirm_keywords = ["ya", "betul", "benar", "saya adalah", "ini saya", "ya ini",
                               "selamat pagi", "selamat siang", "selamat sore", "baik"]
            text_lower = corrected_input.lower() if corrected_input else ""

            for keyword in confirm_keywords:
                if keyword in text_lower:
                    identity_confirmed = True
                    break

            # 处理身份确认的回复
            if self.user_intent == "deny_identity":
                # 用户否认身份/打错电话，直接回复错号结束语，结束对话
                response = self._get_script("closing_wrong_number")
                next_state = ChatState.CLOSE
            elif self.user_intent == "busy_later":
                # 用户现在忙，回复忙的结束语，结束对话
                response = self._get_script("closing_busy")
                next_state = ChatState.CLOSE
            elif self.user_intent == "greeting":
                # 用户只是问候，继续确认身份
                response = self._get_script("identity_verify")
                next_state = ChatState.IDENTITY_VERIFY
            elif identity_confirmed:
                # 用户确认了身份，根据用户的实际意图处理
                if self.user_intent == "ask_extension":
                    # 用户询问展期，直接进入展期解释
                    response = self._get_script("explain_extension")
                    next_state = ChatState.CONFIRM_EXTENSION
                elif self.user_intent == "ask_amount":
                    # 用户询问金额，回答金额并进入询问时间阶段
                    response = self._get_script("answer_amount")
                    next_state = ChatState.ASK_TIME
                elif self.user_intent == "ask_fee":
                    # 用户询问费用，回答金额（包含费用说明）并进入询问时间阶段
                    response = self._get_script("answer_amount")
                    next_state = ChatState.ASK_TIME
                elif self.user_intent == "ask_payment_method":
                    # 用户询问支付方式，回答后进入询问时间阶段
                    response = self._get_script("answer_amount") + " " + self._get_script("ask_time")
                    next_state = ChatState.ASK_TIME
                elif self.user_intent == "already_paid":
                    # 用户说已经付款，确认后结束对话
                    response = "Oh, terima kasih ya. Mohon maaf atas gangguannya."
                    next_state = ChatState.CLOSE
                elif self.user_intent == "partial_payment":
                    # 用户询问部分还款，解释展期选项
                    response = self._get_script("explain_extension")
                    next_state = ChatState.CONFIRM_EXTENSION
                elif self.user_intent == "third_party":
                    # 第三方接听，结束对话
                    response = "Mohon maaf ya, saya akan hubungi kembali nanti. Terima kasih."
                    next_state = ChatState.CLOSE
                elif self.user_intent == "dont_know":
                    # 用户说不知道，继续说明来意
                    next_state = ChatState.PURPOSE
                    response = self._get_script("purpose")
                elif self.user_intent == "question_identity":
                    # 用户质疑身份，回答身份问题
                    response = self._get_script("answer_identity")
                    next_state = ChatState.PURPOSE
                elif self.user_intent == "no_money":
                    # 用户说没钱，处理没钱的情况
                    response = self._get_script("handle_no_money")
                    next_state = ChatState.HANDLE_OBJECTION
                elif self.user_intent == "threaten":
                    # 用户威胁，处理威胁的情况
                    response = self._get_script("handle_threat")
                    next_state = ChatState.HANDLE_OBJECTION
                elif self.user_intent == "refuse_to_pay":
                    # 用户拒绝还款，处理异议
                    response = self._get_script("objection_general")
                    next_state = ChatState.HANDLE_OBJECTION
                elif self.user_intent == "confirm_time":
                    # 用户直接给出了还款时间
                    detected_time = self.time_detector.detect(corrected_input or "")
                    if detected_time:
                        self.commit_time = detected_time
                        # 直接生成确认和结束语
                        commit_resp = self._get_script("commit_time", time=detected_time)
                        wait_script = self._get_script("wait", time=detected_time)
                        closing = self._get_script("closing")
                        response = f"{commit_resp} {wait_script} {closing}"
                        next_state = ChatState.CLOSE
                    else:
                        # 进入询问时间阶段
                        next_state = ChatState.ASK_TIME
                        response = self._get_script("ask_time")
                elif self.user_intent == "confirm_identity" or self.user_intent == "agree_to_pay":
                    # 用户只是确认身份，进入来意说明
                    next_state = ChatState.PURPOSE
                    response = self._get_script("purpose")
                else:
                    # 其他意图，先进入来意说明
                    next_state = ChatState.PURPOSE
                    response = self._get_script("purpose")
            else:
                # 没有确认身份，再次确认身份
                response = self._get_script("identity_verify")
                next_state = ChatState.IDENTITY_VERIFY

        elif self.state == ChatState.PURPOSE:
            # 说明来意后，处理用户的回复
            if self.user_intent == "ask_amount":
                # 用户询问金额
                response = self._get_script("answer_amount")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "ask_fee":
                # 用户询问费用
                response = self._get_script("answer_amount")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "ask_payment_method":
                # 用户询问支付方式
                response = self._get_script("answer_amount") + " " + self._get_script("ask_time")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "already_paid":
                # 用户说已经付款
                response = "Oh, terima kasih ya. Mohon maaf atas gangguannya."
                next_state = ChatState.CLOSE
            elif self.user_intent == "partial_payment":
                # 用户询问部分还款
                response = self._get_script("explain_extension")
                next_state = ChatState.CONFIRM_EXTENSION
            elif self.user_intent == "third_party":
                # 第三方接听
                response = "Mohon maaf ya, saya akan hubungi kembali nanti. Terima kasih."
                next_state = ChatState.CLOSE
            elif self.user_intent == "dont_know":
                # 用户说不知道，再次说明来意
                response = self._get_script("purpose")
                next_state = ChatState.PURPOSE
            elif self.user_intent == "ask_extension":
                # 用户询问展期
                response = self._get_script("explain_extension")
                next_state = ChatState.CONFIRM_EXTENSION
            elif self.user_intent == "busy_later":
                # 用户现在忙
                response = self._get_script("closing_busy")
                next_state = ChatState.CLOSE
            elif self.user_intent == "question_identity":
                # 用户质疑身份
                response = self._get_script("answer_identity")
                next_state = ChatState.PURPOSE
            elif self.user_intent == "no_money":
                # 用户说没钱
                response = self._get_script("handle_no_money")
                next_state = ChatState.HANDLE_OBJECTION
            elif self.user_intent == "threaten":
                # 用户威胁
                response = self._get_script("handle_threat")
                next_state = ChatState.HANDLE_OBJECTION
            elif self.user_intent == "confirm_time":
                # 用户直接给出了还款时间
                detected_time = self.time_detector.detect(corrected_input or "")
                if detected_time:
                    self.commit_time = detected_time
                    # 直接生成确认和结束语，不需要再走COMMIT_TIME状态
                    commit_resp = self._get_script("commit_time", time=detected_time)
                    wait_script = self._get_script("wait", time=detected_time)
                    closing = self._get_script("closing")
                    response = f"{commit_resp} {wait_script} {closing}"
                    next_state = ChatState.CLOSE
                else:
                    next_state = ChatState.ASK_TIME
                    response = self._get_script("ask_time")
            else:
                # 其他情况，进入询问还款时间环节
                next_state = ChatState.ASK_TIME
                response = self._get_script("ask_time")

        elif self.state == ChatState.CONFIRM_EXTENSION:
            # 确认用户是否同意展期
            if self.user_intent == "agree_to_pay" or "ya" in (corrected_input or "").lower():
                # 用户同意展期
                self.extension_agreed = True
                response = self._get_script("ask_time")
                next_state = ChatState.ASK_TIME
            else:
                # 用户不同意，继续询问还款时间
                response = self._get_script("ask_time")
                next_state = ChatState.ASK_TIME

        elif self.state == ChatState.ASK_TIME:
            # 询问还款时间后，处理用户回复
            detected_time = self.time_detector.detect(corrected_input or "")
            if detected_time:
                # 用户给出了时间，直接生成确认和结束语，结束对话
                self.commit_time = detected_time
                commit_resp = self._get_script("commit_time", time=detected_time)
                wait_script = self._get_script("wait", time=detected_time)
                closing = self._get_script("closing")
                response = f"{commit_resp} {wait_script} {closing}"
                next_state = ChatState.CLOSE
            elif self.user_intent == "ask_extension":
                # 用户询问展期
                response = self._get_script("explain_extension")
                next_state = ChatState.CONFIRM_EXTENSION
            elif self.user_intent == "ask_amount" or self.user_intent == "ask_fee":
                # 用户再次询问金额/费用
                response = self._get_script("answer_amount")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "ask_payment_method":
                # 用户询问支付方式
                response = self._get_script("answer_amount")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "already_paid":
                # 用户说已经付款
                response = "Oh, terima kasih ya. Mohon maaf atas gangguannya."
                next_state = ChatState.CLOSE
            elif self.user_intent == "partial_payment":
                # 用户询问部分还款
                response = self._get_script("explain_extension")
                next_state = ChatState.CONFIRM_EXTENSION
            elif self.user_intent == "third_party":
                # 第三方接听
                response = "Mohon maaf ya, saya akan hubungi kembali nanti. Terima kasih."
                next_state = ChatState.CLOSE
            elif self.user_intent == "dont_know":
                # 用户说不知道，再次询问时间
                response = self._get_script("ask_time")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "busy_later":
                # 用户现在忙
                response = self._get_script("closing_busy")
                next_state = ChatState.CLOSE
            elif self.user_intent == "no_money":
                # 用户说没钱
                response = self._get_script("handle_no_money")
                next_state = ChatState.HANDLE_OBJECTION
            elif self.user_intent == "refuse_to_pay":
                # 用户拒绝还款
                response = self._get_script("objection_general")
                next_state = ChatState.HANDLE_OBJECTION
            else:
                # 没有检测到时间，催促用户
                if self.objection_count < self.max_objections:
                    self.objection_count += 1
                    next_state = ChatState.PUSH_FOR_TIME
                    response = self._get_script("push")
                else:
                    next_state = ChatState.FAILED
                    response = ""

        elif self.state == ChatState.PUSH_FOR_TIME:
            # 催促后，处理用户回复
            detected_time = self.time_detector.detect(corrected_input or "")
            if detected_time:
                # 用户给出了时间，直接生成确认和结束语，结束对话
                self.commit_time = detected_time
                commit_resp = self._get_script("commit_time", time=detected_time)
                wait_script = self._get_script("wait", time=detected_time)
                closing = self._get_script("closing")
                response = f"{commit_resp} {wait_script} {closing}"
                next_state = ChatState.CLOSE
            else:
                if self.objection_count < self.max_objections:
                    self.objection_count += 1
                    response = self._get_script("push")
                else:
                    next_state = ChatState.FAILED
                    response = ""

        elif self.state == ChatState.HANDLE_OBJECTION:
            # 处理一般异议
            if self.user_intent == "ask_extension":
                response = self._get_script("explain_extension")
                next_state = ChatState.CONFIRM_EXTENSION
            elif self.user_intent == "partial_payment":
                # 用户询问部分还款
                response = self._get_script("explain_extension")
                next_state = ChatState.CONFIRM_EXTENSION
            elif self.user_intent == "ask_amount" or self.user_intent == "ask_fee":
                # 用户询问金额/费用
                response = self._get_script("answer_amount")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "ask_payment_method":
                # 用户询问支付方式
                response = self._get_script("answer_amount")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "already_paid":
                # 用户说已经付款
                response = "Oh, terima kasih ya. Mohon maaf atas gangguannya."
                next_state = ChatState.CLOSE
            elif self.user_intent == "third_party":
                # 第三方接听
                response = "Mohon maaf ya, saya akan hubungi kembali nanti. Terima kasih."
                next_state = ChatState.CLOSE
            elif self.user_intent == "dont_know":
                # 用户说不知道，继续询问时间
                response = self._get_script("objection_general")
                next_state = ChatState.ASK_TIME
            elif self.user_intent == "busy_later":
                # 用户现在忙
                response = self._get_script("closing_busy")
                next_state = ChatState.CLOSE
            elif self.user_intent == "threaten":
                # 用户再次威胁
                response = self._get_script("handle_threat")
                next_state = ChatState.HANDLE_OBJECTION
            elif self.user_intent == "refuse_to_pay":
                # 用户拒绝还款，继续处理异议
                response = self._get_script("objection_general")
                next_state = ChatState.HANDLE_OBJECTION
            else:
                # 其他异议，返回通用回复，继续询问还款时间
                response = self._get_script("objection_general")
                next_state = ChatState.ASK_TIME

        elif self.state == ChatState.CLOSE or self.state == ChatState.FAILED:
            response = ""

        # 记录机器人回复
        if response:
            self.conversation.append(ChatTurn(agent=response))

        self.state = next_state
        audio_file = await self._tts_speak(response, use_tts)
        return response, audio_file

    async def _tts_speak(self, text: str, use_tts: bool) -> Optional[str]:
        """TTS说话"""
        if not use_tts or not text:
            return None
        return await self.tts.synthesize(text)

    def is_finished(self) -> bool:
        """对话是否结束"""
        return self.state in [ChatState.CLOSE, ChatState.FAILED]

    def is_successful(self) -> bool:
        """对话是否成功（获取到还款时间，或者用户同意展期并给出时间）"""
        return self.state == ChatState.CLOSE and self.commit_time is not None

    def get_log(self) -> ConversationLog:
        """获取对话日志"""
        return ConversationLog(
            session_id=self.session_id,
            chat_group=self.chat_group,
            customer_info={"name": self.customer_name},
            turns=self.conversation.copy(),
            success=self.is_successful(),
            commit_time=self.commit_time,
            end_time=datetime.now().isoformat()
        )

    def reset(self, chat_group: str = "H2", customer_name: Optional[str] = None):
        """重置状态"""
        self.chat_group = chat_group
        self.customer_name = customer_name or "Pak/Bu"
        self.state = ChatState.INIT
        self.conversation = []
        self.commit_time = None
        self.objection_count = 0
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")


class CustomerSimulator:
    """模拟客户回应 - 扩展版"""

    def __init__(self, persona: str = "cooperative"):
        self.persona = persona
        self._init_responses()

    def _init_responses(self):
        """初始化客户回应库"""
        self.customer_responses = {
            "cooperative": {
                "greeting": ["Halo.", "Pagi.", "Siang.", "Sore.", "Iya?"],
                "identity": ["Iya.", "Ya.", "Ya, betul."],
                "purpose": ["Oh, ingatnya.", "Ya.", "Oh ya."],
                "ask_time": ["Jam 5 ya.", "Jam 4.", "Jam 3.", "Besok jam 2."],
                "push": ["Hari ini jam 5.", "Besok jam 3."],
                "commit": ["Iya.", "Ya.", "Oke."],
                "confirm": ["Iya.", "Ya.", "Oke."],
                "close": ["Terima kasih.", "Terima kasih kembali."]
            },
            "busy": {
                "greeting": ["Sibuk.", "Ada apa?", "Sebentar ya."],
                "identity": ["Sibuk nih.", "Nanti ya."],
                "purpose": ["Saya lagi sibuk.", "Nanti saya hubungi balik."],
                "ask_time": ["Saya lagi luar.", "Nanti ya."],
                "push": ["Jam 5 deh."],
                "commit": ["Iya deh.", "Oke."],
                "confirm": ["Ya."],
                "close": ["Iya."]
            },
            "negotiating": {
                "greeting": ["Halo.", "Ada apa?"],
                "identity": ["Ya."],
                "purpose": ["Oh, bisa nggak diperpanjang?"],
                "ask_time": ["Minggu ini bisa?", "Besok bisa?"],
                "push": ["Besok jam 3."],
                "commit": ["Oke, besok jam 3."],
                "confirm": ["Iya."],
                "close": ["Terima kasih."]
            },
            "resistant": {
                "greeting": ["Halo?", "Apaan sih?"],
                "identity": ["Ya, apa?"],
                "purpose": ["Aduh, saya lagi susah.", "Nanti dulu ya."],
                "ask_time": ["Saya belum punya duit.", "Gak bisa."],
                "push": ["Saya benar-benar belum bisa."],
                "commit": [],
                "confirm": [],
                "close": []
            },
            "silent": {
                "greeting": ["...", "", "Iya?"],
                "identity": ["...", "Ya."],
                "purpose": ["...", "Oh."],
                "ask_time": ["...", "Jam 5."],
                "push": ["Jam 5."],
                "commit": ["Iya."],
                "confirm": ["Iya."],
                "close": ["..."]
            },
            "forgetful": {
                "greeting": ["Halo?", "Oh iya."],
                "identity": ["Ya."],
                "purpose": ["Oh ya, saya lupa."],
                "ask_time": ["Nanti ya.", "Sebentar lagi."],
                "push": ["Jam 4 deh."],
                "commit": ["Oke."],
                "confirm": ["Iya."],
                "close": ["Terima kasih."]
            }
        }

    def respond(self, stage: str, agent_said: str) -> str:
        """生成客户回应"""
        if self.persona not in self.customer_responses:
            self.persona = "cooperative"

        responses = self.customer_responses[self.persona].get(stage, [])
        if not responses:
            responses = self.customer_responses["cooperative"].get(stage, ["Iya."])

        return random.choice(responses)


def get_stage_from_state(state: ChatState) -> str:
    """从状态获取阶段名称"""
    stage_map = {
        ChatState.INIT: "greeting",
        ChatState.GREETING: "greeting",
        ChatState.IDENTITY_VERIFY: "identity",
        ChatState.PURPOSE: "purpose",
        ChatState.HANDLE_OBJECTION: "negotiate",
        ChatState.CONFIRM_EXTENSION: "negotiate",
        ChatState.ASK_TIME: "ask_time",
        ChatState.PUSH_FOR_TIME: "push",
        ChatState.COMMIT_TIME: "commit",
        ChatState.HANDLE_BUSY: "close",
        ChatState.HANDLE_WRONG_NUMBER: "close",
        ChatState.CLOSE: "close",
        ChatState.FAILED: "close",
    }
    return stage_map.get(state, "greeting")


async def run_conversation_test(
    chat_group: str = "H2",
    customer_persona: str = "cooperative",
    max_turns: int = 15,
    verbose: bool = True,
    use_tts: bool = False
) -> Dict:
    """运行对话测试"""
    bot = CollectionChatBot(chat_group)
    customer = CustomerSimulator(customer_persona)

    if verbose:
        print(f"\n{'='*70}")
        print(f"场景: {chat_group}环节, 客户类型: {customer_persona}")
        print(f"{'='*70}")

    agent_says, audio_file = await bot.process(use_tts=use_tts)
    if verbose:
        print(f"AGENT: {agent_says}")
        if audio_file:
            print(f"       [音频: {audio_file}]")

    for turn in range(max_turns):
        if bot.is_finished():
            break

        current_stage = get_stage_from_state(bot.state)
        customer_says = customer.respond(current_stage, agent_says)

        if verbose:
            print(f"CUSTOMER: {customer_says}")

        agent_says, audio_file = await bot.process(customer_says, use_tts=use_tts)

        if agent_says:
            if verbose:
                print(f"AGENT: {agent_says}")
                if audio_file:
                    print(f"       [音频: {audio_file}]")
        else:
            if verbose:
                print("AGENT: [对话结束]")
            break

    success = bot.is_successful()
    log = bot.get_log()

    if verbose:
        print(f"\n{'='*70}")
        status_msg = "SUCCESS" if success else "FAILED"
        print(f"对话结束: {status_msg}")
        if bot.commit_time:
            print(f"约定时间: {bot.commit_time}")
        print(f"{'='*70}")

    return {
        "session_id": bot.session_id,
        "chat_group": chat_group,
        "customer_persona": customer_persona,
        "success": success,
        "commit_time": bot.commit_time,
        "log": log
    }


async def run_test_suite(use_tts: bool = False):
    """运行完整测试套件"""
    test_scenarios = [
        ("H2", "cooperative", "H2早期 + 合作客户"),
        ("H2", "busy", "H2早期 + 忙碌客户"),
        ("H2", "negotiating", "H2早期 + 协商客户"),
        ("H2", "silent", "H2早期 + 沉默客户"),
        ("H2", "forgetful", "H2早期 + 健忘客户"),
        ("H1", "cooperative", "H1中期 + 合作客户"),
        ("H1", "negotiating", "H1中期 + 协商客户"),
        ("H1", "busy", "H1中期 + 忙碌客户"),
        ("H1", "forgetful", "H1中期 + 健忘客户"),
        ("S0", "cooperative", "S0晚期 + 合作客户"),
        ("S0", "negotiating", "S0晚期 + 协商客户"),
        ("S0", "resistant", "S0晚期 + 抗拒客户"),
        ("S0", "silent", "S0晚期 + 沉默客户"),
        ("S0", "forgetful", "S0晚期 + 健忘客户"),
    ]

    print(f"\n{'='*80}")
    print(f"开始测试 {len(test_scenarios)} 个场景")
    print(f"{'='*80}")

    results = []
    all_logs = []

    for i, (chat_group, persona, desc) in enumerate(test_scenarios, 1):
        print(f"\n\n--- 场景 {i}: {desc} ---")
        result = await run_conversation_test(
            chat_group, persona, verbose=True, use_tts=use_tts
        )
        results.append(result)
        all_logs.append(result["log"])

    # 汇总结果
    print(f"\n\n{'='*80}")
    print(f"测试结果汇总")
    print(f"{'='*80}")

    for i, result in enumerate(results, 1):
        status = "SUCCESS" if result["success"] else "FAILED"
        time_info = f" (时间: {result['commit_time']})" if result["commit_time"] else ""
        print(f"{i:2d}. {result['chat_group']:2s} + {result['customer_persona']:12s}: {status}{time_info}")

    success_count = sum(1 for r in results if r["success"])
    print(f"\n总体成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

    # 保存结果
    output_dir = Path("data/chatbot_tests")
    output_dir.mkdir(parents=True, exist_ok=True)

    results_file = output_dir / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump([{
            "session_id": r["session_id"],
            "chat_group": r["chat_group"],
            "customer_persona": r["customer_persona"],
            "success": r["success"],
            "commit_time": r["commit_time"]
        } for r in results], f, ensure_ascii=False, indent=2)

    # 保存详细日志
    logs_file = output_dir / f"test_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(logs_file, "w", encoding="utf-8") as f:
        json.dump([{
            "session_id": log.session_id,
            "chat_group": log.chat_group,
            "customer_info": log.customer_info,
            "success": log.success,
            "commit_time": log.commit_time,
            "start_time": log.start_time,
            "end_time": log.end_time,
            "turns": [{"agent": t.agent, "customer": t.customer, "timestamp": t.timestamp} for t in log.turns]
        } for log in all_logs], f, ensure_ascii=False, indent=2)

    print(f"\n完整结果已保存到:")
    print(f"  - {results_file}")
    print(f"  - {logs_file}")

    return results


async def interactive_chat(chat_group: str = "H2", use_tts: bool = False):
    """交互式对话模式"""
    print(f"\n{'='*70}")
    print(f"交互式对话模式 - {chat_group}环节")
    print(f"{'='*70}")
    print("输入 'quit' 或 'exit' 退出\n")

    bot = CollectionChatBot(chat_group)

    agent_says, audio_file = await bot.process(use_tts=use_tts)
    print(f"AGENT: {agent_says}")
    if audio_file:
        print(f"       [音频: {audio_file}]")

    while not bot.is_finished():
        try:
            customer_input = input("CUSTOMER: ").strip()

            if customer_input.lower() in ["quit", "exit", "q"]:
                print("\n结束对话")
                break

            agent_says, audio_file = await bot.process(customer_input, use_tts=use_tts)

            if agent_says:
                print(f"AGENT: {agent_says}")
                if audio_file:
                    print(f"       [音频: {audio_file}]")

        except KeyboardInterrupt:
            print("\n\n结束对话")
            break

    print(f"\n结果: {'成功' if bot.is_successful() else '失败'}")
    if bot.commit_time:
        print(f"约定时间: {bot.commit_time}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能催收对话机器人 v3")
    parser.add_argument("--mode", choices=["test", "interactive"], default="test", help="运行模式")
    parser.add_argument("--chat-group", choices=["H2", "H1", "S0"], default="H2", help="催收环节")
    parser.add_argument("--use-tts", action="store_true", help="启用TTS语音合成")
    parser.add_argument("--persona", default="cooperative", help="客户类型 (测试模式)")

    args = parser.parse_args()

    print("="*70)
    print("智能催收对话机器人 v3")
    print("  - 集成TTS语音合成")
    print("  - 完善状态机逻辑")
    print("  - 支持变量替换")
    print("  - 对话日志记录")
    print("="*70)

    if args.mode == "interactive":
        asyncio.run(interactive_chat(args.chat_group, use_tts=args.use_tts))
    else:
        asyncio.run(run_test_suite(use_tts=args.use_tts))


if __name__ == "__main__":
    main()
