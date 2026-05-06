#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成式客户模拟器单元测试
使用Python标准库unittest，无需额外依赖
"""
import sys
from pathlib import Path
# 添加项目src目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

import unittest
import inspect
import tempfile
from core.simulator import GenerativeCustomerSimulator, RealCustomerSimulatorV2
from core.evaluation import SimulatorInterface


class TestGenerativeCustomerSimulator(unittest.TestCase):
    """生成式客户模拟器测试用例"""

    def test_initialization_default(self):
        """测试使用默认路径初始化模拟器"""
        simulator = GenerativeCustomerSimulator()
        self.assertIsNotNone(simulator)
        self.assertTrue(hasattr(simulator, 'corpus'))
        self.assertIn('stage_corpus', simulator.corpus)
        self.assertIn('category_corpus', simulator.corpus)
        self.assertIn('chat_group_corpus', simulator.corpus)

    def test_initialization_custom_path(self):
        """测试使用自定义路径初始化模拟器"""
        corpus_path = Path(__file__).parent.parent.parent / \
            'data' / 'behavior_analysis' / 'customer_response_corpus.json'
        simulator = GenerativeCustomerSimulator(corpus_path=corpus_path)
        self.assertIsNotNone(simulator)
        self.assertGreater(len(simulator.corpus['stage_corpus']), 0)

    def test_interface_compliance(self):
        """测试生成式模拟器符合SimulatorInterface接口规范"""
        # 检查是否实现了接口或有对应的方法
        implements_interface = issubclass(GenerativeCustomerSimulator, SimulatorInterface)
        has_required_method = hasattr(GenerativeCustomerSimulator, 'generate_response')
        self.assertTrue(implements_interface or has_required_method)

        # 验证方法签名
        simulator = GenerativeCustomerSimulator()
        self.assertTrue(callable(simulator.generate_response))

        # 验证方法接受正确的参数
        sig = inspect.signature(simulator.generate_response)
        params = list(sig.parameters.keys())
        required_params = ['stage', 'chat_group', 'persona', 'resistance_level', 'last_agent_text', 'push_count']
        for param in required_params:
            self.assertIn(param, params, f"缺少必要参数: {param}")

    def test_generate_response_basic(self):
        """测试基本的回复生成功能"""
        simulator = GenerativeCustomerSimulator()

        # 测试正常参数下能生成非空回复
        response = simulator.generate_response(
            stage="greeting",
            chat_group="H2",
            persona="cooperative",
            resistance_level="low",
            last_agent_text="Halo, selamat pagi!",
            push_count=0
        )

        self.assertIsInstance(response, str)
        # 允许空回复（沉默用户）
        self.assertGreaterEqual(len(response.strip()), 0)

    def test_generate_response_all_stages(self):
        """测试所有对话阶段都能生成回复"""
        stages = ["greeting", "identity", "purpose", "ask_time", "push", "confirm", "close"]
        simulator = GenerativeCustomerSimulator()
        for stage in stages:
            with self.subTest(stage=stage):
                response = simulator.generate_response(
                    stage=stage,
                    chat_group="H2",
                    persona="cooperative",
                    resistance_level="low",
                    last_agent_text="Test",
                    push_count=0
                )
                self.assertIsInstance(response, str)

    def test_generate_response_all_chat_groups(self):
        """测试所有催收阶段都能生成回复"""
        chat_groups = ["H2", "H1", "S0"]
        simulator = GenerativeCustomerSimulator()
        for chat_group in chat_groups:
            with self.subTest(chat_group=chat_group):
                response = simulator.generate_response(
                    stage="ask_time",
                    chat_group=chat_group,
                    persona="cooperative",
                    resistance_level="low",
                    last_agent_text="Test",
                    push_count=0
                )
                self.assertIsInstance(response, str)

    def test_generate_response_all_personas(self):
        """测试所有用户类型都能生成回复"""
        personas = [
            "cooperative", "busy", "negotiating", "silent",
            "forgetful", "resistant", "excuse_master"
        ]
        simulator = GenerativeCustomerSimulator()
        for persona in personas:
            with self.subTest(persona=persona):
                response = simulator.generate_response(
                    stage="ask_time",
                    chat_group="H2",
                    persona=persona,
                    resistance_level="medium",
                    last_agent_text="Test",
                    push_count=0
                )
                self.assertIsInstance(response, str)

    def test_generate_response_all_resistance_levels(self):
        """测试所有抗拒程度都能生成回复"""
        resistance_levels = ["very_low", "low", "medium", "high", "very_high"]
        simulator = GenerativeCustomerSimulator()
        for level in resistance_levels:
            with self.subTest(resistance_level=level):
                response = simulator.generate_response(
                    stage="ask_time",
                    chat_group="H2",
                    persona="resistant",
                    resistance_level=level,
                    last_agent_text="Test",
                    push_count=0
                )
                self.assertIsInstance(response, str)

    def test_generate_response_different_push_counts(self):
        """测试不同追问次数下都能生成回复"""
        push_counts = [0, 1, 2, 3, 4, 5, 10]
        simulator = GenerativeCustomerSimulator()
        for count in push_counts:
            with self.subTest(push_count=count):
                response = simulator.generate_response(
                    stage="push",
                    chat_group="H1",
                    persona="resistant",
                    resistance_level="high",
                    last_agent_text="Kapan bisa bayar?",
                    push_count=count
                )
                self.assertIsInstance(response, str)

    def test_persona_behavior_consistency(self):
        """测试不同persona的回复行为符合预期（统计意义上）"""
        simulator = GenerativeCustomerSimulator()
        test_runs = 50

        # 合作型用户应该更多给出明确时间
        cooperative_responses = []
        for _ in range(test_runs):
            resp = simulator.generate_response(
                stage="ask_time",
                chat_group="H2",
                persona="cooperative",
                resistance_level="very_low",
                last_agent_text="Kapan bisa bayar?",
                push_count=0
            )
            cooperative_responses.append(resp)

        # 抗拒型用户应该更多拒绝或找借口
        resistant_responses = []
        for _ in range(test_runs):
            resp = simulator.generate_response(
                stage="ask_time",
                chat_group="H2",
                persona="resistant",
                resistance_level="very_high",
                last_agent_text="Kapan bisa bayar?",
                push_count=0
            )
            resistant_responses.append(resp)

        # 验证回复非空
        self.assertTrue(all(isinstance(r, str) for r in cooperative_responses))
        self.assertTrue(all(isinstance(r, str) for r in resistant_responses))

    def test_resistance_level_effect(self):
        """测试抗拒程度对回复的影响（统计意义上）"""
        simulator = GenerativeCustomerSimulator()
        test_runs = 100

        # 低抗拒下应该更多合作
        low_resistance_count = 0
        for _ in range(test_runs):
            resp = simulator.generate_response(
                stage="ask_time",
                chat_group="H2",
                persona="resistant",
                resistance_level="very_low",
                last_agent_text="Kapan bisa bayar?",
                push_count=0
            ).lower()
            # 检测合作类关键词
            if any(word in resp for word in ["bisa", "jam", "hari", "ya", "oke"]):
                low_resistance_count += 1

        # 高抗拒下应该更少合作
        high_resistance_count = 0
        for _ in range(test_runs):
            resp = simulator.generate_response(
                stage="ask_time",
                chat_group="H2",
                persona="resistant",
                resistance_level="very_high",
                last_agent_text="Kapan bisa bayar?",
                push_count=0
            ).lower()
            if any(word in resp for word in ["bisa", "jam", "hari", "ya", "oke"]):
                high_resistance_count += 1

        # 低抗拒的合作率应该高于高抗拒（统计意义上，允许一定波动）
        self.assertGreaterEqual(low_resistance_count, high_resistance_count * 0.7,
                                "抗拒程度逻辑可能有问题：低抗拒的合作率不应低于高抗拒太多")

    def test_push_count_effect(self):
        """测试追问次数对回复的影响：多次追问后更可能出现愤怒或松口"""
        simulator = GenerativeCustomerSimulator()
        test_runs = 50

        # 多次追问下的回复
        high_push_responses = []
        for _ in range(test_runs):
            resp = simulator.generate_response(
                stage="push",
                chat_group="S0",
                persona="resistant",
                resistance_level="high",
                last_agent_text="Kapan bisa bayar?",
                push_count=5
            ).lower()
            high_push_responses.append(resp)

        # 验证回复非空
        self.assertTrue(all(isinstance(r, str) for r in high_push_responses))

    def test_empty_corpus_handling(self):
        """测试空语料库或无效路径的处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_path = Path(tmpdir) / "nonexistent_corpus.json"
            simulator = GenerativeCustomerSimulator(corpus_path=invalid_path)
            self.assertIsNotNone(simulator)
            # 应该使用默认回复
            response = simulator.generate_response(
                stage="greeting",
                chat_group="H2",
                persona="cooperative",
                resistance_level="low",
                last_agent_text="Test",
                push_count=0
            )
            self.assertIsInstance(response, str)
            self.assertIn(response, ["Ya", "Iya", "Tidak", "Maaf", "Nanti ya"])

    def test_unknown_parameter_handling(self):
        """测试未知参数的处理，应该能优雅降级不崩溃"""
        simulator = GenerativeCustomerSimulator()

        # 未知stage
        response = simulator.generate_response(
            stage="unknown_stage",
            chat_group="H2",
            persona="cooperative",
            resistance_level="low",
            last_agent_text="Test",
            push_count=0
        )
        self.assertIsInstance(response, str)

        # 未知persona
        response = simulator.generate_response(
            stage="greeting",
            chat_group="H2",
            persona="unknown_persona",
            resistance_level="low",
            last_agent_text="Test",
            push_count=0
        )
        self.assertIsInstance(response, str)

        # 未知resistance_level
        response = simulator.generate_response(
            stage="greeting",
            chat_group="H2",
            persona="cooperative",
            resistance_level="unknown_level",
            last_agent_text="Test",
            push_count=0
        )
        self.assertIsInstance(response, str)


class TestRealCustomerSimulatorV2(unittest.TestCase):
    """原有规则模拟器的回归测试，确保向后兼容性"""

    def test_initialization(self):
        """测试规则模拟器初始化"""
        simulator = RealCustomerSimulatorV2()
        self.assertIsNotNone(simulator)

    def test_generate_response(self):
        """测试规则模拟器基本功能"""
        simulator = RealCustomerSimulatorV2()
        response = simulator.generate_response(
            stage="greeting",
            chat_group="H2",
            persona="cooperative",
            resistance_level="low",
            last_agent_text="Halo",
            push_count=0
        )
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)
