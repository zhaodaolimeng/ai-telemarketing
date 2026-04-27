#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版客户模拟器 - 基于真实对话数据
增加更多拒绝借口和抗拒程度分级
"""
import random
from typing import List, Dict, Optional


class RealCustomerSimulatorV2:
    """增强版印尼语催收客户模拟器"""

    def __init__(self):
        self.customer_patterns = self._load_real_patterns()
        self.resistance_levels = {
            "very_low": 0.1,  # 几乎不抗拒
            "low": 0.3,      # 轻微抗拒
            "medium": 0.5,   # 中等抗拒
            "high": 0.7,     # 高度抗拒
            "very_high": 0.9 # 极其抗拒
        }

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

            # ========================================================
            # 增强版：各种拒绝借口 - 从真实对话中总结
            # ========================================================

            # 经济困难类
            "excuse_financial": [
                "Saya belum punya duit", "Saya sedang susah",
                "Lagi tidak ada uang", "Uangnya belum turun",
                "Gaji belum keluar", "Saya baru kehilangan pekerjaan",
                "Usaha sedang lesu", "Lagi krisis ekonomi",
                "Belum dapat gaji bulan ini", "Baru keluar uang untuk kebutuhan pokok"
            ],

            # 时间/忙碌类
            "excuse_busy": [
                "Saya lagi sibuk", "Saya lagi di luar",
                "Nanti saya hubungi balik", "Saya sedang meeting",
                "Saya sedang mengemudi", "Nanti saya telepon kembali",
                "Saya sedang ada urusan penting", "Saya tidak bisa bicara sekarang"
            ],

            # 家庭/个人问题类
            "excuse_personal": [
                "Saya sedang sakit", "Orang tua sedang dirawat",
                "Anak sedang sakit", "Saya baru mengalami musibah",
                "Keluarga sedang ada masalah", "Saya sedang pusing",
                "Saya baru bercerai", "Saya sedang stres"
            ],

            # 忘记/拖延类
            "excuse_delay": [
                "Saya lupa", "Nanti ya",
                "Saya ingat-ingat dulu", "Nanti saya konfirmasi lagi",
                "Saya perlu cek dulu", "Saya belum ingat kapan",
                "Nanti saya kabari", "Saya perlu bicara dengan istri/suami dulu"
            ],

            # 质疑/争议类
            "excuse_dispute": [
                "Saya kira sudah lunas", "Saya tidak ingat ada pinjaman",
                "Kok tagihannya sebesar ini?", "Saya sudah bayar sebagian",
                "Aplikasi Extra tidak saya gunakan", "Saya tidak jadi pinjam",
                "Saya merasa ditipu", "Saya tidak setuju dengan biaya ini"
            ],

            # 直接拒绝类
            "excuse_reject": [
                "Saya tidak mau bayar", "Tidak bisa",
                "Jangan dipaksa", "Saya tidak bisa",
                "Saya tidak mau bicara tentang ini", "Sudah-sudah saja",
                "Saya tutup telepon ya", "Jangan panggil saya lagi"
            ],

            # 借口链条 - 从轻度抗拒到重度抗拒
            "excuse_chain_level_1": [
                "Nanti ya", "Sebentar lagi", "Saya tunggu dulu",
                "Besok ya", "Hari ini tidak bisa"
            ],

            "excuse_chain_level_2": [
                "Saya sedang susah", "Saya belum punya duit",
                "Nanti saya hubungi balik", "Saya lagi di luar"
            ],

            "excuse_chain_level_3": [
                "Saya tidak mau bayar", "Tidak bisa",
                "Jangan dipaksa", "Saya tidak ingat ada pinjaman"
            ],

            "excuse_chain_level_4": [
                "Saya tutup telepon ya", "Jangan panggil saya lagi",
                "Saya akan laporan ke polisi", "Saya tidak mau bicara tentang ini"
            ],

            # 最后可能松口
            "excuse_final_relent": [
                "Oke deh, saya usahakan besok",
                "Ya sudah, saya transfer nanti",
                "Oke, saya bayar minggu ini"
            ]
        }

    def generate_response(
        self,
        stage: str,
        chat_group: str = "H2",
        persona: str = "cooperative",
        resistance_level: str = "medium",
        last_agent_text: str = "",
        conversation_history: List = None,
        push_count: int = 0
    ) -> str:
        """
        生成客户回应

        Args:
            stage: 当前对话阶段
            chat_group: H2/H1/S0
            persona: 客户类型
            resistance_level: 抗拒程度 (very_low, low, medium, high, very_high)
            last_agent_text: 坐席最后说的话
            conversation_history: 对话历史
            push_count: 被追问次数
        """
        history = conversation_history or []

        if persona == "cooperative":
            return self._cooperative_response(stage)
        elif persona == "busy":
            return self._busy_response(stage)
        elif persona == "negotiating":
            return self._negotiating_response(stage)
        elif persona == "silent":
            return self._silent_response(stage)
        elif persona == "forgetful":
            return self._forgetful_response(stage)
        elif persona == "resistant":
            return self._resistant_response_with_level(
                stage, resistance_level, push_count
            )
        elif persona == "excuse_master":
            return self._excuse_master_response(
                stage, chat_group, push_count
            )
        else:
            return random.choice(self.customer_patterns["greeting"])

    def _cooperative_response(self, stage: str) -> str:
        """合作型客户回应"""
        if stage == "greeting":
            return random.choice(["Halo", "Sore", "Pagi", "Iya?", "Ya"])
        elif stage == "identity":
            return random.choice(["Ya", "Iya", "Ya betul", "Benar"])
        elif stage == "purpose":
            return random.choice(["Oh ingatnya", "Ya, saya ingat", "Oh ya", "Ya saya tahu"])
        elif stage == "ask_time":
            return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            return random.choice(["Oke, jam 5 deh", "Besok jam 3", "Hari ini jam 4"])
        elif stage == "confirm":
            return random.choice(self.customer_patterns["confirm"])
        elif stage == "close":
            return random.choice(self.customer_patterns["close"])
        return "Iya"

    def _busy_response(self, stage: str) -> str:
        """忙碌型客户回应"""
        if stage == "greeting":
            return random.choice(["Sibuk", "Ada apa?", "Sebentar ya", "Maaf"])
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
            if random.random() < 0.6:
                return random.choice(["Saya lagi luar", "Nanti ya", "Saya lagi sibuk"])
            else:
                return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            if random.random() < 0.7:
                return random.choice(["Oke, jam 5 deh", "Besok jam 3", "Hari ini nanti"])
            else:
                return random.choice(self.customer_patterns["vague_time"])
        return "Ya"

    def _negotiating_response(self, stage: str) -> str:
        """协商型客户回应"""
        if stage == "greeting":
            return random.choice(["Halo", "Ada apa?"])
        elif stage == "identity":
            return "Ya"
        elif stage == "purpose":
            return random.choice([
                "Oh ya, bisa nggak diperpanjang?",
                "Ya, tapi saya sedang kesulitan",
                "Bisa diundur nggak?"
            ])
        elif stage == "ask_time":
            if random.random() < 0.5:
                return random.choice(self.customer_patterns["time_options"])
            else:
                return random.choice([
                    "Minggu ini bisa?", "Besok bisa?",
                    "Saya tunggu dana dulu"
                ])
        elif stage == "push":
            return random.choice([
                "Oke, besok jam 3", "Ya, hari ini jam 5",
                "Besok ya"
            ])
        return "Iya"

    def _silent_response(self, stage: str) -> str:
        """沉默型客户回应"""
        if random.random() < 0.4:
            return ""
        elif random.random() < 0.7:
            return "..."
        else:
            if stage == "greeting":
                return random.choice(["Halo?", "Iya?"])
            elif stage == "ask_time":
                return random.choice(["...", "Jam 5"])
            else:
                return random.choice(["Iya", "Ya", "..."])

    def _forgetful_response(self, stage: str) -> str:
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
            return random.choice([
                "Nanti ya", "Sebentar lagi",
                "Saya lupa, nanti saya ingat dulu"
            ])
        elif stage == "push":
            return random.choice([
                "Oh ya! Jam 4 deh", "Besok jam 3",
                "Oke, hari ini jam 5"
            ])
        return "Iya"

    def _resistant_response_with_level(
        self, stage: str, resistance_level: str, push_count: int
    ) -> str:
        """带抗拒程度的抗拒型客户回应"""
        level_prob = self.resistance_levels.get(resistance_level, 0.5)

        if stage == "greeting":
            if random.random() < level_prob:
                return random.choice(["Halo?", "Apaan sih?", "Ada apa?"])
            else:
                return random.choice(["Halo", "Pagi", "Sore"])

        elif stage == "identity":
            if random.random() < level_prob:
                return random.choice(["Ya, apa?", "Ini kenapa?", "Ada apa sih?"])
            else:
                return random.choice(["Ya", "Iya", "Ya betul"])

        elif stage == "purpose":
            if random.random() < level_prob:
                return random.choice([
                    "Aduh, saya lagi susah", "Nanti dulu ya",
                    "Saya sedang kesulitan"
                ])
            else:
                return random.choice(["Oh ingatnya", "Ya, saya ingat"])

        elif stage == "ask_time":
            if random.random() < level_prob:
                return random.choice([
                    "Saya belum punya duit", "Gak bisa",
                    "Saya sedang susah", "Nanti dulu"
                ])
            else:
                return random.choice(self.customer_patterns["time_direct"])

        elif stage == "push":
            # 被追问次数越多，越可能松口或越抗拒
            if push_count >= 3 and random.random() < 0.3:
                return random.choice(self.customer_patterns["excuse_final_relent"])

            if random.random() < level_prob:
                if push_count == 0:
                    return random.choice(self.customer_patterns["excuse_chain_level_1"])
                elif push_count == 1:
                    return random.choice(self.customer_patterns["excuse_chain_level_2"])
                elif push_count == 2:
                    return random.choice(self.customer_patterns["excuse_chain_level_3"])
                else:
                    return random.choice(self.customer_patterns["excuse_chain_level_4"])
            else:
                if random.random() < 0.2:
                    return random.choice(self.customer_patterns["excuse_final_relent"])
                else:
                    return random.choice([
                        "Oke, jam 5 deh", "Besok jam 3",
                        "Hari ini jam 4"
                    ])

        return "..."

    def _excuse_master_response(self, stage: str, chat_group: str, push_count: int) -> str:
        """借口大师型客户 - 不断变换借口"""
        if stage == "greeting":
            return random.choice(["Halo?", "Ada apa?", "Ya?"])

        elif stage == "identity":
            return random.choice(["Ya, dengan saya", "Ada apa?", "Ya"])

        elif stage == "purpose":
            # 根据不同催收阶段有不同反应
            if chat_group == "H2":
                return random.choice([
                    "Oh ya, saya ingat", "Nanti dulu ya",
                    random.choice(self.customer_patterns["excuse_busy"])
                ])
            elif chat_group == "H1":
                return random.choice([
                    random.choice(self.customer_patterns["excuse_personal"]),
                    random.choice(self.customer_patterns["excuse_delay"])
                ])
            else:  # S0
                return random.choice([
                    random.choice(self.customer_patterns["excuse_dispute"]),
                    random.choice(self.customer_patterns["excuse_financial"])
                ])

        elif stage == "ask_time":
            if push_count == 0:
                return random.choice(self.customer_patterns["excuse_chain_level_1"])
            else:
                # 根据push_count选择不同程度的借口
                excuse_mix = []
                if push_count == 1:
                    excuse_mix = self.customer_patterns["excuse_busy"] + \
                                 self.customer_patterns["excuse_delay"]
                elif push_count == 2:
                    excuse_mix = self.customer_patterns["excuse_financial"] + \
                                 self.customer_patterns["excuse_personal"]
                else:
                    excuse_mix = self.customer_patterns["excuse_dispute"] + \
                                 self.customer_patterns["excuse_reject"]

                return random.choice(excuse_mix)

        elif stage == "push":
            if push_count >= 4 and random.random() < 0.15:
                return random.choice(self.customer_patterns["excuse_final_relent"])
            elif push_count >= 3:
                return random.choice(self.customer_patterns["excuse_chain_level_4"])
            elif push_count == 2:
                return random.choice(self.customer_patterns["excuse_chain_level_3"])
            elif push_count == 1:
                return random.choice(self.customer_patterns["excuse_chain_level_2"])
            else:
                return random.choice(self.customer_patterns["excuse_chain_level_1"])

        return "..."


# 增强版测试用例
GOLDEN_TEST_CASES_V2 = [
    # (chat_group, persona, description, expected_success, resistance_level)
    ("H2", "cooperative", "H2早期-合作客户-直接给时间", True, "very_low"),
    ("H2", "busy", "H2早期-忙碌客户-先推脱后给时间", True, "low"),
    ("H2", "negotiating", "H2早期-协商客户-问选项后确定", True, "low"),
    ("H2", "silent", "H2早期-沉默客户-偶尔说话", False, "high"),
    ("H2", "forgetful", "H2早期-健忘客户-先忘后想起来", True, "low"),
    ("H2", "resistant", "H2早期-抗拒客户-推托", False, "medium"),
    ("H2", "excuse_master", "H2早期-借口大师-多变借口", False, "high"),

    ("H1", "cooperative", "H1中期-合作客户", True, "very_low"),
    ("H1", "busy", "H1中期-忙碌客户", True, "low"),
    ("H1", "negotiating", "H1中期-协商客户", True, "medium"),
    ("H1", "resistant", "H1中期-抗拒客户-中等抗拒", False, "medium"),
    ("H1", "excuse_master", "H1中期-借口大师-高度抗拒", False, "high"),

    ("S0", "cooperative", "S0晚期-合作客户", True, "very_low"),
    ("S0", "negotiating", "S0晚期-协商客户", True, "medium"),
    ("S0", "resistant", "S0晚期-抗拒客户-高抗拒", False, "high"),
    ("S0", "excuse_master", "S0晚期-借口大师-极高抗拒", False, "very_high"),
    ("S0", "silent", "S0晚期-沉默客户", False, "very_high"),

    # 额外测试：不同抗拒程度
    ("H2", "resistant", "H2早期-抗拒客户-低抗拒", True, "low"),
    ("H1", "resistant", "H1中期-抗拒客户-高抗拒", False, "high"),
    ("S0", "resistant", "S0晚期-抗拒客户-极高抗拒", False, "very_high"),
]


if __name__ == "__main__":
    print("=" * 70)
    print("测试增强版真实客户模拟器")
    print("=" * 70)

    simulator = RealCustomerSimulatorV2()

    test_stages = ["greeting", "identity", "purpose", "ask_time", "push", "confirm", "close"]
    personas = ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful", "excuse_master"]
    resistance_levels = ["very_low", "low", "medium", "high", "very_high"]

    print("\n1. 测试不同persona在各阶段的回应:")
    print("-" * 70)

    for persona in personas:
        print(f"\nPersona: {persona}")
        for stage in test_stages[:4]:
            resp = simulator.generate_response(stage, persona=persona)
            print(f"  {stage:12} -> {resp}")

    print("\n" + "=" * 70)
    print("\n2. 测试不同抗拒程度的抗拒型客户:")
    print("-" * 70)

    for level in resistance_levels:
        print(f"\nResistance Level: {level}")
        for push_count in range(3):
            resp = simulator.generate_response(
                "push", persona="resistant",
                resistance_level=level, push_count=push_count
            )
            print(f"  Push {push_count}: {resp}")

    print("\n" + "=" * 70)
    print("\n3. 测试借口大师的借口变化:")
    print("-" * 70)

    print("Excuse Master (S0晚期):")
    for push_count in range(5):
        resp = simulator.generate_response(
            "push" if push_count > 0 else "ask_time",
            chat_group="S0", persona="excuse_master",
            push_count=push_count
        )
        print(f"  Push {push_count}: {resp}")

    print("\n" + "=" * 70)
    print("增强版模拟器加载完成！")
    print("=" * 70)
