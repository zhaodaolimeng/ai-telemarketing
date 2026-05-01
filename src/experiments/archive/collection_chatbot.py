#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能催收对话机器人 - 文本版本
基于246条对话分析
"""
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple


class ChatState(Enum):
    INIT = auto()
    GREETING = auto()
    IDENTIFY = auto()
    PURPOSE = auto()
    ASK_TIME = auto()
    COMMIT_TIME = auto()
    CONFIRM = auto()
    CLOSE = auto()
    FAILED = auto()


@dataclass
class ChatTurn:
    agent: str
    customer: Optional[str] = None


class CollectionChatBot:
    def __init__(self, chat_group: str = "H2"):
        self.chat_group = chat_group
        self.state: ChatState = ChatState.INIT
        self.conversation: List[ChatTurn] = []
        self.commit_time: Optional[str] = None
        self.customer_name: Optional[str] = None

        # 话术库 - 基于分析结果
        self.script_lib = {
            "greeting": {
                "H2": ["Halo?", "Halo.", "Hello?"],
                "H1": ["Halo?", "Halo.", "Halo, selamat pagi."],
                "S0": ["Halo?", "Halo."]
            },
            "greeting_response": {
                "H2": ["Halo, selamat pagi Pak/Bu.", "Halo, selamat siang Pak/Bu.", "Halo, selamat sore Pak/Bu."],
                "H1": ["Halo, selamat pagi Pak/Bu.", "Halo, selamat siang Pak/Bu."],
                "S0": ["Halo, selamat sore Pak/Bu."]
            },
            "identify": {
                "H2": ["Saya dari aplikasi Extra."],
                "H1": ["Saya dari aplikasi Extra."],
                "S0": ["Saya dari aplikasi Extra."]
            },
            "purpose": {
                "H2": ["Untuk pinjaman ya Pak/Bu."],
                "H1": ["Untuk pinjaman yang sudah jatuh tempo."],
                "S0": ["Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu."]
            },
            "ask_time": {
                "H2": ["Kapan bisa bayar Pak/Bu?", "Jam berapa ya?"],
                "H1": ["Kapan bisa melakukan pembayaran?", "Jam berapa ya?"],
                "S0": ["Bagaimana rencana pembayaran Pak/Bu?", "Kapan bisa bayar ya?"]
            },
            "commit_time": {
                "H2": ["Oke, jam {time} ya Pak/Bu.", "Ya, ya, ya. Jam {time} ya Pak/Bu.", "Baik, saya tunggu jam {time}."],
                "H1": ["Ya, ya. Oke, jam {time} ya Pak/Bu.", "Saya tunggu jam {time}."],
                "S0": ["Ya, ya, ya. Oke, {time} ya Pak/Bu.", "Baik, saya tunggu {time}."]
            },
            "confirm": {
                "H2": ["Ya, ya, ya.", "Iya.", "Baik.", "Ya, ya."],
                "H1": ["Ya, ya.", "Iya.", "Baik."],
                "S0": ["Ya, ya, ya.", "Baik."]
            },
            "wait": {
                "H2": ["Saya tunggu ya.", "Saya tunggu jam {time}."],
                "H1": ["Saya tunggu ya."],
                "S0": ["Saya tunggu ya."]
            },
            "closing": {
                "H2": ["Terima kasih.", "Terima kasih. Selamat pagi.", "Terima kasih. Selamat siang.", "Terima kasih. Selamat sore."],
                "H1": ["Terima kasih.", "Terima kasih. Selamat siang."],
                "S0": ["Terima kasih.", "Terima kasih. Selamat sore."]
            },
            "push": {
                "H2": ["Jam berapa tepatnya?", "Hari ini jam berapa ya?"],
                "H1": ["Jam berapa tepatnya?", "Besok jam berapa ya?"],
                "S0": ["Jam berapa tepatnya?", "Hari apa ya?", "Jam berapa ya?"]
            }
        }

        # 停顿标记
        self.pause_mark = "..."

    def reset(self, chat_group: str = "H2"):
        self.chat_group = chat_group
        self.state = ChatState.INIT
        self.conversation = []
        self.commit_time = None
        self.customer_name = None

    def _get_script(self, category: str, **kwargs) -> str:
        scripts = self.script_lib.get(category, {}).get(self.chat_group, [])
        script = random.choice(scripts) if scripts else ""
        if kwargs:
            script = script.format(**kwargs)
        return script

    def _detect_time(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        if "jam 5" in text_lower or "jam 5." in text_lower:
            return "jam 5"
        if "jam 4" in text_lower or "jam 4." in text_lower:
            return "jam 4"
        if "jam 3" in text_lower or "jam 3." in text_lower:
            return "jam 3"
        if "jam 2" in text_lower or "jam 2." in text_lower:
            return "jam 2"
        if "jam 1" in text_lower or "jam 1." in text_lower:
            return "jam 1"
        if "jam 8" in text_lower or "jam 8." in text_lower:
            return "jam 8"
        if "hari ini" in text_lower:
            return "hari ini"
        if "besok" in text_lower:
            return "besok"
        if "jam" in text_lower:
            words = text_lower.split()
            for i, word in enumerate(words):
                if word == "jam" and i < len(words) - 1:
                    return f"jam {words[i+1]}"
        return None

    def process(self, customer_input: Optional[str] = None) -> str:
        if self.state == ChatState.INIT:
            self.state = ChatState.GREETING
            greeting = self._get_script("greeting")
            self.conversation.append(ChatTurn(agent=greeting))
            return greeting

        if customer_input:
            self.conversation[-1].customer = customer_input

        if self.state == ChatState.GREETING:
            self.state = ChatState.IDENTIFY
            greeting_resp = self._get_script("greeting_response")
            identify = self._get_script("identify")
            response = f"{greeting_resp} {identify}"
            self.conversation.append(ChatTurn(agent=response))
            return response

        if self.state == ChatState.IDENTIFY:
            self.state = ChatState.PURPOSE
            purpose = self._get_script("purpose")
            self.conversation.append(ChatTurn(agent=purpose))
            return purpose

        if self.state == ChatState.PURPOSE:
            self.state = ChatState.ASK_TIME
            ask_time = self._get_script("ask_time")
            self.conversation.append(ChatTurn(agent=ask_time))
            return ask_time

        if self.state == ChatState.ASK_TIME:
            detected_time = self._detect_time(customer_input or "")
            if detected_time:
                self.commit_time = detected_time
                self.state = ChatState.COMMIT_TIME
                commit = self._get_script("commit_time", time=detected_time)
                self.conversation.append(ChatTurn(agent=commit))
                return commit
            else:
                push = self._get_script("push")
                self.conversation.append(ChatTurn(agent=push))
                return push

        if self.state == ChatState.COMMIT_TIME:
            self.state = ChatState.CONFIRM
            confirm = self._get_script("confirm")
            self.conversation.append(ChatTurn(agent=confirm))
            return confirm

        if self.state == ChatState.CONFIRM:
            self.state = ChatState.CLOSE
            wait_script = self._get_script("wait", time=self.commit_time) if self.commit_time else "Saya tunggu ya."
            closing = self._get_script("closing")
            response = f"{wait_script} {closing}"
            self.conversation.append(ChatTurn(agent=response))
            return response

        if self.state == ChatState.CLOSE:
            return ""

        return ""


class CustomerSimulator:
    """模拟客户回应"""

    def __init__(self, persona: str = "cooperative"):
        self.persona = persona

        # 不同客户类型的回应库
        self.customer_responses = {
            "cooperative": {
                "greeting": ["Halo.", "Pagi.", "Siang.", "Sore.", "Iya?"],
                "identity": ["Iya.", "Ya.", "Ya, betul."],
                "purpose": ["Oh, ingatnya.", "Ya.", "Oh ya."],
                "ask_time": ["Jam 5 ya.", "Jam 4.", "Jam 3.", "Besok jam 2."],
                "commit": ["Iya.", "Ya.", "Oke."],
                "confirm": ["Iya.", "Ya.", "Oke."],
                "close": ["Terima kasih.", "Terima kasih kembali."]
            },
            "busy": {
                "greeting": ["Sibuk.", "Ada apa?", "Sebentar ya."],
                "identity": ["Sibuk nih.", "Nanti ya."],
                "purpose": ["Saya lagi sibuk.", "Nanti ya."],
                "ask_time": ["Saya lagi luar.", "Nanti saya hubungi balik."],
                "commit": ["Iya deh.", "Oke."],
                "confirm": ["Ya."],
                "close": ["Iya."]
            },
            "negotiating": {
                "greeting": ["Halo.", "Ada apa?"],
                "identity": ["Ya."],
                "purpose": ["Oh, bisa nggak diperpanjang?"],
                "ask_time": ["Minggu ini bisa?", "Besok bisa?"],
                "commit": ["Oke, besok jam 3."],
                "confirm": ["Iya."],
                "close": ["Terima kasih."]
            },
            "resistant": {
                "greeting": ["Halo?", "Apaan sih?"],
                "identity": ["Ya, apa?"],
                "purpose": ["Aduh, saya lagi susah.", "Nanti dulu ya."],
                "ask_time": ["Saya belum punya duit.", "Gak bisa."],
                "commit": [],
                "confirm": [],
                "close": []
            },
            "silent": {
                "greeting": ["...", "", "Iya?"],
                "identity": ["...", "Ya."],
                "purpose": ["...", "Oh."],
                "ask_time": ["...", "Jam 5."],
                "commit": ["Iya."],
                "confirm": ["Iya."],
                "close": ["..."]
            }
        }

    def respond(self, stage: str, agent_said: str) -> str:
        if self.persona not in self.customer_responses:
            self.persona = "cooperative"

        responses = self.customer_responses[self.persona].get(stage, [])
        if not responses:
            responses = self.customer_responses["cooperative"].get(stage, ["Iya."])

        return random.choice(responses)


def run_conversation_test(
    chat_group: str = "H2",
    customer_persona: str = "cooperative",
    max_turns: int = 12,
    verbose: bool = True
) -> Dict:
    """运行对话测试"""
    bot = CollectionChatBot(chat_group)
    customer = CustomerSimulator(customer_persona)
    conversation_log = []

    if verbose:
        print(f"\n{'='*70}")
        print(f"测试场景: {chat_group}环节, 客户类型: {customer_persona}")
        print(f"{'='*70}")

    stage_map = {
        ChatState.INIT: "greeting",
        ChatState.GREETING: "greeting",
        ChatState.IDENTIFY: "identity",
        ChatState.PURPOSE: "purpose",
        ChatState.ASK_TIME: "ask_time",
        ChatState.COMMIT_TIME: "commit",
        ChatState.CONFIRM: "confirm",
        ChatState.CLOSE: "close",
    }

    # 开始对话
    agent_says = bot.process()
    conversation_log.append({"role": "AGENT", "text": agent_says})
    if verbose:
        print(f"AGENT: {agent_says}")

    success = False

    for turn in range(max_turns):
        current_stage = stage_map.get(bot.state, "greeting")
        customer_says = customer.respond(current_stage, agent_says)
        conversation_log.append({"role": "CUSTOMER", "text": customer_says})
        if verbose:
            print(f"CUSTOMER: {customer_says}")

        if bot.state == ChatState.CLOSE or bot.state == ChatState.FAILED:
            if bot.commit_time:
                success = True
            break

        agent_says = bot.process(customer_says)
        if not agent_says:
            if bot.commit_time:
                success = True
            break

        conversation_log.append({"role": "AGENT", "text": agent_says})
        if verbose:
            print(f"AGENT: {agent_says}")

    if verbose:
        print(f"\n{'='*70}")
        print(f"对话结束: {'✅ 成功' if success else '❌ 失败'}")
        if bot.commit_time:
            print(f"约定时间: {bot.commit_time}")
        print(f"{'='*70}")

    return {
        "chat_group": chat_group,
        "customer_persona": customer_persona,
        "success": success,
        "commit_time": bot.commit_time,
        "conversation": conversation_log
    }


def main():
    print("智能催收对话机器人 - 测试套件")
    print("基于246条对话分析")

    # 定义10个测试场景
    test_scenarios = [
        ("H2", "cooperative", "H2早期 + 合作客户"),
        ("H2", "busy", "H2早期 + 忙碌客户"),
        ("H2", "negotiating", "H2早期 + 协商客户"),
        ("H2", "silent", "H2早期 + 沉默客户"),
        ("H1", "cooperative", "H1中期 + 合作客户"),
        ("H1", "negotiating", "H1中期 + 协商客户"),
        ("H1", "busy", "H1中期 + 忙碌客户"),
        ("S0", "cooperative", "S0晚期 + 合作客户"),
        ("S0", "negotiating", "S0晚期 + 协商客户"),
        ("S0", "resistant", "S0晚期 + 抗拒客户"),
    ]

    print(f"\n{'='*80}")
    print(f"开始测试 {len(test_scenarios)} 个场景")
    print(f"{'='*80}")

    results = []
    for i, (chat_group, persona, desc) in enumerate(test_scenarios, 1):
        print(f"\n\n--- 场景 {i}: {desc} ---")
        result = run_conversation_test(chat_group, persona, verbose=True)
        results.append(result)

    # 输出汇总结果
    print(f"\n\n{'='*80}")
    print(f"测试结果汇总")
    print(f"{'='*80}")

    for i, result in enumerate(results, 1):
        status = "✅ 成功" if result["success"] else "❌ 失败"
        time_info = f" (约定: {result['commit_time']})" if result["commit_time"] else ""
        print(f"{i}. {result['chat_group']} + {result['customer_persona']}: {status}{time_info}")

    success_count = sum(1 for r in results if r["success"])
    print(f"\n总体成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")


if __name__ == "__main__":
    main()
