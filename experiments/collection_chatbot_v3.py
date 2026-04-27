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
    IDENTIFY = auto()
    PURPOSE = auto()
    ASK_TIME = auto()
    PUSH_FOR_TIME = auto()
    COMMIT_TIME = auto()
    CONFIRM = auto()
    CLOSE = auto()
    FAILED = auto()
    HANDLE_OBJECTION = auto()


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
    """时间检测器 - 增强版"""

    TIME_PATTERNS = [
        ("jam 12", ["jam 12", "12 siang"]),
        ("jam 11", ["jam 11"]),
        ("jam 10", ["jam 10"]),
        ("jam 9", ["jam 9"]),
        ("jam 8", ["jam 8"]),
        ("jam 7", ["jam 7"]),
        ("jam 6", ["jam 6"]),
        ("jam 5", ["jam 5"]),
        ("jam 4", ["jam 4"]),
        ("jam 3", ["jam 3"]),
        ("jam 2", ["jam 2"]),
        ("jam 1", ["jam 1"]),
        ("hari ini", ["hari ini", "sekarang", "hari ini siang"]),
        ("besok", ["besok", "besok pagi", "besok siang", "besok sore"]),
        ("lusa", ["lusa"]),
        ("minggu ini", ["minggu ini"]),
        ("nanti", ["nanti", "nanti sore", "nanti pagi"]),
    ]

    @classmethod
    def detect(cls, text: str) -> Optional[str]:
        """检测时间"""
        if not text:
            return None

        text_lower = text.lower()

        for time_value, patterns in cls.TIME_PATTERNS:
            for pattern in patterns:
                if pattern in text_lower:
                    return time_value

        # 通用jam检测
        if "jam" in text_lower:
            words = text_lower.split()
            for i, word in enumerate(words):
                if word == "jam" and i < len(words) - 1:
                    return f"jam {words[i+1]}"

        return None


class CollectionChatBot:
    """催收对话机器人 - 增强版"""

    def __init__(self, chat_group: str = "H2", customer_name: Optional[str] = None):
        self.chat_group = chat_group
        self.customer_name = customer_name or "Pak/Bu"
        self.state: ChatState = ChatState.INIT
        self.conversation: List[ChatTurn] = []
        self.commit_time: Optional[str] = None
        self.objection_count: int = 0
        self.max_objections: int = 3

        # TTS
        self.tts = TextToSpeech()
        self.var_replacer = VariableReplacer()
        self.time_detector = TimeDetector()

        # 会话ID
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 话术库 - 扩展版
        self._init_script_lib()

    def _init_script_lib(self):
        """初始化话术库"""
        self.script_lib = {
            "greeting": {
                "H2": ["Halo?", "Halo.", "Hello?"],
                "H1": ["Halo?", "Halo.", "Halo, selamat pagi."],
                "S0": ["Halo?", "Halo."]
            },
            "greeting_response": {
                "H2": ["Halo, selamat pagi {name}.", "Halo, selamat siang {name}."],
                "H1": ["Halo, selamat pagi {name}.", "Halo, selamat siang {name}."],
                "S0": ["Halo, selamat sore {name}."]
            },
            "identify": {
                "H2": ["Saya dari aplikasi Extra."],
                "H1": ["Saya dari aplikasi Extra."],
                "S0": ["Saya dari aplikasi Extra."]
            },
            "purpose": {
                "H2": ["Untuk pinjaman ya {name}."],
                "H1": ["Untuk pinjaman yang sudah jatuh tempo."],
                "S0": ["Kita bicara tentang pinjaman yang sudah agak lama ya {name}."]
            },
            "ask_time": {
                "H2": ["Kapan bisa bayar {name}?", "Jam berapa ya?"],
                "H1": ["Kapan bisa melakukan pembayaran?", "Jam berapa ya?"],
                "S0": ["Bagaimana rencana pembayaran {name}?", "Kapan bisa bayar ya?"]
            },
            "push": {
                "H2": ["Jam berapa tepatnya?", "Hari ini jam berapa ya?"],
                "H1": ["Jam berapa tepatnya?", "Besok jam berapa ya?"],
                "S0": ["Jam berapa tepatnya?", "Hari apa ya?", "Jam berapa ya?"]
            },
            "commit_time": {
                "H2": ["Oke, {time} ya {name}.", "Ya, ya, ya. {time} ya {name}."],
                "H1": ["Ya, ya. Oke, {time} ya {name}.", "Saya tunggu {time}."],
                "S0": ["Ya, ya, ya. Oke, {time} ya {name}."]
            },
            "confirm": {
                "H2": ["Ya, ya, ya.", "Iya.", "Baik."],
                "H1": ["Ya, ya.", "Iya.", "Baik."],
                "S0": ["Ya, ya, ya.", "Baik."]
            },
            "wait": {
                "H2": ["Saya tunggu ya.", "Saya tunggu {time}."],
                "H1": ["Saya tunggu ya."],
                "S0": ["Saya tunggu ya."]
            },
            "closing": {
                "H2": ["Terima kasih.", "Terima kasih. Selamat pagi."],
                "H1": ["Terima kasih.", "Terima kasih. Selamat siang."],
                "S0": ["Terima kasih.", "Terima kasih. Selamat sore."]
            },
            "objection": {
                "H2": ["Saya mengerti, tapi kapan bisa bayar?", "Paham, tapi kita harus selesaikan ini."],
                "H1": ["Saya mengerti, tapi kapan bisa bayar ya?"],
                "S0": ["Paham, tapi bagaimana rencananya?"]
            }
        }

    def _get_script(self, category: str, **kwargs) -> str:
        """获取话术并替换变量"""
        scripts = self.script_lib.get(category, {}).get(self.chat_group, [])
        script = random.choice(scripts) if scripts else ""

        # 合并变量
        vars = {"name": self.customer_name}
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

        if self.state == ChatState.INIT:
            self.state = ChatState.GREETING
            greeting = self._get_script("greeting")
            self.conversation.append(ChatTurn(agent=greeting))
            audio_file = await self._tts_speak(greeting, use_tts)
            return greeting, audio_file

        if customer_input:
            self.conversation[-1].customer = customer_input

        response = ""
        next_state = self.state

        if self.state == ChatState.GREETING:
            next_state = ChatState.IDENTIFY
            greeting_resp = self._get_script("greeting_response")
            identify = self._get_script("identify")
            response = f"{greeting_resp} {identify}"

        elif self.state == ChatState.IDENTIFY:
            next_state = ChatState.PURPOSE
            response = self._get_script("purpose")

        elif self.state == ChatState.PURPOSE:
            next_state = ChatState.ASK_TIME
            response = self._get_script("ask_time")

        elif self.state == ChatState.ASK_TIME:
            detected_time = self.time_detector.detect(customer_input or "")
            if detected_time:
                self.commit_time = detected_time
                next_state = ChatState.COMMIT_TIME
                response = self._get_script("commit_time", time=detected_time)
            else:
                if self.objection_count < self.max_objections:
                    self.objection_count += 1
                    next_state = ChatState.PUSH_FOR_TIME
                    response = self._get_script("push")
                else:
                    next_state = ChatState.FAILED
                    response = ""

        elif self.state == ChatState.PUSH_FOR_TIME:
            detected_time = self.time_detector.detect(customer_input or "")
            if detected_time:
                self.commit_time = detected_time
                next_state = ChatState.COMMIT_TIME
                response = self._get_script("commit_time", time=detected_time)
            else:
                if self.objection_count < self.max_objections:
                    self.objection_count += 1
                    response = self._get_script("push")
                else:
                    next_state = ChatState.FAILED
                    response = ""

        elif self.state == ChatState.COMMIT_TIME:
            next_state = ChatState.CONFIRM
            response = self._get_script("confirm")

        elif self.state == ChatState.CONFIRM:
            next_state = ChatState.CLOSE
            wait_script = self._get_script("wait", time=self.commit_time) if self.commit_time else "Saya tunggu ya."
            closing = self._get_script("closing")
            response = f"{wait_script} {closing}"

        elif self.state == ChatState.CLOSE:
            response = ""

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
        """对话是否成功（获取到还款时间）"""
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
        ChatState.IDENTIFY: "identity",
        ChatState.PURPOSE: "purpose",
        ChatState.ASK_TIME: "ask_time",
        ChatState.PUSH_FOR_TIME: "push",
        ChatState.COMMIT_TIME: "commit",
        ChatState.CONFIRM: "confirm",
        ChatState.CLOSE: "close",
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
