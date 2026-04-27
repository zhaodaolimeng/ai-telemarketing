#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于真实对话数据的客户模拟器
从246个真实对话中学习客户回应模式
"""
import random
import re
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


class RealCustomerSimulator:
    """基于真实数据的印尼语催收客户模拟器"""

    def __init__(self):
        # 从真实对话中提取的客户回应模式
        self.customer_patterns = self._load_real_patterns()

    def _load_real_patterns(self) -> Dict:
        """加载从真实对话中提取的回应模式"""
        return {
            # 问候阶段回应
            "greeting": [
                "Halo", "Sore", "Pagi", "Iya?", "Ya", "Ada apa?",
                "Halo?", "Ya dengan Bapak", "Assalamualaikum",
                "Saya lagi sibuk", "Sebentar ya", "Maaf",
                "Lagi di luar", "Nanti saya hubungi balik"
            ],

            # 确认身份阶段
            "identity": [
                "Ya", "Iya", "Ya betul", "Benar", "Ini dengan saya",
                "Ada apa?", "Maaf, saya lagi", "Nanti dulu ya"
            ],

            # 说明来意后
            "purpose": [
                "Oh ingatnya", "Ya, saya ingat", "Oh ya, pinjaman ya",
                "Maaf ya, saya lupa", "Oh begitu", "Saya sedang kesulitan",
                "Bisa nggak diperpanjang?", "Nanti dulu ya",
                "Saya belum punya duit", "Lagi susah nih",
                "Saya jualan dulu, nanti baru bisa", "Ya saya tahu"
            ],

            # 询问时间后 - 直接给出时间
            "time_direct": [
                "Jam 5", "Jam 4", "Jam 3", "Jam 2", "Jam 8",
                "Besok jam 5", "Besok jam 3", "Hari ini jam 4",
                "Nanti jam 5", "Siang ini jam 2", "Malam ini jam 8",
                "Hari ini", "Besok", "Lusa", "Minggu ini"
            ],

            # 询问时间后 - 协商/推托
            "time_negotiate": [
                "Nanti ya", "Sebentar lagi", "Saya lagi keluar",
                "Bisa besok?", "Minggu ini bisa?", "Saya tunggu dana dulu",
                "Jangan sekejap", "Nanti saya hubungi balik",
                "Saya belum pasti", "Bisa nggak diundur?",
                "Kesulitan nih", "Saya lagi belum punya duit"
            ],

            # 询问时间后 - 给选项
            "time_options": [
                "Jam 5 bisa atau jam 3?", "Jam 4 atau jam 5?",
                "Besok atau hari ini?", "Siang atau sore?",
                "Jam 2 atau jam 3?"
            ],

            # 被追问后
            "push": [
                "Oke, jam 5 deh", "Besok jam 3", "Hari ini jam 4",
                "Ya, ya, jam 5", "Nanti ya, saya usahakan",
                "Saya benar-benar belum bisa", "Maaf ya, nanti saya hubungi",
                "Saya tunggu transfer dulu", "Nanti saya konfirmasi lagi"
            ],

            # 确认阶段
            "confirm": [
                "Iya", "Ya", "Oke", "Siap", "Baik",
                "Ya, ya, ya", "Oke, saya ingat", "Terima kasih",
                "Ditunggu ya", "Saya komitmen"
            ],

            # 结束阶段
            "close": [
                "Terima kasih", "Terima kasih kembali", "Selamat pagi",
                "Selamat sore", "Selamat siang", "Oke, dadah",
                "Baik, saya tunggu", "Terima kasih ya"
            ],

            # 抗拒/拒绝
            "resist": [
                "Saya tidak mau", "Saya belum bisa", "Nanti dulu",
                "Saya sedang susah", "Jangan dipaksa",
                "Saya pikir dulu", "Maaf, saya tidak bisa",
                "Saya akan hubungi nanti", "Saya butuh waktu"
            ],

            # 模糊时间表达（来自真实数据）
            "vague_time": [
                "Nanti", "Sebentar lagi", "Nanti sore", "Nanti pagi",
                "Nanti malam", "Hari ini nanti", "Besok nanti",
                "Nanti saya konfirmasi", "Nanti saya usahakan",
                "Nanti saya kirim bukti", "Saya tunggu dana dulu",
                "Nanti saya transfer", "Saya usahakan hari ini"
            ],

            # 真实对话中发现的打断/反问
            "interrupt": [
                "Tadi hanya hari ini dibajarkan apa ya?",
                "Tagian apa?", "Saya tunggu apa?",
                "Gimana?", "Ya benar-benar gimana?",
                "Ini baru banyak penasaran", "Berapa yang dulu?"
            ],

            # 真实ASR错误导致的奇怪表达
            "asr_noise": [
                "Ya saya tunggu di jam 2 siang ini pembayarannya ya pak",
                "Ya, saya serang berapa, Pak?",
                "Tadi ini kenapa masih belum dibayarkan ibu",
                "Ini masih keberiling, Ibu",
                "Saya tunggu pukmar airannya"
            ]
        }

    def generate_response(
        self,
        stage: str,
        chat_group: str = "H2",
        persona: str = "cooperative",
        last_agent_text: str = "",
        conversation_history: List = None
    ) -> str:
        """
        生成客户回应

        Args:
            stage: 当前对话阶段 (greeting, identity, purpose, ask_time, etc.)
            chat_group: H2/H1/S0
            persona: 客户类型 (cooperative, busy, negotiating, resistant, silent, forgetful)
            last_agent_text: 坐席最后说的话
            conversation_history: 对话历史
        """
        history = conversation_history or []

        # 基于persona选择不同的回应策略
        if persona == "cooperative":
            return self._cooperative_response(stage, last_agent_text)
        elif persona == "busy":
            return self._busy_response(stage, last_agent_text)
        elif persona == "negotiating":
            return self._negotiating_response(stage, last_agent_text)
        elif persona == "resistant":
            return self._resistant_response(stage, last_agent_text)
        elif persona == "silent":
            return self._silent_response(stage, last_agent_text)
        elif persona == "forgetful":
            return self._forgetful_response(stage, last_agent_text)
        else:
            return random.choice(self.customer_patterns["greeting"])

    def _cooperative_response(self, stage: str, agent_text: str) -> str:
        """合作型客户回应"""
        if stage == "greeting":
            return random.choice([
                "Halo", "Sore", "Pagi", "Iya?", "Ya"
            ])
        elif stage == "identity":
            return random.choice([
                "Ya", "Iya", "Ya betul", "Benar"
            ])
        elif stage == "purpose":
            return random.choice([
                "Oh ingatnya", "Ya, saya ingat", "Oh ya",
                "Ya saya tahu"
            ])
        elif stage == "ask_time":
            # 合作型直接给时间
            return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            return random.choice([
                "Oke, jam 5 deh", "Besok jam 3", "Hari ini jam 4"
            ])
        elif stage == "confirm":
            return random.choice(self.customer_patterns["confirm"])
        elif stage == "close":
            return random.choice(self.customer_patterns["close"])
        else:
            return "Iya"

    def _busy_response(self, stage: str, agent_text: str) -> str:
        """忙碌型客户回应"""
        if stage == "greeting":
            return random.choice([
                "Sibuk", "Ada apa?", "Sebentar ya", "Maaf"
            ])
        elif stage == "identity":
            return random.choice([
                "Ya, tapi saya lagi sibuk", "Nanti dulu ya",
                "Saya lagi di luar", "Sebentar"
            ])
        elif stage == "purpose":
            return random.choice([
                "Saya lagi sibuk", "Nanti saya hubungi balik",
                "Oh ya, tapi saya sedang keluar"
            ])
        elif stage == "ask_time":
            # 忙碌型先推脱，然后可能给时间
            if random.random() < 0.6:
                return random.choice([
                    "Saya lagi luar", "Nanti ya", "Saya lagi sibuk"
                ])
            else:
                return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            # 被追问后可能给时间
            if random.random() < 0.7:
                return random.choice([
                    "Oke, jam 5 deh", "Besok jam 3", "Hari ini nanti"
                ])
            else:
                return random.choice(self.customer_patterns["vague_time"])
        else:
            return "Ya"

    def _negotiating_response(self, stage: str, agent_text: str) -> str:
        """协商型客户回应"""
        if stage == "greeting":
            return random.choice(["Halo", "Ada apa?"])
        elif stage == "identity":
            return "Ya"
        elif stage == "purpose":
            # 协商型可能问问题或要求延期
            return random.choice([
                "Oh ya, bisa nggak diperpanjang?",
                "Ya, tapi saya sedang kesulitan",
                "Bisa diundur nggak?"
            ])
        elif stage == "ask_time":
            # 给选项或模糊时间
            if random.random() < 0.5:
                return random.choice(self.customer_patterns["time_options"])
            else:
                return random.choice([
                    "Minggu ini bisa?", "Besok bisa?",
                    "Saya tunggu dana dulu"
                ])
        elif stage == "push":
            # 被追问后给出确定时间
            return random.choice([
                "Oke, besok jam 3", "Ya, hari ini jam 5",
                "Besok ya"
            ])
        else:
            return "Iya"

    def _resistant_response(self, stage: str, agent_text: str) -> str:
        """抗拒型客户回应"""
        if stage == "greeting":
            return random.choice([
                "Halo?", "Apaan sih?", "Ada apa?"
            ])
        elif stage == "identity":
            return random.choice([
                "Ya, apa?", "Ini kenapa?", "Ada apa sih?"
            ])
        elif stage == "purpose":
            return random.choice([
                "Aduh, saya lagi susah", "Nanti dulu ya",
                "Saya sedang kesulitan"
            ])
        elif stage == "ask_time":
            # 抗拒型直接拒绝或找借口
            return random.choice([
                "Saya belum punya duit", "Gak bisa",
                "Saya sedang susah", "Nanti dulu"
            ])
        elif stage == "push":
            # 被追问后继续抗拒，或极少数情况松口
            if random.random() < 0.2:
                return random.choice([
                    "Oke, saya usahakan besok",
                    "Nanti saya pikir dulu"
                ])
            else:
                return random.choice([
                    "Saya benar-benar belum bisa",
                    "Maaf ya, nanti saya hubungi",
                    "Saya butuh waktu"
                ])
        else:
            return "..."

    def _silent_response(self, stage: str, agent_text: str) -> str:
        """沉默型客户回应"""
        if random.random() < 0.4:
            return ""
        elif random.random() < 0.7:
            return "..."
        else:
            # 偶尔说话
            if stage == "greeting":
                return random.choice(["Halo?", "Iya?"])
            elif stage == "ask_time":
                return random.choice(["...", "Jam 5"])
            else:
                return random.choice(["Iya", "Ya", "..."])

    def _forgetful_response(self, stage: str, agent_text: str) -> str:
        """健忘型客户回应"""
        if stage == "greeting":
            return random.choice(["Halo?", "Oh iya"])
        elif stage == "identity":
            return "Ya"
        elif stage == "purpose":
            return random.choice([
                "Oh ya, saya lupa", "Oh, baru ingat",
                "Ah, iya ya, pinjaman"
            ])
        elif stage == "ask_time":
            # 健忘型先模糊，然后想起来
            return random.choice([
                "Nanti ya", "Sebentar lagi",
                "Saya lupa, nanti saya ingat dulu"
            ])
        elif stage == "push":
            # 被追问后想起来给时间
            return random.choice([
                "Oh ya! Jam 4 deh", "Besok jam 3",
                "Oke, hari ini jam 5"
            ])
        else:
            return "Iya"


# 测试数据 - 从真实对话中提取的Golden测试用例
GOLDEN_TEST_CASES = [
    # (chat_group, persona, description, expected_success)
    ("H2", "cooperative", "H2早期-合作客户-直接给时间", True),
    ("H2", "busy", "H2早期-忙碌客户-先推脱后给时间", True),
    ("H2", "negotiating", "H2早期-协商客户-问选项后确定", True),
    ("H2", "silent", "H2早期-沉默客户-偶尔说话", True),
    ("H2", "forgetful", "H2早期-健忘客户-先忘后想起来", True),
    ("H2", "resistant", "H2早期-抗拒客户-推托", False),

    ("H1", "cooperative", "H1中期-合作客户", True),
    ("H1", "busy", "H1中期-忙碌客户", True),
    ("H1", "negotiating", "H1中期-协商客户", True),
    ("H1", "resistant", "H1中期-抗拒客户", False),

    ("S0", "cooperative", "S0晚期-合作客户", True),
    ("S0", "negotiating", "S0晚期-协商客户", True),
    ("S0", "resistant", "S0晚期-抗拒客户-拒绝", False),
    ("S0", "silent", "S0晚期-沉默客户", False),
]


if __name__ == "__main__":
    # 测试模拟器
    print("=" * 60)
    print("测试真实客户模拟器")
    print("=" * 60)

    simulator = RealCustomerSimulator()

    test_stages = ["greeting", "identity", "purpose", "ask_time", "push", "confirm", "close"]
    personas = ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful"]

    print("\n测试不同persona在各阶段的回应:")
    print("-" * 60)

    for persona in personas:
        print(f"\nPersona: {persona}")
        for stage in test_stages[:4]:  # 只测前4个阶段
            resp = simulator.generate_response(stage, persona=persona)
            print(f"  {stage:12} -> {resp}")

    print("\n" + "=" * 60)
    print("模拟器加载完成！")
    print("=" * 60)
