#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键评估流水线 - 自动化运行所有评估并生成统一报告
"""
import sys
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from core.evaluation import EvaluationFrameworkV2, GoldenDatasetTestCaseProvider


class EvaluationPipeline:
    """一键评估流水线"""

    def __init__(self, output_dir: str = "data/evaluations"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results: Dict[str, Any] = {}

    async def run_golden_dataset_evaluation(self, case_ids: List[str] = None, priority_threshold: float = None) -> Dict[str, Any]:
        """运行黄金数据集评估"""
        print("\n" + "=" * 80)
        print("运行黄金数据集评估")
        print("=" * 80)

        framework = EvaluationFrameworkV2(
            simulator=None,  # 回放测试不需要模拟器
            use_tts=False
        )

        await framework.run_golden_dataset_evaluation(
            case_ids=case_ids,
            priority_threshold=priority_threshold
        )

        # 保存结果
        result = {
            "total": framework.stats["total"],
            "success": framework.stats["success"],
            "failed": framework.stats["failed"],
            "success_rate": framework.stats["success"] / framework.stats["total"] * 100 if framework.stats["total"] > 0 else 0,
            "true_positive": framework.stats["true_positive"],
            "true_negative": framework.stats["true_negative"],
            "false_positive": framework.stats["false_positive"],
            "false_negative": framework.stats["false_negative"],
            "accuracy": (framework.stats["true_positive"] + framework.stats["true_negative"]) / framework.stats["total"] * 100 if framework.stats["total"] > 0 else 0,
            "stats": framework.stats,
        }

        self.results["golden_dataset"] = result
        return result

    async def run_rule_simulator_evaluation(self, num_additional_tests: int = 20) -> Dict[str, Any]:
        """运行规则模拟器评估"""
        print("\n" + "=" * 80)
        print("运行规则模拟器评估")
        print("=" * 80)

        framework = EvaluationFrameworkV2(
            simulator=None,  # 使用默认规则模拟器
            use_tts=False
        )

        await framework.run_full_evaluation(
            num_additional_tests=num_additional_tests,
            run_golden_cases=True
        )

        # 保存结果
        result = {
            "total": framework.stats["total"],
            "success": framework.stats["success"],
            "failed": framework.stats["failed"],
            "success_rate": framework.stats["success"] / framework.stats["total"] * 100 if framework.stats["total"] > 0 else 0,
            "stats": framework.stats,
        }

        self.results["rule_simulator"] = result
        return result

    def generate_summary_report(self) -> str:
        """生成汇总报告"""
        report = f"""# 智能催收对话系统评估汇总报告

**评估时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 总体结果

"""

        if "golden_dataset" in self.results:
            res = self.results["golden_dataset"]
            report += f"""### 黄金数据集评估
| 指标 | 数值 |
|-----|------|
| 总测试数 | {res['total']} |
| 成功 | {res['success']} |
| 失败 | {res['failed']} |
| 成功率 | {res['success_rate']:.1f}% |
| 准确率 | {res['accuracy']:.1f}% |
| 真阳性 | {res['true_positive']} |
| 真阴性 | {res['true_negative']} |
| 假阳性 | {res['false_positive']} |
| 假阴性 | {res['false_negative']} |

"""

        if "rule_simulator" in self.results:
            res = self.results["rule_simulator"]
            report += f"""### 规则模拟器评估
| 指标 | 数值 |
|-----|------|
| 总测试数 | {res['total']} |
| 成功 | {res['success']} |
| 失败 | {res['failed']} |
| 成功率 | {res['success_rate']:.1f}% |

"""

        report += """---

## 评估说明

1. 黄金数据集评估基于195个真实催收对话案例，覆盖各种常见场景和边缘情况
2. 规则模拟器评估基于预设的客户行为模型，测试系统在各种模拟场景下的表现
3. 成功率定义为系统成功获取用户明确还款时间承诺的对话比例
4. 准确率定义为系统预测结果与人工标注结果一致的比例

"""

        # 保存报告
        report_file = self.output_dir / f"evaluation_summary_{self.timestamp}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n汇总报告已保存到: {report_file}")
        return str(report_file)

    def save_full_results(self):
        """保存完整的评估结果"""
        result_file = self.output_dir / f"evaluation_full_results_{self.timestamp}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"完整结果已保存到: {result_file}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="一键评估流水线")
    parser.add_argument("--mode", choices=["all", "golden", "simulator"], default="all", help="评估模式")
    parser.add_argument("--case-ids", type=str, nargs="+", help="指定要运行的黄金数据集案例ID")
    parser.add_argument("--priority-threshold", type=float, help="黄金数据集优先级阈值")
    parser.add_argument("--num-tests", type=int, default=20, help="模拟器评估的测试数量")

    args = parser.parse_args()

    pipeline = EvaluationPipeline()

    if args.mode in ["all", "golden"]:
        await pipeline.run_golden_dataset_evaluation(
            case_ids=args.case_ids,
            priority_threshold=args.priority_threshold
        )

    if args.mode in ["all", "simulator"]:
        await pipeline.run_rule_simulator_evaluation(
            num_additional_tests=args.num_tests
        )

    # 生成报告
    report_file = pipeline.generate_summary_report()
    pipeline.save_full_results()

    # 打印最终结果
    print("\n" + "=" * 80)
    print("评估完成！")
    print("=" * 80)

    if "golden_dataset" in pipeline.results:
        res = pipeline.results["golden_dataset"]
        print(f"黄金数据集成功率: {res['success_rate']:.1f}% ({res['success']}/{res['total']})")

    if "rule_simulator" in pipeline.results:
        res = pipeline.results["rule_simulator"]
        print(f"规则模拟器成功率: {res['success_rate']:.1f}% ({res['success']}/{res['total']})")

    print(f"\n报告已保存到: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
