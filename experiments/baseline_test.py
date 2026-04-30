#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红黑对抗训练 - 第一轮：基准建立
运行所有测试场景，记录基准指标
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

sys.path.append(str(Path(__file__).parent))

from evaluation_framework_v2 import EvaluationFrameworkV2, GOLDEN_TEST_CASES_V2
from real_customer_simulator_v2 import RealCustomerSimulatorV2


BASELINE_TEST_SCENARIOS = [
    # H2早期 - 5个场景
    ("H2", "cooperative", "H2早期 + 合作型客户", True, "very_low"),
    ("H2", "busy", "H2早期 + 忙碌型客户", True, "low"),
    ("H2", "negotiating", "H2早期 + 协商型客户", True, "medium"),
    ("H2", "silent", "H2早期 + 沉默型客户", True, "low"),
    ("H2", "forgetful", "H2早期 + 健忘型客户", True, "low"),

    # H1中期 - 4个场景
    ("H1", "cooperative", "H1中期 + 合作型客户", True, "medium"),
    ("H1", "negotiating", "H1中期 + 协商型客户", True, "high"),
    ("H1", "busy", "H1中期 + 忙碌型客户", True, "medium"),
    ("H1", "forgetful", "H1中期 + 健忘型客户", True, "medium"),

    # S0晚期 - 5个场景
    ("S0", "cooperative", "S0晚期 + 合作型客户", True, "medium"),
    ("S0", "negotiating", "S0晚期 + 协商型客户", True, "very_high"),
    ("S0", "resistant", "S0晚期 + 抗拒型客户", False, "very_high"),
    ("S0", "silent", "S0晚期 + 沉默型客户", False, "high"),
    ("S0", "forgetful", "S0晚期 + 健忘型客户", True, "high"),
]


class BaselineTest:
    """基准测试"""

    def __init__(self, output_dir: str = "data/baseline"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.framework = EvaluationFrameworkV2(use_tts=False)

    async def run_all_tests(self):
        """运行所有基准测试"""
        print("=" * 80)
        print("🤖 红黑对抗训练 - 第一轮：基准建立")
        print("=" * 80)
        print(f"测试场景数: {len(BASELINE_TEST_SCENARIOS)}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # 运行所有测试
        for idx, (chat_group, persona, description, expected_success, resistance) in enumerate(BASELINE_TEST_SCENARIOS):
            print(f"\n【场景 {idx+1}/{len(BASELINE_TEST_SCENARIOS)}】")
            await self.framework.run_single_test(
                chat_group=chat_group,
                persona=persona,
                description=description,
                expected_success=expected_success,
                resistance_level=resistance
            )

        # 生成报告
        print("\n" + "=" * 80)
        print("📊 基准测试完成，生成报告...")
        print("=" * 80)
        report = self._generate_report()
        self._save_report(report)
        self._print_summary(report)

        return report

    def _generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        stats = self.framework.stats

        # 详细结果
        detailed_results = []
        for result in self.framework.results:
            detailed_results.append({
                "session_id": result.session_id,
                "chat_group": result.chat_group,
                "persona": result.persona,
                "description": result.description,
                "success": result.success,
                "commit_time": result.commit_time,
                "conversation_length": result.conversation_length,
                "expected_success": result.expected_success,
                "resistance_level": result.resistance_level,
                "push_count": result.push_count,
                "stage_completion": result.stage_completion,
                "timestamp": result.timestamp
            })

        # 按客户类型统计
        by_persona = {}
        for persona in ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful", "excuse_master"]:
            persona_results = [r for r in self.framework.results if r.persona == persona]
            if persona_results:
                total = len(persona_results)
                success = sum(1 for r in persona_results if r.success)
                avg_turns = sum(r.conversation_length for r in persona_results) / total
                avg_push = sum(r.push_count for r in persona_results) / total
                by_persona[persona] = {
                    "total": total,
                    "success": success,
                    "success_rate": success / total if total > 0 else 0,
                    "avg_turns": avg_turns,
                    "avg_push_count": avg_push
                }

        return {
            "test_type": "baseline",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": stats["total"],
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0,
                "true_positive": stats["true_positive"],
                "true_negative": stats["true_negative"],
                "false_positive": stats["false_positive"],
                "false_negative": stats["false_negative"]
            },
            "by_group": stats["by_group"],
            "by_persona": by_persona,
            "by_resistance": stats["by_resistance_level"],
            "detailed_results": detailed_results,
            "weak_points": self._identify_weak_points(),
            "suggestions": self._generate_suggestions()
        }

    def _identify_weak_points(self) -> List[Dict[str, Any]]:
        """识别薄弱环节"""
        weak_points = []

        # 成功率 < 80% 的客户类型
        by_persona = {}
        for result in self.framework.results:
            if result.persona not in by_persona:
                by_persona[result.persona] = []
            by_persona[result.persona].append(result)

        for persona, results in by_persona.items():
            total = len(results)
            success = sum(1 for r in results if r.success)
            rate = success / total if total > 0 else 0
            if rate < 0.8:
                weak_points.append({
                    "type": "persona_low_success",
                    "persona": persona,
                    "success_rate": rate,
                    "total_tests": total,
                    "severity": "high" if rate < 0.6 else "medium"
                })

        # S0晚期的成功率
        s0_results = [r for r in self.framework.results if r.chat_group == "S0"]
        if s0_results:
            s0_total = len(s0_results)
            s0_success = sum(1 for r in s0_results if r.success)
            s0_rate = s0_success / s0_total if s0_total > 0 else 0
            if s0_rate < 0.7:
                weak_points.append({
                    "type": "s0_low_success",
                    "success_rate": s0_rate,
                    "total_tests": s0_total,
                    "severity": "high"
                })

        return weak_points

    def _generate_suggestions(self) -> List[str]:
        """生成改进建议"""
        suggestions = []

        # 检查薄弱环节
        weak_points = self._identify_weak_points()

        for point in weak_points:
            if point["type"] == "persona_low_success":
                suggestions.append(f"优先优化 {point['persona']} 类型客户的话术（成功率：{point['success_rate']:.1%}）")
            elif point["type"] == "s0_low_success":
                suggestions.append("S0晚期环节需要强化施压策略")

        suggestions.append("收集失败案例，分析共同模式")
        suggestions.append("为抗拒型客户补充更多应对话术")
        suggestions.append("增加时间检测的鲁棒性")

        return suggestions

    def _save_report(self, report: Dict[str, Any]):
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"baseline_report_{timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 报告已保存到: {report_file}")

        # 同时保存一份最新的
        latest_file = self.output_dir / "baseline_report_latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ 最新报告已保存到: {latest_file}")

    def _print_summary(self, report: Dict[str, Any]):
        """打印摘要"""
        print("\n" + "=" * 80)
        print("📊 基准测试报告")
        print("=" * 80)

        summary = report["summary"]
        print(f"\n📈 总体指标:")
        print(f"  总测试数: {summary['total_tests']}")
        print(f"  成功: {summary['success']}")
        print(f"  失败: {summary['failed']}")
        print(f"  成功率: {summary['success_rate']:.1%}")
        print(f"  TP: {summary['true_positive']}, TN: {summary['true_negative']}")
        print(f"  FP: {summary['false_positive']}, FN: {summary['false_negative']}")

        print(f"\n📊 按环节统计:")
        for group, data in report["by_group"].items():
            rate = data['success'] / data['total'] if data['total'] > 0 else 0
            print(f"  {group}: {data['success']}/{data['total']} ({rate:.1%})")

        print(f"\n📊 按客户类型统计:")
        for persona, data in report["by_persona"].items():
            print(f"  {persona:15}: {data['success']}/{data['total']} ({data['success_rate']:.1%}), 平均 {data['avg_turns']:.1f} 轮")

        print(f"\n⚠️  薄弱环节:")
        if report["weak_points"]:
            for point in report["weak_points"]:
                print(f"  - {point['type']}: {point.get('persona', '')} 成功率 {point.get('success_rate',0):.1%}")
        else:
            print("  无明显薄弱环节")

        print(f"\n💡 改进建议:")
        for idx, suggestion in enumerate(report["suggestions"], 1):
            print(f"  {idx}. {suggestion}")

        print("\n" + "=" * 80)
        print("✅ 基准建立完成！")
        print("=" * 80)


async def main():
    """主函数"""
    tester = BaselineTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
