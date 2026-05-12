#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小规模生产测试 - 模拟1000通对话
"""
import sys
import asyncio
import random
import time
import json
import argparse
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime

_PROJECT_ROOT = Path(__file__).parent.parent.parent

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, get_stage_from_state
from core.simulator import RealCustomerSimulatorV2, GenerativeCustomerSimulator
from core.evaluation import SimulatorInterface


@dataclass
class TestResult:
    """测试结果"""
    session_id: str
    chat_group: str
    persona: str
    resistance_level: str
    success: bool
    commit_time: str
    turns: int
    duration: float
    conversation_log: Optional[List[Dict[str, str]]] = None


class LargeScaleTester:
    """大规模测试器"""

    def __init__(
        self,
        num_tests: int = 1000,
        simulator: Optional[SimulatorInterface] = None,
        chat_groups: Optional[List[str]] = None,
        personas: Optional[List[str]] = None,
        resistance_levels: Optional[List[str]] = None,
        include_conversation_logs: bool = False
    ):
        self.num_tests = num_tests
        self.simulator = simulator or RealCustomerSimulatorV2()
        self.results: List[TestResult] = []
        self.include_conversation_logs = include_conversation_logs

        # 可配置的测试参数范围
        self.chat_groups = chat_groups or ["H2", "H1", "S0"]
        self.personas = personas or [
            "cooperative",
            "busy",
            "negotiating",
            "resistant",
            "silent",
            "forgetful",
            "excuse_master"
        ]
        self.resistance_levels = resistance_levels or [
            "very_low",
            "low",
            "medium",
            "high",
            "very_high"
        ]

        # 抗拒程度权重，模拟真实分布
        self.resistance_weights = [0.2, 0.25, 0.3, 0.15, 0.1]

    def select_random_params(self) -> tuple:
        """随机选择测试参数"""
        chat_group = random.choice(self.chat_groups)
        persona = random.choice(self.personas)
        resistance_level = random.choices(self.resistance_levels, weights=self.resistance_weights, k=1)[0]
        return chat_group, persona, resistance_level

    async def run_single_test(self, test_id: int) -> TestResult:
        """运行单个测试"""
        chat_group, persona, resistance_level = self.select_random_params()

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
                resistance_level=resistance_level,
                last_agent_text=agent_text,
                push_count=push_count
            )

            agent_text, _ = await bot.process(customer_text, use_tts=False)

        duration = time.time() - start_time

        # 可选保存对话日志
        conversation_log = None
        if self.include_conversation_logs:
            conversation_log = [
                {
                    "speaker": turn["speaker"],
                    "text": turn["text"],
                    "stage": get_stage_from_state(turn["state"])
                } for turn in bot.conversation
            ]

        result = TestResult(
            session_id=bot.session_id,
            chat_group=chat_group,
            persona=persona,
            resistance_level=resistance_level,
            success=bot.is_successful(),
            commit_time=bot.commit_time or "",
            turns=len(bot.conversation),
            duration=duration,
            conversation_log=conversation_log
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
                "success_rate": persona_success / persona_total * 100 if persona_total > 0 else 0,
                "avg_turns": sum(r.turns for r in persona_results) / persona_total if persona_total > 0 else 0
            }

        # 按抗拒程度统计
        resistance_stats = {}
        for level in self.resistance_levels:
            level_results = [r for r in self.results if r.resistance_level == level]
            level_total = len(level_results)
            level_success = sum(1 for r in level_results if r.success)
            resistance_stats[level] = {
                "total": level_total,
                "successful": level_success,
                "success_rate": level_success / level_total * 100 if level_total > 0 else 0,
                "avg_turns": sum(r.turns for r in level_results) / level_total if level_total > 0 else 0
            }

        # 交叉统计：催收阶段 × 抗拒程度
        cross_stats = {}
        for group in self.chat_groups:
            cross_stats[group] = {}
            for level in self.resistance_levels:
                cross_results = [r for r in self.results if r.chat_group == group and r.resistance_level == level]
                cross_total = len(cross_results)
                cross_success = sum(1 for r in cross_results if r.success)
                cross_stats[group][level] = {
                    "total": cross_total,
                    "successful": cross_success,
                    "success_rate": cross_success / cross_total * 100 if cross_total > 0 else 0
                }

        # 失败案例抽样（最多10个）
        failure_examples = []
        failed_results = [r for r in self.results if not r.success]
        for i, failed in enumerate(failed_results[:10]):
            example = {
                "session_id": failed.session_id,
                "chat_group": failed.chat_group,
                "persona": failed.persona,
                "resistance_level": failed.resistance_level,
                "turns": failed.turns,
                "commit_time": failed.commit_time
            }
            if failed.conversation_log:
                example["conversation"] = failed.conversation_log
            failure_examples.append(example)

        # 整体统计
        avg_turns = sum(r.turns for r in self.results) / total
        avg_duration = sum(r.duration for r in self.results) / total

        # 统计不同对话长度的成功率
        turn_bins = {
            "1-5轮": {"count": 0, "success": 0},
            "6-10轮": {"count": 0, "success": 0},
            "11-15轮": {"count": 0, "success": 0},
            "15+轮": {"count": 0, "success": 0}
        }
        for r in self.results:
            if r.turns <= 5:
                bin_name = "1-5轮"
            elif r.turns <= 10:
                bin_name = "6-10轮"
            elif r.turns <= 15:
                bin_name = "11-15轮"
            else:
                bin_name = "15+轮"
            turn_bins[bin_name]["count"] += 1
            if r.success:
                turn_bins[bin_name]["success"] += 1

        for bin_name, stats in turn_bins.items():
            if stats["count"] > 0:
                stats["success_rate"] = stats["success"] / stats["count"] * 100
            else:
                stats["success_rate"] = 0

        return {
            "summary": {
                "total_tests": total,
                "successful_tests": successful,
                "failed_tests": total - successful,
                "success_rate": round(success_rate, 2),
                "avg_turns": round(avg_turns, 1),
                "avg_duration_seconds": round(avg_duration, 2),
                "test_time": datetime.now().isoformat()
            },
            "by_chat_group": group_stats,
            "by_persona": persona_stats,
            "by_resistance_level": resistance_stats,
            "cross_group_resistance": cross_stats,
            "by_turn_count": turn_bins,
            "failure_examples": failure_examples
        }

    def save_report(self, report: Dict[str, Any], output_file: str = "data/outputs/test_report.json"):
        """保存报告"""
        Path("data").mkdir(exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存到: {output_file}")

    def print_report(self, report: Dict[str, Any]):
        """打印报告"""
        print("\n" + "=" * 90)
        print("智能催收系统 小规模生产测试报告")
        print("=" * 90)

        summary = report["summary"]
        print(f"\n📊 总体统计:")
        print(f"  总测试数: {summary['total_tests']}")
        print(f"  成功: {summary['successful_tests']}")
        print(f"  失败: {summary['failed_tests']}")
        print(f"  成功率: {summary['success_rate']}%")
        print(f"  平均回合数: {summary['avg_turns']}")
        print(f"  平均耗时: {summary['avg_duration_seconds']}s")
        print(f"  测试时间: {summary['test_time'][:19]}")

        print("\n🏷️  按催收组别:")
        for group, stats in sorted(report["by_chat_group"].items()):
            print(f"  {group:2}: {stats['success_rate']:5.1f}% ({stats['successful']:3}/{stats['total']:<3}) | 平均回合数: {stats['avg_turns']:.1f}")

        print("\n👤 按客户类型:")
        for persona, stats in sorted(report["by_persona"].items(), key=lambda x: x[1]["success_rate"], reverse=True):
            print(f"  {persona:15}: {stats['success_rate']:5.1f}% ({stats['successful']:3}/{stats['total']:<3}) | 平均回合数: {stats['avg_turns']:.1f}")

        print("\n⚔️  按抗拒程度:")
        for level, stats in sorted(report["by_resistance_level"].items()):
            print(f"  {level:10}: {stats['success_rate']:5.1f}% ({stats['successful']:3}/{stats['total']:<3}) | 平均回合数: {stats['avg_turns']:.1f}")

        print("\n🔢 按对话长度统计:")
        for bin_name, stats in report["by_turn_count"].items():
            print(f"  {bin_name:6}: {stats['success_rate']:5.1f}% ({stats['success']:3}/{stats['count']:<3})")

        print("\n❌ 失败案例抽样:")
        for i, example in enumerate(report["failure_examples"][:5]):
            print(f"  {i+1}. [{example['chat_group']}/{example['persona']}/{example['resistance_level']}] 对话长度: {example['turns']}轮")

        print("\n" + "=" * 90)

    def generate_markdown_report(self, report: Dict[str, Any], output_file: str = "data/outputs/test_report.md"):
        """生成Markdown格式的详细报告"""
        summary = report["summary"]

        md_lines = [
            "# 智能催收系统 测试报告",
            f"**测试时间**: {summary['test_time'][:19]}",
            f"**总测试数**: {summary['total_tests']}",
            f"**成功率**: {summary['success_rate']}% ({summary['successful_tests']}/{summary['total_tests']})",
            f"**平均对话长度**: {summary['avg_turns']} 轮",
            f"**平均耗时**: {summary['avg_duration_seconds']} 秒",
            "",
            "## 1. 按催收阶段统计",
            "| 阶段 | 测试数 | 成功数 | 成功率 | 平均回合数 |",
            "|------|--------|--------|--------|------------|"
        ]

        for group, stats in sorted(report["by_chat_group"].items()):
            md_lines.append(
                f"| {group} | {stats['total']} | {stats['successful']} | {stats['success_rate']:.1f}% | {stats['avg_turns']:.1f} |"
            )

        md_lines.extend([
            "",
            "## 2. 按客户类型统计",
            "| 客户类型 | 测试数 | 成功数 | 成功率 | 平均回合数 |",
            "|----------|--------|--------|--------|------------|"
        ])

        for persona, stats in sorted(report["by_persona"].items(), key=lambda x: x[1]["success_rate"], reverse=True):
            md_lines.append(
                f"| {persona} | {stats['total']} | {stats['successful']} | {stats['success_rate']:.1f}% | {stats['avg_turns']:.1f} |"
            )

        md_lines.extend([
            "",
            "## 3. 按抗拒程度统计",
            "| 抗拒程度 | 测试数 | 成功数 | 成功率 | 平均回合数 |",
            "|----------|--------|--------|--------|------------|"
        ])

        for level, stats in sorted(report["by_resistance_level"].items()):
            md_lines.append(
                f"| {level} | {stats['total']} | {stats['successful']} | {stats['success_rate']:.1f}% | {stats['avg_turns']:.1f} |"
            )

        md_lines.extend([
            "",
            "## 4. 交叉统计（催收阶段 × 抗拒程度）",
            "| 阶段 | very_low | low | medium | high | very_high |",
            "|------|----------|-----|--------|------|-----------|"
        ])

        for group, level_stats in report["cross_group_resistance"].items():
            line = f"| {group} |"
            for level in self.resistance_levels:
                stats = level_stats[level]
                line += f" {stats['success_rate']:.1f}% |"
            md_lines.append(line)

        md_lines.extend([
            "",
            "## 5. 对话长度统计",
            "| 对话长度 | 测试数 | 成功数 | 成功率 |",
            "|----------|--------|--------|--------|"
        ])

        for bin_name, stats in report["by_turn_count"].items():
            md_lines.append(
                f"| {bin_name} | {stats['count']} | {stats['success']} | {stats['success_rate']:.1f}% |"
            )

        if report["failure_examples"]:
            md_lines.extend([
                "",
                "## 6. 失败案例抽样",
                ""
            ])
            for i, example in enumerate(report["failure_examples"][:10]):
                md_lines.append(f"### 案例 {i+1}")
                md_lines.append(f"- **场景**: {example['chat_group']} / {example['persona']} / {example['resistance_level']}")
                md_lines.append(f"- **对话长度**: {example['turns']} 轮")
                md_lines.append(f"- **承诺还款时间**: {example['commit_time'] or '未获取'}")

                if "conversation" in example and example["conversation"]:
                    md_lines.append("- **对话日志**:")
                    for turn in example["conversation"]:
                        speaker = "🤖 坐席" if turn["speaker"] == "agent" else "👤 客户"
                        md_lines.append(f"  {speaker}: {turn['text']}")

                md_lines.append("")

        # 保存报告
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        print(f"Markdown报告已保存到: {output_file}")

    def generate_csv_report(self, report: Dict[str, Any], output_file: str = "data/outputs/test_report.csv"):
        """生成CSV格式的详细结果"""
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # 表头
            writer.writerow([
                "session_id", "chat_group", "persona", "resistance_level",
                "success", "commit_time", "turns", "duration_seconds"
            ])
            # 数据行
            for result in self.results:
                writer.writerow([
                    result.session_id,
                    result.chat_group,
                    result.persona,
                    result.resistance_level,
                    "1" if result.success else "0",
                    result.commit_time,
                    result.turns,
                    round(result.duration, 2)
                ])
        print(f"CSV报告已保存到: {output_file}")

    def compare_with_previous(self, previous_report_path: str, current_report: Dict[str, Any]) -> Dict[str, Any]:
        """与之前的报告做对比，分析效果变化"""
        try:
            with open(previous_report_path, "r", encoding="utf-8") as f:
                previous_report = json.load(f)
        except Exception as e:
            print(f"读取之前的报告失败: {e}")
            return {}

        comparison = {
            "previous_summary": previous_report["summary"],
            "current_summary": current_report["summary"],
            "changes": {}
        }

        # 总体变化
        prev_success = previous_report["summary"]["success_rate"]
        curr_success = current_report["summary"]["success_rate"]
        comparison["changes"]["overall_success_rate"] = {
            "previous": prev_success,
            "current": curr_success,
            "delta": round(curr_success - prev_success, 2)
        }

        # 按组变化
        group_changes = {}
        for group in self.chat_groups:
            prev_stat = previous_report["by_chat_group"].get(group, {})
            curr_stat = current_report["by_chat_group"].get(group, {})
            if prev_stat and curr_stat and "success_rate" in prev_stat and "success_rate" in curr_stat:
                prev_rate = prev_stat["success_rate"]
                curr_rate = curr_stat["success_rate"]
                group_changes[group] = {
                    "previous": prev_rate,
                    "current": curr_rate,
                    "delta": round(curr_rate - prev_rate, 2)
                }
        comparison["changes"]["by_chat_group"] = group_changes

        # 按客户类型变化
        persona_changes = {}
        for persona in self.personas:
            prev_stat = previous_report["by_persona"].get(persona, {})
            curr_stat = current_report["by_persona"].get(persona, {})
            if prev_stat and curr_stat and "success_rate" in prev_stat and "success_rate" in curr_stat:
                prev_rate = prev_stat["success_rate"]
                curr_rate = curr_stat["success_rate"]
                persona_changes[persona] = {
                    "previous": prev_rate,
                    "current": curr_rate,
                    "delta": round(curr_rate - prev_rate, 2)
                }
        comparison["changes"]["by_persona"] = persona_changes

        # 打印对比结果
        print("\n" + "=" * 70)
        print("与之前版本对比结果")
        print("=" * 70)
        overall_delta = comparison["changes"]["overall_success_rate"]["delta"]
        print(f"总体成功率变化: {prev_success:.1f}% → {curr_success:.1f}% ({'+' if overall_delta > 0 else ''}{overall_delta:.1f}%)")
        if overall_delta >= 2:
            print("✅ 效果明显提升！")
        elif overall_delta > 0:
            print("✅ 效果略有提升")
        elif overall_delta == 0:
            print("⚪ 效果持平")
        elif overall_delta > -2:
            print("⚠️  效果略有下降")
        else:
            print("❌ 效果明显下降！")

        print("\n按催收组别变化:")
        for group, change in group_changes.items():
            delta = change["delta"]
            delta_str = f"({'+' if delta > 0 else ''}{delta:.1f}%)"
            print(f"  {group}: {change['previous']:.1f}% → {change['current']:.1f}% {delta_str}")

        print("\n" + "=" * 70)

        return comparison


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能催收系统 大规模生产测试工具")
    parser.add_argument("num_tests", nargs="?", type=int, default=1000, help="测试次数（默认: 1000）")
    parser.add_argument("--use-generative", action="store_true", help="使用数据驱动生成式客户模拟器（默认: 规则模拟器）")
    parser.add_argument("--chat-groups", nargs="+", choices=["H2", "H1", "S0"], help="指定测试的催收阶段（默认: 全部）")
    parser.add_argument("--personas", nargs="+", choices=[
        "cooperative", "busy", "negotiating", "resistant", "silent", "forgetful", "excuse_master"
    ], help="指定测试的客户类型（默认: 全部）")
    parser.add_argument("--resistance-levels", nargs="+", choices=[
        "very_low", "low", "medium", "high", "very_high"
    ], help="指定测试的抗拒程度（默认: 全部）")
    parser.add_argument("--include-logs", action="store_true", help="在报告中包含对话日志（失败案例）")
    parser.add_argument("--concurrency", type=int, default=20, help="并发数（默认: 20）")
    parser.add_argument("--output-prefix", type=str, default="test_report", help="输出文件前缀（默认: test_report）")
    parser.add_argument("--compare", type=str, help="与之前的报告对比，指定报告路径")
    parser.add_argument("--generate-md", action="store_true", help="生成Markdown格式的详细报告")
    parser.add_argument("--generate-csv", action="store_true", help="生成CSV格式的详细结果")

    args = parser.parse_args()

    # 选择模拟器
    if args.use_generative:
        print("使用数据驱动生成式客户模拟器")
        simulator = GenerativeCustomerSimulator()
    else:
        print("使用规则增强版客户模拟器")
        simulator = None  # 用默认

    # 创建测试器
    tester = LargeScaleTester(
        num_tests=args.num_tests,
        simulator=simulator,
        chat_groups=args.chat_groups,
        personas=args.personas,
        resistance_levels=args.resistance_levels,
        include_conversation_logs=args.include_logs
    )

    # 运行测试
    await tester.run_all_tests(concurrency=args.concurrency)

    # 生成报告
    report = tester.generate_report()

    # 打印报告
    tester.print_report(report)

    # 保存JSON报告
    output_dir = _PROJECT_ROOT / "data/outputs/test_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"{args.output_prefix}_{timestamp}.json"
    tester.save_report(report, str(json_path))

    # 生成Markdown报告
    if args.generate_md:
        md_path = output_dir / f"{args.output_prefix}_{timestamp}.md"
        tester.generate_markdown_report(report, str(md_path))

    # 生成CSV报告
    if args.generate_csv:
        csv_path = output_dir / f"{args.output_prefix}_{timestamp}.csv"
        tester.generate_csv_report(report, str(csv_path))

    # 与之前的报告对比
    if args.compare:
        tester.compare_with_previous(args.compare, report)


if __name__ == "__main__":
    asyncio.run(main())
