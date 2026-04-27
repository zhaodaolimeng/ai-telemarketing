#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小规模生产测试 - 模拟1000通对话
"""
import asyncio
import random
import time
import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

from experiments.collection_chatbot_v3 import CollectionChatBot, get_stage_from_state
from experiments.real_customer_simulator_v2 import RealCustomerSimulatorV2, CustomerPersona


@dataclass
class TestResult:
    """测试结果"""
    session_id: str
    chat_group: str
    persona: str
    success: bool
    commit_time: str
    turns: int
    duration: float


class LargeScaleTester:
    """大规模测试器"""

    def __init__(self, num_tests: int = 1000):
        self.num_tests = num_tests
        self.simulator = RealCustomerSimulatorV2()
        self.results: List[TestResult] = []
        self.chat_groups = ["H2", "H1", "S0"]
        self.personas = [
            "cooperative",
            "busy",
            "negotiating",
            "resistant",
            "silent",
            "forgetful",
            "excuse_master"
        ]

    def select_random_params(self) -> tuple:
        """随机选择测试参数"""
        chat_group = random.choice(self.chat_groups)
        persona = random.choice(self.personas)
        return chat_group, persona

    async def run_single_test(self, test_id: int) -> TestResult:
        """运行单个测试"""
        chat_group, persona = self.select_random_params()

        start_time = time.time()
        bot = CollectionChatBot(
            chat_group=chat_group,
            customer_name="Test User"
        )

        # 开始对话
        agent_text, _ = await bot.process(use_tts=False)

        push_count = 0
        max_turns = 30

        for turn in range(max_turns):
            if bot.is_finished():
                break

            # 检测是否在询问时间
            if "jam berapa" in agent_text.lower() or "kapan" in agent_text.lower():
                push_count += 1

            # 生成客户响应
            customer_text = self.simulator.generate_response(
                stage=get_stage_from_state(bot.state),
                chat_group=chat_group,
                persona=persona,
                push_count=push_count
            )

            agent_text, _ = await bot.process(customer_text, use_tts=False)

        duration = time.time() - start_time

        result = TestResult(
            session_id=bot.session_id,
            chat_group=chat_group,
            persona=persona,
            success=bot.is_successful(),
            commit_time=bot.commit_time or "",
            turns=len(bot.conversation),
            duration=duration
        )

        # 进度显示
        if (test_id + 1) % 100 == 0:
            print(f"已完成 {test_id + 1}/{self.num_tests} 测试")

        return result

    async def run_all_tests(self, concurrency: int = 10) -> List[TestResult]:
        """运行所有测试"""
        print(f"开始小规模生产测试: {self.num_tests} 通对话")
        print(f"并发数: {concurrency}")
        print("=" * 70)

        self.results = []

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_test(test_id: int) -> TestResult:
            async with semaphore:
                return await self.run_single_test(test_id)

        # 创建任务
        tasks = [bounded_test(i) for i in range(self.num_tests)]
        self.results = await asyncio.gather(*tasks)

        print("=" * 70)
        print("测试完成!")

        return self.results

    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        if not self.results:
            return {"error": "没有测试结果"}

        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        success_rate = successful / total * 100

        # 按组别统计
        group_stats = {}
        for group in self.chat_groups:
            group_results = [r for r in self.results if r.chat_group == group]
            group_total = len(group_results)
            group_success = sum(1 for r in group_results if r.success)
            group_stats[group] = {
                "total": group_total,
                "successful": group_success,
                "success_rate": group_success / group_total * 100 if group_total > 0 else 0,
                "avg_turns": sum(r.turns for r in group_results) / group_total if group_total > 0 else 0,
                "avg_duration": sum(r.duration for r in group_results) / group_total if group_total > 0 else 0
            }

        # 按客户类型统计
        persona_stats = {}
        for persona in self.personas:
            persona_results = [r for r in self.results if r.persona == persona]
            persona_total = len(persona_results)
            persona_success = sum(1 for r in persona_results if r.success)
            persona_stats[persona] = {
                "total": persona_total,
                "successful": persona_success,
                "success_rate": persona_success / persona_total * 100 if persona_total > 0 else 0
            }

        # 整体统计
        avg_turns = sum(r.turns for r in self.results) / total
        avg_duration = sum(r.duration for r in self.results) / total

        return {
            "summary": {
                "total_tests": total,
                "successful_tests": successful,
                "failed_tests": total - successful,
                "success_rate": round(success_rate, 2),
                "avg_turns": round(avg_turns, 1),
                "avg_duration_seconds": round(avg_duration, 2)
            },
            "by_chat_group": group_stats,
            "by_persona": persona_stats
        }

    def save_report(self, report: Dict[str, Any], output_file: str = "data/test_report.json"):
        """保存报告"""
        Path("data").mkdir(exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存到: {output_file}")

    def print_report(self, report: Dict[str, Any]):
        """打印报告"""
        print("\n" + "=" * 70)
        print("小规模生产测试报告")
        print("=" * 70)

        summary = report["summary"]
        print(f"\n总测试数: {summary['total_tests']}")
        print(f"成功: {summary['successful_tests']}")
        print(f"失败: {summary['failed_tests']}")
        print(f"成功率: {summary['success_rate']}%")
        print(f"平均回合数: {summary['avg_turns']}")
        print(f"平均耗时: {summary['avg_duration_seconds']}s")

        print("\n--- 按催收组别 ---")
        for group, stats in report["by_chat_group"].items():
            print(f"  {group}: {stats['success_rate']:.1f}% ({stats['successful']}/{stats['total']})")

        print("\n--- 按客户类型 ---")
        for persona, stats in report["by_persona"].items():
            print(f"  {persona:15}: {stats['success_rate']:5.1f}% ({stats['successful']}/{stats['total']})")

        print("\n" + "=" * 70)


async def main():
    """主函数"""
    import sys

    num_tests = 1000
    if len(sys.argv) > 1:
        try:
            num_tests = int(sys.argv[1])
        except ValueError:
            pass

    tester = LargeScaleTester(num_tests=num_tests)
    await tester.run_all_tests(concurrency=20)

    report = tester.generate_report()
    tester.print_report(report)
    tester.save_report(report)


if __name__ == "__main__":
    asyncio.run(main())
