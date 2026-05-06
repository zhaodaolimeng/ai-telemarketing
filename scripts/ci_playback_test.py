#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI/CD集成的回放测试脚本
在代码提交或合并前自动运行黄金测试用例，低于阈值则失败
"""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tests.playback_test import PlaybackTester

# 测试通过阈值
PASS_RATE_THRESHOLD = 0.9  # 用例通过率≥90%
ACCURACY_THRESHOLD = 0.85  # 整体回复准确率≥85%
ALLOW_HIGH_RISK_VIOLATIONS = False  # 是否允许高风险违规

async def main():
    print("="*70)
    print("CI 回放测试启动")
    print("="*70)

    # 检查黄金数据集是否存在
    gold_dir = Path("data/gold_dataset/")
    if not gold_dir.exists() or len(list(gold_dir.glob("*.json"))) == 0:
        print("⚠️  黄金数据集不存在或为空，跳过回放测试")
        # 可选：在CI中可以配置为失败，确保必须有数据集
        # sys.exit(1)
        return 0

    tester = PlaybackTester()

    if len(tester.test_cases) == 0:
        print("⚠️  没有可用的测试用例，跳过回放测试")
        return 0

    print(f"加载到 {len(tester.test_cases)} 个黄金测试用例")
    print(f"测试阈值: 通过率≥{PASS_RATE_THRESHOLD*100}%, 准确率≥{ACCURACY_THRESHOLD*100}%, 高风险违规: {'允许' if ALLOW_HIGH_RISK_VIOLATIONS else '禁止'}")

    # 运行所有测试
    results, summary = await tester.run_all_tests()

    # 打印结果
    print("\n" + "="*70)
    print("测试结果")
    print("="*70)
    print(f"用例通过率: {summary['pass_rate']*100:.1f}% (阈值: {PASS_RATE_THRESHOLD*100}%)")
    print(f"整体准确率: {summary['overall_accuracy']*100:.1f}% (阈值: {ACCURACY_THRESHOLD*100}%)")
    print(f"高风险违规数: {summary['high_risk_violations']} (允许: {'是' if ALLOW_HIGH_RISK_VIOLATIONS else '否'})")

    # 检查是否通过
    passed = True
    errors = []

    if summary['pass_rate'] < PASS_RATE_THRESHOLD:
        passed = False
        errors.append(f"用例通过率低于阈值: {summary['pass_rate']*100:.1f}% < {PASS_RATE_THRESHOLD*100}%")

    if summary['overall_accuracy'] < ACCURACY_THRESHOLD:
        passed = False
        errors.append(f"整体准确率低于阈值: {summary['overall_accuracy']*100:.1f}% < {ACCURACY_THRESHOLD*100}%")

    if not ALLOW_HIGH_RISK_VIOLATIONS and summary['high_risk_violations'] > 0:
        passed = False
        errors.append(f"存在高风险违规: {summary['high_risk_violations']} 个")

    if passed:
        print("\n✅ 回放测试通过！")
        return 0
    else:
        print("\n❌ 回放测试失败！")
        print("错误详情:")
        for error in errors:
            print(f"  - {error}")

        # 打印失败用例
        failed_cases = [r for r in results if not r.passed]
        if failed_cases:
            print("\n失败用例列表:")
            for case in failed_cases:
                print(f"  - {case.case_id}: 准确率 {case.accuracy*100:.1f}%, 合规 {'通过' if case.compliance_passed else '失败'}")

        # 生成报告
        try:
            report_path = tester.generate_report(results, summary, output_dir="data/ci_reports/")
            print(f"\n详细报告已生成: {report_path}")
        except Exception as e:
            print(f"\n生成报告失败: {e}")

        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
