#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版客户模拟器 - 复合类型与边界场景
"""
import random
from typing import List, Dict, Optional


class EnhancedCustomerSimulator:
    """增强版客户模拟器 - 支持复合类型与渐进抗拒"""

    def __init__(self):
        self.customer_patterns = self._load_patterns()
        self.resistance_levels = {
            "very_low": 0.1,
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "very_high": 0.9
        }

    def _load_patterns(self) -> Dict:
        """加载回应模式"""
        return {
            # 问候
            "greeting": ["Halo", "Sore", "Pagi", "Iya?", "Ya", "Ada apa?", "Halo?"],

            # 身份确认
            "identity": ["Ya", "Iya", "Ya betul", "Benar", "Ini dengan saya", "Ada apa?"],

            # 目的说明回应
            "purpose": [
                "Oh ingatnya", "Ya, saya ingat", "Oh ya, pinjaman ya",
                "Maaf ya, saya lupa", "Oh begitu", "Saya sedang kesulitan",
                "Bisa nggak diperpanjang?", "Nanti dulu ya",
                "Saya belum punya duit", "Lagi susah nih", "Ya saya tahu"
            ],

            # 直接给时间
            "time_direct": [
                "Jam 5", "Jam 4", "Jam 3", "Besok jam 5",
                "Hari ini jam 4", "Minggu ini", "Besok"
            ],

            # 协商时间
            "time_negotiate": [
                "Nanti ya", "Sebentar lagi", "Saya lagi luar",
                "Bisa besok?", "Minggu ini bisa?", "Saya tunggu dana dulu",
                "Saya belum pasti", "Bisa diundur nggak?"
            ],

            # 确认与结束
            "confirm": ["Iya", "Ya", "Oke", "Siap", "Baik", "Oke, saya ingat"],
            "close": ["Terima kasih", "Baik, saya tunggu", "Selamat pagi"],

            # 借口分类
            "excuse_financial": [
                "Saya belum punya duit", "Saya sedang susah", "Gaji belum keluar",
                "Baru keluar uang untuk kebutuhan pokok"
            ],
            "excuse_busy": [
                "Saya lagi sibuk", "Saya lagi di luar", "Nanti saya hubungi balik",
                "Saya sedang meeting"
            ],
            "excuse_personal": [
                "Saya sedang sakit", "Orang tua sedang dirawat", "Anak sedang sakit"
            ],
            "excuse_delay": [
                "Saya lupa", "Nanti ya", "Saya perlu cek dulu",
                "Saya perlu bicara dengan istri/suami dulu"
            ],
            "excuse_dispute": [
                "Saya kira sudah lunas", "Saya tidak ingat ada pinjaman",
                "Kok tagihannya sebesar ini?", "Saya tidak setuju dengan biaya ini"
            ],
            "excuse_reject": [
                "Saya tidak mau bayar", "Tidak bisa", "Jangan dipaksa",
                "Saya tutup telepon ya", "Jangan panggil saya lagi"
            ],

            # 转移话题
            "divert": [
                "Ngomongin dulu yang lain ya", "Cuaca hari ini bagus ya?",
                "Kamu dari mana?", "Sudah makan belum?"
            ],

            # 反问攻击
            "counter_question": [
                "Kenapa sih kamu tanya terus?", "Kamu siapa?",
                "Ini penting banget?", "Nanti bisa nggak?",
                "Kamu punya bukti?", "Perusahaan kamu di mana?"
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
        """生成客户回应"""
        history = conversation_history or []

        # 复合类型处理
        if "+" in persona:
            return self._composite_persona_response(
                persona, stage, chat_group, resistance_level, push_count
            )

        # 边界类型处理
        if persona.startswith("edge_"):
            return self._edge_case_response(
                persona, stage, chat_group, resistance_level, push_count
            )

        # 渐进抗拒
        if persona == "gradual_resistant":
            return self._gradual_resistant_response(
                stage, chat_group, push_count, len(history)
            )

        # 情绪波动
        if persona == "mood_swinger":
            return self._mood_swinger_response(stage, chat_group, push_count)

        # 标准类型
        return self._standard_persona_response(
            persona, stage, chat_group, resistance_level, push_count
        )

    def _composite_persona_response(
        self, composite_persona: str, stage: str, chat_group: str,
        resistance_level: str, push_count: int
    ) -> str:
        """复合类型回应"""
        personas = composite_persona.split("+")

        # 根据对话阶段切换主导特征
        if push_count == 0:
            primary_persona = personas[0]
        else:
            primary_persona = personas[-1]

        # 沉默+抗拒
        if "silent" in composite_persona and "resistant" in composite_persona:
            if push_count < 2:
                if random.random() < 0.6:
                    return "" if random.random() < 0.5 else "..."
            else:
                return self._resistant_response(stage, chat_group, resistance_level, push_count)

        # 健忘+协商
        if "forgetful" in composite_persona and "negotiating" in composite_persona:
            if stage in ["greeting", "identity", "purpose"]:
                return self._forgetful_response(stage)
            else:
                return self._negotiating_response(stage, push_count)

        # 忙碌+借口
        if "busy" in composite_persona and "excuse_master" in composite_persona:
            if stage in ["greeting", "identity"]:
                return random.choice(self.customer_patterns["excuse_busy"])
            else:
                excuse_types = ["excuse_financial", "excuse_personal", "excuse_delay"]
                selected_excuse = random.choice(excuse_types)
                return random.choice(self.customer_patterns[selected_excuse])

        # 默认：混合
        return self._standard_persona_response(
            primary_persona, stage, chat_group, resistance_level, push_count
        )

    def _edge_case_response(
        self, edge_persona: str, stage: str, chat_group: str,
        resistance_level: str, push_count: int
    ) -> str:
        """边界场景回应"""

        # 极端抗拒：拒绝一切
        if edge_persona == "edge_extreme_resistant":
            level_prob = 0.95
            if stage == "greeting":
                if random.random() < level_prob:
                    return random.choice(self.customer_patterns["excuse_reject"])
                return "Ada apa?"
            else:
                if random.random() < level_prob:
                    return random.choice(self.customer_patterns["excuse_reject"])
                return random.choice(self.customer_patterns["excuse_dispute"])

        # 完全沉默：全程不说或极少说话
        if edge_persona == "edge_total_silent":
            silence_prob = 0.8
            if random.random() < silence_prob:
                return ""
            return "..." if random.random() < 0.7 else "Iya"

        # 胡搅蛮缠：逻辑混乱，转移话题
        if edge_persona == "edge_chaotic":
            if random.random() < 0.6:
                return random.choice(self.customer_patterns["divert"])
            elif random.random() < 0.3:
                return random.choice(self.customer_patterns["counter_question"])
            else:
                return random.choice(self.customer_patterns["excuse_reject"])

        # 条件不断变：同意A又变B
        if edge_persona == "edge_shifting_conditions":
            if stage == "ask_time":
                if push_count == 0:
                    return "Jam 5"
                elif push_count == 1:
                    return "Wait, besok deh"
                elif push_count == 2:
                    return "Eh, nggak jadi, minggu ini"
                else:
                    return "Saya belum pasti deh"
            elif stage == "push":
                if push_count <= 1:
                    return random.choice(self.customer_patterns["time_direct"])
                else:
                    return random.choice(self.customer_patterns["time_negotiate"])

        return "..."

    def _gradual_resistant_response(
        self, stage: str, chat_group: str, push_count: int, history_length: int
    ) -> str:
        """渐进抗拒：对话过程中逐步提升抗拒程度"""
        # 随着对话进行，抗拒程度增加
        resistance_factor = min(0.9, 0.2 + 0.15 * push_count)

        if stage == "greeting":
            return random.choice(["Halo", "Sore", "Pagi"])
        elif stage == "identity":
            return random.choice(["Ya", "Iya"])
        elif stage == "purpose":
            if random.random() < resistance_factor:
                return random.choice(self.customer_patterns["excuse_busy"])
            return "Oh ya, saya ingat"
        elif stage == "ask_time":
            if random.random() < resistance_factor:
                return random.choice(self.customer_patterns["excuse_delay"])
            return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            if random.random() < resistance_factor:
                excuse_level = min(push_count, 4)
                if excuse_level <= 1:
                    return random.choice(self.customer_patterns["excuse_delay"])
                elif excuse_level == 2:
                    return random.choice(self.customer_patterns["excuse_financial"])
                elif excuse_level == 3:
                    return random.choice(self.customer_patterns["excuse_dispute"])
                else:
                    return random.choice(self.customer_patterns["excuse_reject"])
            return random.choice(self.customer_patterns["time_direct"])
        return "Iya"

    def _mood_swinger_response(self, stage: str, chat_group: str, push_count: int) -> str:
        """情绪波动：客户态度变化"""
        # 随机决定当前情绪
        moods = ["cooperative", "negotiating", "resistant"]
        current_mood = random.choice(moods)
        return self._standard_persona_response(
            current_mood, stage, chat_group, "medium", push_count
        )

    def _standard_persona_response(
        self, persona: str, stage: str, chat_group: str,
        resistance_level: str, push_count: int
    ) -> str:
        """标准类型回应"""
        if persona == "cooperative":
            return self._cooperative_response(stage)
        elif persona == "busy":
            return self._busy_response(stage)
        elif persona == "negotiating":
            return self._negotiating_response(stage, push_count)
        elif persona == "silent":
            return self._silent_response(stage)
        elif persona == "forgetful":
            return self._forgetful_response(stage)
        elif persona == "resistant":
            return self._resistant_response(stage, chat_group, resistance_level, push_count)
        elif persona == "excuse_master":
            return self._excuse_master_response(stage, chat_group, push_count)
        return "Iya"

    def _cooperative_response(self, stage: str) -> str:
        """合作型回应"""
        if stage == "greeting":
            return random.choice(["Halo", "Sore", "Pagi"])
        elif stage == "identity":
            return random.choice(["Ya", "Iya", "Ya betul"])
        elif stage == "purpose":
            return random.choice(["Oh ingatnya", "Ya, saya ingat"])
        elif stage == "ask_time":
            return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            return random.choice(self.customer_patterns["time_direct"])
        return "Iya"

    def _busy_response(self, stage: str) -> str:
        """忙碌型回应"""
        if stage in ["greeting", "identity"]:
            return random.choice(self.customer_patterns["excuse_busy"])
        elif stage == "purpose":
            return "Nanti saya hubungi balik"
        elif stage in ["ask_time", "push"]:
            if random.random() < 0.5:
                return random.choice(self.customer_patterns["excuse_busy"])
            return random.choice(self.customer_patterns["time_direct"])
        return "Nanti ya"

    def _negotiating_response(self, stage: str, push_count: int) -> str:
        """协商型回应"""
        if stage == "ask_time":
            if push_count == 0 and random.random() < 0.7:
                return random.choice(self.customer_patterns["time_negotiate"])
            return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            return random.choice(self.customer_patterns["time_direct"])
        return "Iya"

    def _silent_response(self, stage: str) -> str:
        """沉默型回应"""
        if random.random() < 0.5:
            return ""
        elif random.random() < 0.7:
            return "..."
        return "Iya"

    def _forgetful_response(self, stage: str) -> str:
        """健忘型回应"""
        if stage == "purpose":
            return "Oh, baru ingat"
        elif stage in ["ask_time", "push"]:
            if random.random() < 0.4:
                return "Saya lupa, sebentar ya"
            return random.choice(self.customer_patterns["time_direct"])
        return "Iya"

    def _resistant_response(
        self, stage: str, chat_group: str, resistance_level: str, push_count: int
    ) -> str:
        """抗拒型回应"""
        level_prob = self.resistance_levels.get(resistance_level, 0.5)

        if stage in ["greeting", "identity"]:
            if random.random() < level_prob:
                return random.choice(["Ada apa?", "Ya, apa?"])
            return "Halo"
        elif stage == "purpose":
            if random.random() < level_prob:
                return random.choice(self.customer_patterns["excuse_financial"])
            return "Oh ya"
        elif stage == "ask_time":
            if random.random() < level_prob:
                return random.choice(self.customer_patterns["excuse_delay"])
            return random.choice(self.customer_patterns["time_direct"])
        elif stage == "push":
            if push_count >= 3 and random.random() < 0.2:
                return random.choice(self.customer_patterns["time_direct"])
            if random.random() < level_prob:
                if push_count == 0:
                    return random.choice(self.customer_patterns["excuse_delay"])
                elif push_count == 1:
                    return random.choice(self.customer_patterns["excuse_financial"])
                elif push_count == 2:
                    return random.choice(self.customer_patterns["excuse_dispute"])
                else:
                    return random.choice(self.customer_patterns["excuse_reject"])
            return random.choice(self.customer_patterns["time_direct"])
        return "..."

    def _excuse_master_response(self, stage: str, chat_group: str, push_count: int) -> str:
        """借口大师回应"""
        if stage in ["greeting", "identity"]:
            return "Ada apa?"
        elif stage == "purpose":
            if chat_group == "H2":
                return random.choice(self.customer_patterns["excuse_busy"])
            elif chat_group == "H1":
                return random.choice(self.customer_patterns["excuse_personal"])
            else:
                return random.choice(self.customer_patterns["excuse_dispute"])
        elif stage in ["ask_time", "push"]:
            if push_count == 0:
                return random.choice(self.customer_patterns["excuse_delay"])
            elif push_count == 1:
                return random.choice(self.customer_patterns["excuse_busy"] +
                                     self.customer_patterns["excuse_financial"])
            elif push_count == 2:
                return random.choice(self.customer_patterns["excuse_personal"] +
                                     self.customer_patterns["excuse_dispute"])
            else:
                return random.choice(self.customer_patterns["excuse_reject"])
        return "..."


# 增强测试用例
ENHANCED_TEST_CASES = [
    # 复合类型测试
    ("H2", "silent+resistant", "H2-沉默+抗拒", False, "high"),
    ("H1", "forgetful+negotiating", "H1-健忘+协商", True, "medium"),
    ("S0", "busy+excuse_master", "S0-忙碌+借口", False, "very_high"),

    # 边界场景测试
    ("S0", "edge_extreme_resistant", "S0-极端抗拒", False, "very_high"),
    ("H1", "edge_total_silent", "H1-完全沉默", False, "high"),
    ("H2", "edge_chaotic", "H2-胡搅蛮缠", False, "medium"),
    ("S0", "edge_shifting_conditions", "S0-条件多变", False, "high"),

    # 渐进抗拒
    ("H2", "gradual_resistant", "H2-渐进抗拒", True, "medium"),
    ("H1", "gradual_resistant", "H1-渐进抗拒", True, "high"),
    ("S0", "gradual_resistant", "S0-渐进抗拒", False, "very_high"),

    # 情绪波动
    ("H2", "mood_swinger", "H2-情绪波动", True, "medium"),
    ("S0", "mood_swinger", "S0-情绪波动", False, "high"),
]


if __name__ == "__main__":
    print("=" * 70)
    print("增强版客户模拟器")
    print("=" * 70)

    simulator = EnhancedCustomerSimulator()

    print("\n1. 测试复合类型:")
    print("-" * 70)

    composite_personas = ["silent+resistant", "forgetful+negotiating", "busy+excuse_master"]
    for persona in composite_personas:
        print(f"\nPersona: {persona}")
        for stage in ["greeting", "purpose", "ask_time"]:
            for push in range(2):
                resp = simulator.generate_response(
                    stage, persona=persona, push_count=push
                )
                print(f"  {stage:12} (push={push}): {resp}")

    print("\n2. 测试边界场景:")
    print("-" * 70)

    edge_personas = ["edge_extreme_resistant", "edge_total_silent", "edge_chaotic", "edge_shifting_conditions"]
    for persona in edge_personas:
        print(f"\nPersona: {persona}")
        for stage in ["greeting", "purpose", "ask_time", "push"]:
            for push in range(2):
                resp = simulator.generate_response(
                    stage, persona=persona, push_count=push
                )
                print(f"  {stage:12} (push={push}): {resp}")

    print("\n" + "=" * 70)
    print("增强版模拟器加载完成！")
    print("=" * 70)
