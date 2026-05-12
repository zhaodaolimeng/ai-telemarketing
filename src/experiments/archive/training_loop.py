#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红黑对抗训练 - 第四轮：自动化训练闭环框架
自动测试 -> 分析失败 -> 生成改进建议 -> 优化策略
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent.parent))

from core.evaluation import EvaluationFrameworkV2
from core.simulator import RealCustomerSimulatorV2, GOLDEN_TEST_CASES_V2


@dataclass
class FailurePattern:
    """失败模式"""
    pattern_type: str
    description: str
    examples: List[str]
    severity: str  # high/medium/low
    occurrences: int


@dataclass
class ImprovementSuggestion:
    """改进建议"""
    category: str  # script/logic/prompt
    priority: str  # high/medium/low
    description: str
    implementation_hint: Optional[str] = None


class AdversarialTrainer:
    """对抗训练器"""

    def __init__(self, output_dir: str = "data/outputs/training"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.framework = EvaluationFrameworkV2(use_tts=False)
        self.benchmark_results = []

    async def run_full_cycle(self) -> Dict[str, Any]:
        """运行完整训练循环"""
        print("=" * 80)
        print("🔄 红黑对抗训练 - 自动化训练闭环")
        print("=" * 80)

        # 1. 运行基准测试
        print("\n📊 步骤 1/4: 运行基准测试")
        baseline = await self._run_baseline_test()

        # 2. 分析失败案例
        print("\n🔍 步骤 2/4: 分析失败案例")
        failure_patterns = self._analyze_failures(baseline)

        # 3. 生成改进建议
        print("\n💡 步骤 3/4: 生成改进建议")
        suggestions = self._generate_suggestions(failure_patterns, baseline)

        # 4. 生成改进报告
        print("\n📝 步骤 4/4: 生成改进报告")
        report = self._create_training_report(
            baseline, failure_patterns, suggestions
        )

        self._save_report(report)
        self._print_summary(report)

        return report

    async def _run_baseline_test(self) -> Dict[str, Any]:
        """运行基准测试"""
        test_cases = GOLDEN_TEST_CASES_V2

        for idx, (chat_group, persona, description, expected_success, resistance) in enumerate(test_cases):
            print(f"  运行 {idx+1}/{len(test_cases)}: {description}")
            await self.framework.run_single_test(
                chat_group=chat_group,
                persona=persona,
                description=description,
                expected_success=expected_success,
                resistance_level=resistance
            )

        stats = self.framework.stats
        return {
            "stats": stats,
            "results": self.framework.results,
            "timestamp": datetime.now().isoformat()
        }

    def _analyze_failures(self, baseline: Dict[str, Any]) -> List[FailurePattern]:
        """分析失败模式"""
        patterns = []

        # 收集所有失败案例
        failures = [r for r in baseline["results"] if not r.success]

        if not failures:
            return patterns

        # 按环节分组失败
        failures_by_group = defaultdict(list)
        for f in failures:
            failures_by_group[f.chat_group].append(f)

        for group, group_failures in failures_by_group.items():
            if len(group_failures) >= 2:
                patterns.append(FailurePattern(
                    pattern_type="group_failure_cluster",
                    description=f"{group} 环节存在多个失败",
                    examples=[f.description for f in group_failures],
                    severity="high" if len(group_failures) >= 3 else "medium",
                    occurrences=len(group_failures)
                ))

        # 按客户类型分组失败
        failures_by_persona = defaultdict(list)
        for f in failures:
            failures_by_persona[f.persona].append(f)

        for persona, persona_failures in failures_by_persona.items():
            if len(persona_failures) >= 2:
                patterns.append(FailurePattern(
                    pattern_type="persona_failure_cluster",
                    description=f"{persona} 类型客户存在多个失败",
                    examples=[f.description for f in persona_failures],
                    severity="high" if len(persona_failures) >= 3 else "medium",
                    occurrences=len(persona_failures)
                ))

        # 分析追问次数与失败的关系
        high_push_failures = [f for f in failures if f.push_count >= 3]
        if high_push_failures:
            patterns.append(FailurePattern(
                pattern_type="high_push_failure",
                description=f"多次追问({3}+)后仍失败",
                examples=[f.description for f in high_push_failures],
                severity="medium",
                occurrences=len(high_push_failures)
            ))

        return patterns

    def _generate_suggestions(
        self, patterns: List[FailurePattern], baseline: Dict[str, Any]
    ) -> List[ImprovementSuggestion]:
        """生成改进建议"""
        suggestions = []

        stats = baseline["stats"]

        # 基于成功率的建议
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0

        if success_rate < 0.7:
            suggestions.append(ImprovementSuggestion(
                category="logic",
                priority="high",
                description="整体成功率偏低，需要检查核心流程逻辑",
                implementation_hint="检查状态转移逻辑，确保关键步骤覆盖"
            ))

        # 基于失败模式的建议
        for pattern in patterns:
            if pattern.pattern_type.startswith("group"):
                suggestions.append(ImprovementSuggestion(
                    category="script",
                    priority=pattern.severity,
                    description=f"{pattern.description}，需要优化该环节话术",
                    implementation_hint="增加更多话术变体，调整施压策略"
                ))
            elif pattern.pattern_type.startswith("persona"):
                suggestions.append(ImprovementSuggestion(
                    category="script",
                    priority=pattern.severity,
                    description=f"{pattern.description}，需要设计针对性应对话术",
                    implementation_hint="分析该客户类型特征，补充场景化话术"
                ))
            elif pattern.pattern_type == "high_push_failure":
                suggestions.append(ImprovementSuggestion(
                    category="logic",
                    priority=pattern.severity,
                    description="追问策略需要优化，多次追问无效",
                    implementation_hint="设计追问升级策略，考虑适时结束"
                ))

        # 通用建议
        suggestions.append(ImprovementSuggestion(
            category="script",
            priority="medium",
            description="增加话术多样性，减少重复感",
            implementation_hint="为每个阶段准备3-5个变体话术"
        ))

        suggestions.append(ImprovementSuggestion(
            category="logic",
            priority="low",
            description="完善时间检测，支持更多时间表达",
            implementation_hint="扩展时间识别正则表达式"
        ))

        return suggestions

    def _create_training_report(
        self,
        baseline: Dict[str, Any],
        patterns: List[FailurePattern],
        suggestions: List[ImprovementSuggestion]
    ) -> Dict[str, Any]:
        """创建训练报告"""
        stats = baseline["stats"]

        return {
            "report_type": "adversarial_training",
            "timestamp": datetime.now().isoformat(),
            "baseline": {
                "total": stats["total"],
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0,
                "true_positive": stats["true_positive"],
                "true_negative": stats["true_negative"],
                "false_positive": stats["false_positive"],
                "false_negative": stats["false_negative"],
            },
            "failure_patterns": [
                {
                    "type": p.pattern_type,
                    "description": p.description,
                    "examples": p.examples,
                    "severity": p.severity,
                    "occurrences": p.occurrences
                }
                for p in patterns
            ],
            "suggestions": [
                {
                    "category": s.category,
                    "priority": s.priority,
                    "description": s.description,
                    "implementation_hint": s.implementation_hint
                }
                for s in suggestions
            ],
            "action_plan": self._generate_action_plan(suggestions)
        }

    def _generate_action_plan(self, suggestions: List[ImprovementSuggestion]) -> List[Dict]:
        """生成行动计划"""
        action_plan = []

        # 按优先级排序
        high_priority = [s for s in suggestions if s.priority == "high"]
        medium_priority = [s for s in suggestions if s.priority == "medium"]
        low_priority = [s for s in suggestions if s.priority == "low"]

        step = 1
        for s in high_priority:
            action_plan.append({
                "step": step,
                "priority": "high",
                "category": s.category,
                "task": s.description,
                "status": "pending"
            })
            step += 1

        for s in medium_priority:
            action_plan.append({
                "step": step,
                "priority": "medium",
                "category": s.category,
                "task": s.description,
                "status": "pending"
            })
            step += 1

        for s in low_priority:
            action_plan.append({
                "step": step,
                "priority": "low",
                "category": s.category,
                "task": s.description,
                "status": "pending"
            })
            step += 1

        return action_plan

    def _save_report(self, report: Dict[str, Any]):
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"training_report_{timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 训练报告已保存到: {report_file}")

        latest_file = self.output_dir / "training_report_latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ 最新报告已保存到: {latest_file}")

    def _print_summary(self, report: Dict[str, Any]):
        """打印摘要"""
        print("\n" + "=" * 80)
        print("📋 训练报告摘要")
        print("=" * 80)

        baseline = report["baseline"]
        print(f"\n📊 基准测试结果:")
        print(f"  总测试数: {baseline['total']}")
        print(f"  成功: {baseline['success']}")
        print(f"  失败: {baseline['failed']}")
        print(f"  成功率: {baseline['success_rate']:.1%}")
        print(f"  TP: {baseline['true_positive']}, TN: {baseline['true_negative']}")
        print(f"  FP: {baseline['false_positive']}, FN: {baseline['false_negative']}")

        print(f"\n🔴 失败模式:")
        if report["failure_patterns"]:
            for p in report["failure_patterns"]:
                print(f"  - [{p['severity'].upper()}] {p['description']} ({p['occurrences']} 次)")
        else:
            print("  未发现明显失败模式")

        print(f"\n💡 改进建议:")
        for s in report["suggestions"]:
            priority_icon = "🔴" if s["priority"] == "high" else "🟡" if s["priority"] == "medium" else "🟢"
            print(f"  {priority_icon} [{s['category']}] {s['description']}")

        print(f"\n📋 行动计划:")
        for action in report["action_plan"][:5]:  # 只显示前5个
            status_icon = "⏳" if action["status"] == "pending" else "✅"
            print(f"  {status_icon} 步骤 {action['step']}: {action['task']}")

        print("\n" + "=" * 80)
        print("✅ 训练闭环框架就绪！")
        print("=" * 80)


async def main():
    """主函数"""
    trainer = AdversarialTrainer()
    await trainer.run_full_cycle()


if __name__ == "__main__":
    asyncio.run(main())
