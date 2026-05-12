#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红黑对抗训练 - 第二轮：仿真客户增强测试
复合类型与边界场景
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

sys.path.append(str(Path(__file__).parent.parent.parent))

from core.evaluation import EvaluationFrameworkV2
from experiments.enhanced_customer_simulator import EnhancedCustomerSimulator, ENHANCED_TEST_CASES


class EnhancedTest:
    """增强版测试"""

    def __init__(self, output_dir: str = "data/outputs/enhanced"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.framework = EvaluationFrameworkV2(use_tts=False)
        self.simulator = EnhancedCustomerSimulator()

    async def run_all_tests(self):
        """运行所有增强测试"""
        print("=" * 80)
        print("🤖 红黑对抗训练 - 第二轮：仿真客户增强")
        print("=" * 80)
        print(f"测试场景数: {len(ENHANCED_TEST_CASES)}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # 替换框架中的模拟器
        self.framework.simulator = self.simulator

        # 运行所有测试
        for idx, (chat_group, persona, description, expected_success, resistance) in enumerate(ENHANCED_TEST_CASES):
            print(f"\n【场景 {idx+1}/{len(ENHANCED_TEST_CASES)}】")
            await self.framework.run_single_test(
                chat_group=chat_group,
                persona=persona,
                description=description,
                expected_success=expected_success,
                resistance_level=resistance
            )

        # 生成报告
        print("\n" + "=" * 80)
        print("📊 增强测试完成，生成报告...")
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
        persona_set = set(r.persona for r in self.framework.results)
        for persona in persona_set:
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
            "test_type": "enhanced",
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
            "findings": self._analyze_findings(),
            "suggestions": self._generate_suggestions()
        }

    def _analyze_findings(self) -> List[Dict[str, Any]]:
        """分析发现"""
        findings = []

        # 复合类型分析
        composite_results = [r for r in self.framework.results if "+" in r.persona]
        if composite_results:
            total = len(composite_results)
            success = sum(1 for r in composite_results if r.success)
            findings.append({
                "type": "composite_performance",
                "total": total,
                "success": success,
                "success_rate": success / total
            })

        # 边界场景分析
        edge_results = [r for r in self.framework.results if r.persona.startswith("edge_")]
        if edge_results:
            total = len(edge_results)
            success = sum(1 for r in edge_results if r.success)
            findings.append({
                "type": "edge_performance",
                "total": total,
                "success": success,
                "success_rate": success / total
            })

        # 特殊类型分析
        special_types = ["gradual_resistant", "mood_swinger"]
        special_results = [r for r in self.framework.results if r.persona in special_types]
        if special_results:
            total = len(special_results)
            success = sum(1 for r in special_results if r.success)
            findings.append({
                "type": "special_performance",
                "total": total,
                "success": success,
                "success_rate": success / total
            })

        return findings

    def _generate_suggestions(self) -> List[str]:
        """生成改进建议"""
        suggestions = []

        # 分析各类型表现
        edge_results = [r for r in self.framework.results if r.persona.startswith("edge_")]
        if edge_results:
            edge_success = sum(1 for r in edge_results if r.success)
            edge_total = len(edge_results)
            if edge_success / edge_total < 0.3:
                suggestions.append("边界场景表现较差，需要专门优化边界应对策略")

        composite_results = [r for r in self.framework.results if "+" in r.persona]
        if composite_results:
            composite_success = sum(1 for r in composite_results if r.success)
            composite_total = len(composite_results)
            if composite_success / composite_total < 0.5:
                suggestions.append("复合类型处理有待提升，需要多特征混合应对")

        suggestions.append("分析失败对话，找出共同模式")
        suggestions.append("考虑增加更多话术变体")
        suggestions.append("优化追问策略，针对不同场景调整")

        return suggestions

    def _save_report(self, report: Dict[str, Any]):
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"enhanced_report_{timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 报告已保存到: {report_file}")

        # 同时保存最新的
        latest_file = self.output_dir / "enhanced_report_latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ 最新报告已保存到: {latest_file}")

    def _print_summary(self, report: Dict[str, Any]):
        """打印摘要"""
        print("\n" + "=" * 80)
        print("📊 增强测试报告")
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
            print(f"  {persona:30}: {data['success']}/{data['total']} ({data['success_rate']:.1%}, 平均 {data['avg_turns']:.1f} 轮)")

        print(f"\n🔍 分析发现:")
        for finding in report["findings"]:
            print(f"  - {finding['type']}: {finding['success']}/{finding['total']} ({finding['success_rate']:.1%})")

        print(f"\n💡 改进建议:")
        for idx, suggestion in enumerate(report["suggestions"], 1):
            print(f"  {idx}. {suggestion}")

        print("\n" + "=" * 80)
        print("✅ 增强测试完成！")
        print("=" * 80)


async def main():
    """主函数"""
    tester = EnhancedTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
