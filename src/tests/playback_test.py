#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话回放测试引擎
加载黄金测试数据集，自动回放对话，对比机器人回复与标注结果，生成测试报告
"""
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot
from core.compliance_checker import get_compliance_checker

@dataclass
class TestResult:
    """单个测试用例的结果"""
    case_id: str
    file_name: str
    passed: bool
    total_turns: int
    correct_turns: int
    accuracy: float
    compliance_passed: bool
    violations: List[Dict]
    failed_turns: List[Dict]
    details: Dict

class PlaybackTester:
    """回放测试器"""

    def __init__(self, gold_dataset_dir: str = "data/raw/gold_dataset/"):
        self.gold_dir = Path(gold_dataset_dir)
        self.compliance_checker = get_compliance_checker()
        self.test_cases = self._load_gold_cases()

    def _load_gold_cases(self) -> List[Dict]:
        """加载所有黄金测试用例"""
        cases = []
        if not self.gold_dir.exists():
            print(f"警告：黄金数据集目录 {self.gold_dir} 不存在，请先完成标注")
            return cases

        for file_path in self.gold_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    case = json.load(f)
                    case["file_name"] = file_path.name
                    cases.append(case)
            except Exception as e:
                print(f"加载测试用例 {file_path} 失败: {e}")

        print(f"成功加载 {len(cases)} 个黄金测试用例")
        return cases

    async def run_single_test(self, test_case: Dict) -> TestResult:
        """运行单个测试用例"""
        case_id = test_case["case_id"]
        file_name = test_case["file_name"]
        dialogue = test_case["dialogue"]
        collection_stage = test_case["basic_info"]["collection_stage"]

        print(f"运行测试用例: {case_id} - {file_name}")

        # 初始化机器人
        bot = CollectionChatBot(chat_group=collection_stage)
        bot_state = ChatState()

        total_turns = 0
        correct_turns = 0
        failed_turns = []
        all_violations = []

        # 对话历史
        history = []

        for i, turn in enumerate(dialogue):
            if turn["speaker"] == "customer":
                # 用户轮次，保存用户输入，准备发送给机器人
                user_input = turn["text"]
                expected_intent = turn["user_intent"]
                history.append({"role": "user", "content": user_input})
                continue

            if turn["speaker"] == "agent":
                # 坐席轮次，这里是预期的回复，我们需要让机器人生成回复并对比
                total_turns += 1
                expected_response = turn["text"]
                expected_correct = turn["is_correct"]
                expected_stage = turn["stage"]

                # 获取上一条用户输入
                if not history or history[-1]["role"] != "user":
                    # 没有找到对应的用户输入，跳过这个轮次
                    continue

                user_input = history[-1]["content"]

                # 让机器人生成回复
                try:
                    actual_response, updated_state = await bot.process(user_input, bot_state)
                    bot_state = updated_state
                except Exception as e:
                    print(f"机器人处理失败: {e}")
                    failed_turns.append({
                        "turn_number": turn["turn_number"],
                        "user_input": user_input,
                        "expected_response": expected_response,
                        "actual_response": "",
                        "error": str(e),
                        "expected_stage": expected_stage,
                        "actual_stage": None
                    })
                    continue

                # 保存机器人回复到历史
                history.append({"role": "assistant", "content": actual_response})

                # 1. 合规检查
                compliance_passed, violations = self.compliance_checker.check(actual_response)
                if not compliance_passed:
                    all_violations.extend(violations)

                # 2. 回复正确性检查
                # 首先检查是否符合预期的正确性要求
                if expected_correct:
                    # 预期这个回复是正确的，我们需要检查机器人的回复是否也正确
                    # 这里用相似度比较，或者检查关键信息是否存在
                    is_correct, reason = self._check_response_correctness(
                        actual_response, expected_response, expected_stage
                    )
                else:
                    # 预期这个回复是不正确的，我们需要检查机器人是否没有犯同样的错误
                    # 即机器人的回复应该是正确的，不应该包含标注的错误内容
                    is_correct, reason = self._check_response_not_incorrect(
                        actual_response, expected_response, turn["standard_response"]
                    )

                if is_correct:
                    correct_turns += 1
                else:
                    failed_turns.append({
                        "turn_number": turn["turn_number"],
                        "user_input": user_input,
                        "expected_response": expected_response,
                        "actual_response": actual_response,
                        "reason": reason,
                        "expected_stage": expected_stage,
                        "actual_stage": bot_state.current_stage if hasattr(bot_state, 'current_stage') else None
                    })

        # 计算准确率
        accuracy = correct_turns / total_turns if total_turns > 0 else 0.0

        # 整体是否通过：准确率≥90% 且 无高风险违规
        overall_passed = accuracy >= 0.9 and all(v["severity"] != "high" for v in all_violations)

        return TestResult(
            case_id=case_id,
            file_name=file_name,
            passed=overall_passed,
            total_turns=total_turns,
            correct_turns=correct_turns,
            accuracy=accuracy,
            compliance_passed=len(all_violations) == 0,
            violations=all_violations,
            failed_turns=failed_turns,
            details={
                "collection_stage": collection_stage,
                "call_result": test_case["basic_info"]["call_result"],
                "user_persona": test_case["user_profile"]["persona"],
                "resistance_level": test_case["user_profile"]["resistance_level"]
            }
        )

    def _check_response_correctness(self, actual: str, expected: str, stage: str) -> Tuple[bool, str]:
        """检查机器人回复是否正确（当预期回复是正确的时候）"""
        actual_lower = actual.lower().strip()
        expected_lower = expected.lower().strip()

        if not actual_lower:
            return False, "机器人回复为空"

        # 检查关键信息是否匹配
        # 1. 问候阶段
        if stage == "greeting":
            greeting_keywords = ["halo", "selamat pagi", "selamat siang", "selamat sore", "pak", "ibu"]
            has_greeting = any(kw in actual_lower for kw in greeting_keywords)
            if has_greeting:
                return True, "问候语正确"
            else:
                return False, "缺少问候语或称呼"

        # 2. 身份确认阶段
        if stage == "identity":
            identity_keywords = ["nama saya", "dari", "extra", "apakah benar", "bapak", "ibu"]
            has_identity = any(kw in actual_lower for kw in identity_keywords)
            if has_identity:
                return True, "身份介绍正确"
            else:
                return False, "缺少自我介绍或身份确认"

        # 3. 说明来意阶段
        if stage == "purpose":
            purpose_keywords = ["tagihan", "pinjaman", "hutang", "jatuh tempo", "pembayaran"]
            has_purpose = any(kw in actual_lower for kw in purpose_keywords)
            if has_purpose:
                return True, "来意说明正确"
            else:
                return False, "没有说明催收来意"

        # 4. 询问还款时间阶段
        if stage == "ask_time":
            ask_time_keywords = ["kapan", "tanggal berapa", "jam berapa", "bisa bayar", "kapan bisa"]
            has_ask_time = any(kw in actual_lower for kw in ask_time_keywords)
            if has_ask_time:
                return True, "询问还款时间正确"
            else:
                return False, "没有询问还款时间"

        # 5. 施压阶段
        if stage == "push":
            push_keywords = ["segera", "hari ini", "batas waktu", "denda", "bunga", "konsekuensi"]
            has_push = any(kw in actual_lower for kw in push_keywords)
            if has_push:
                return True, "施压内容正确"
            else:
                return False, "没有包含施压相关内容"

        # 6. 协商阶段
        if stage == "negotiate":
            # 协商阶段需要表现出理解和愿意沟通
            negotiate_keywords = ["bisa", "coba", "bagaimana", "mengerti", "paham", "kita bicarakan"]
            has_negotiate = any(kw in actual_lower for kw in negotiate_keywords)
            if has_negotiate and len(actual_lower) > 5:
                return True, "协商应对正确"
            else:
                return False, "协商应对不当，缺少沟通意愿的表达"

        # 7. 确认承诺阶段
        if stage == "commit":
            commit_keywords = ["oke", "ya", "baik", "janji", "pasti", "terima kasih", "kami tunggu"]
            has_commit = any(kw in actual_lower for kw in commit_keywords)
            if has_commit:
                return True, "承诺确认正确"
            else:
                return False, "没有确认用户的还款承诺"

        # 8. 结束阶段
        if stage == "close":
            close_keywords = ["terima kasih", "selamat tinggal", "saya tutup telepon", "sampai jumpa"]
            has_close = any(kw in actual_lower for kw in close_keywords)
            if has_close:
                return True, "结束语正确"
            else:
                return False, "缺少合适的结束语"

        # 默认用相似度比较
        # 计算简单的词重叠率
        actual_words = set(actual_lower.split())
        expected_words = set(expected_lower.split())
        if not expected_words:
            return True, "预期回复为空，跳过检查"

        overlap = len(actual_words & expected_words) / len(expected_words)
        if overlap >= 0.3:  # 30%以上的词重叠就算正确
            return True, f"回复相似度符合要求 ({overlap:.1%})"
        else:
            return False, f"回复相似度不足 ({overlap:.1%})"

    def _check_response_not_incorrect(self, actual: str, incorrect_expected: str, standard_response: str) -> Tuple[bool, str]:
        """检查机器人回复是否没有犯标注的错误（当预期回复是不正确的时候）"""
        actual_lower = actual.lower().strip()
        incorrect_lower = incorrect_expected.lower().strip()
        standard_lower = standard_response.lower().strip()

        if not actual_lower:
            return False, "机器人回复为空"

        # 首先检查是否包含错误回复的关键内容
        incorrect_words = set(incorrect_lower.split())
        actual_words = set(actual_lower.split())
        overlap = len(actual_words & incorrect_words) / len(incorrect_words) if incorrect_words else 0

        if overlap >= 0.5:
            return False, f"机器人回复包含了标注的错误内容 (相似度: {overlap:.1%})"

        # 然后检查是否与标准回复有一定相似度
        if standard_lower:
            standard_words = set(standard_lower.split())
            standard_overlap = len(actual_words & standard_words) / len(standard_words) if standard_words else 0
            if standard_overlap >= 0.2:
                return True, f"机器人回复正确，符合标准回复要求 (相似度: {standard_overlap:.1%})"
            else:
                # 即使和标准回复不太像，只要没有错误内容也算对
                return True, "机器人回复没有包含错误内容"
        else:
            return True, "没有提供标准回复，机器人回复没有明显错误"

    async def run_all_tests(self) -> Tuple[List[TestResult], Dict]:
        """运行所有测试用例"""
        if not self.test_cases:
            print("没有可用的测试用例，请先标注黄金数据集")
            return [], {}

        print(f"开始运行 {len(self.test_cases)} 个黄金测试用例...")
        results = []

        for case in self.test_cases:
            result = await self.run_single_test(case)
            results.append(result)

        # 统计整体结果
        total_cases = len(results)
        passed_cases = sum(1 for r in results if r.passed)
        pass_rate = passed_cases / total_cases if total_cases > 0 else 0.0

        total_turns = sum(r.total_turns for r in results)
        correct_turns = sum(r.correct_turns for r in results)
        overall_accuracy = correct_turns / total_turns if total_turns > 0 else 0.0

        # 统计合规情况
        compliance_passed_cases = sum(1 for r in results if r.compliance_passed)
        total_violations = sum(len(r.violations) for r in results)
        high_risk_violations = sum(1 for r in results for v in r.violations if v["severity"] == "high")

        # 按维度统计
        stage_stats = {}
        persona_stats = {}
        resistance_stats = {}

        for result in results:
            # 按催收阶段统计
            stage = result.details["collection_stage"]
            if stage not in stage_stats:
                stage_stats[stage] = {"total": 0, "passed": 0}
            stage_stats[stage]["total"] += 1
            if result.passed:
                stage_stats[stage]["passed"] += 1

            # 按用户类型统计
            persona = result.details["user_persona"]
            if persona not in persona_stats:
                persona_stats[persona] = {"total": 0, "passed": 0}
            persona_stats[persona]["total"] += 1
            if result.passed:
                persona_stats[persona]["passed"] += 1

            # 按抗拒程度统计
            resistance = result.details["resistance_level"]
            if resistance not in resistance_stats:
                resistance_stats[resistance] = {"total": 0, "passed": 0}
            resistance_stats[resistance]["total"] += 1
            if result.passed:
                resistance_stats[resistance]["passed"] += 1

        summary = {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": total_cases - passed_cases,
            "pass_rate": round(pass_rate, 4),
            "total_turns": total_turns,
            "correct_turns": correct_turns,
            "overall_accuracy": round(overall_accuracy, 4),
            "compliance_passed_cases": compliance_passed_cases,
            "total_violations": total_violations,
            "high_risk_violations": high_risk_violations,
            "stage_stats": stage_stats,
            "persona_stats": persona_stats,
            "resistance_stats": resistance_stats,
            "test_time": datetime.now().isoformat()
        }

        return results, summary

    def generate_report(self, results: List[TestResult], summary: Dict, output_dir: str = "data/outputs/playback_reports/") -> str:
        """生成测试报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 生成JSON报告
        json_file = output_path / f"playback_test_{timestamp}.json"
        report_data = {
            "summary": summary,
            "results": [
                {
                    "case_id": r.case_id,
                    "file_name": r.file_name,
                    "passed": r.passed,
                    "total_turns": r.total_turns,
                    "correct_turns": r.correct_turns,
                    "accuracy": r.accuracy,
                    "compliance_passed": r.compliance_passed,
                    "violations": r.violations,
                    "failed_turns": r.failed_turns,
                    "details": r.details
                }
                for r in results
            ]
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 生成Markdown报告
        md_file = output_path / f"playback_test_{timestamp}.md"

        md_content = f"""# 对话回放测试报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 总体结果
| 指标 | 数值 |
|------|------|
| 总测试用例数 | {summary['total_cases']} |
| 通过用例数 | {summary['passed_cases']} |
| 失败用例数 | {summary['failed_cases']} |
| 用例通过率 | {summary['pass_rate']*100:.1f}% |
| 总对话轮数 | {summary['total_turns']} |
| 正确回复轮数 | {summary['correct_turns']} |
| 整体回复准确率 | {summary['overall_accuracy']*100:.1f}% |
| 合规通过用例数 | {summary['compliance_passed_cases']} |
| 总违规数 | {summary['total_violations']} |
| 高风险违规数 | {summary['high_risk_violations']} |

## 📈 按催收阶段统计
| 阶段 | 用例数 | 通过数 | 通过率 |
|------|--------|--------|--------|
"""
        for stage, stats in summary["stage_stats"].items():
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            md_content += f"| {stage} | {stats['total']} | {stats['passed']} | {pass_rate:.1f}% |\n"

        md_content += """
## 👤 按用户类型统计
| 用户类型 | 用例数 | 通过数 | 通过率 |
|----------|--------|--------|--------|
"""
        for persona, stats in sorted(summary["persona_stats"].items()):
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            md_content += f"| {persona} | {stats['total']} | {stats['passed']} | {pass_rate:.1f}% |\n"

        md_content += """
## ⚔️ 按抗拒程度统计
| 抗拒程度 | 用例数 | 通过数 | 通过率 |
|----------|--------|--------|--------|
"""
        for resistance, stats in sorted(summary["resistance_stats"].items()):
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            md_content += f"| {resistance} | {stats['total']} | {stats['passed']} | {pass_rate:.1f}% |\n"

        md_content += """
## ❌ 失败用例详情
| 用例ID | 文件名称 | 通过率 | 失败原因 |
|--------|----------|--------|----------|
"""
        for result in results:
            if not result.passed:
                reasons = []
                if result.accuracy < 0.9:
                    reasons.append(f"回复准确率不足: {result.accuracy*100:.1f}%")
                if any(v["severity"] == "high" for v in result.violations):
                    reasons.append("存在高风险合规问题")
                md_content += f"| {result.case_id} | {result.file_name} | {result.accuracy*100:.1f}% | {', '.join(reasons)} |\n"

        md_content += """
## 🚨 违规详情
| 用例ID | 违规内容 | 严重程度 | 建议 |
|--------|----------|----------|------|
"""
        for result in results:
            for violation in result.violations:
                md_content += f"| {result.case_id} | {violation['description']} | {violation['severity']} | {violation['suggestion']} |\n"

        md_content += """
## 🎯 测试说明
1. 用例通过标准：回复准确率≥90% 且 无高风险合规违规
2. 回复准确率：正确回复的轮数占总坐席轮数的比例
3. 合规检查基于内置的15条催收合规规则，覆盖所有高风险场景
4. 测试结果可用于评估机器人优化效果，对比不同版本的性能
"""

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n测试报告已生成:")
        print(f"  - JSON报告: {json_file}")
        print(f"  - Markdown报告: {md_file}")

        return str(md_file)

    def print_summary(self, summary: Dict):
        """打印测试结果摘要"""
        print("\n" + "="*70)
        print("回放测试结果汇总")
        print("="*70)
        print(f"总测试用例数: {summary['total_cases']}")
        print(f"通过: {summary['passed_cases']}")
        print(f"失败: {summary['failed_cases']}")
        print(f"用例通过率: {summary['pass_rate']*100:.1f}%")
        print(f"整体回复准确率: {summary['overall_accuracy']*100:.1f}%")
        print(f"高风险违规数: {summary['high_risk_violations']}")

        if summary['high_risk_violations'] > 0:
            print("\n⚠️  警告：存在高风险合规问题，请优先修复！")

        if summary['pass_rate'] >= 0.9:
            print("\n✅ 测试通过！整体表现符合预期")
        else:
            print(f"\n❌ 测试未通过！需要优化，目标通过率≥90%，当前{summary['pass_rate']*100:.1f}%")

async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="对话回放测试工具")
    parser.add_argument("--case", help="运行单个测试用例，指定文件名")
    parser.add_argument("--generate-report", action="store_true", default=True, help="生成测试报告")
    parser.add_argument("--output-dir", default="data/outputs/playback_reports/", help="报告输出目录")

    args = parser.parse_args()

    tester = PlaybackTester()

    if not tester.test_cases:
        print("请先完成黄金数据集的标注工作")
        return

    if args.case:
        # 运行单个测试用例
        case = next((c for c in tester.test_cases if c["file_name"] == args.case), None)
        if not case:
            print(f"找不到测试用例: {args.case}")
            return

        result = await tester.run_single_test(case)
        print(f"\n测试结果: {'通过' if result.passed else '失败'}")
        print(f"回复准确率: {result.accuracy*100:.1f}%")
        print(f"合规检查: {'通过' if result.compliance_passed else '失败'}")

        if result.violations:
            print("\n违规内容:")
            for v in result.violations:
                print(f"  - [{v['severity']}] {v['description']}: {v['suggestion']}")

        if result.failed_turns:
            print("\n失败轮次:")
            for turn in result.failed_turns:
                print(f"  轮次 {turn['turn_number']}:")
                print(f"    用户输入: {turn['user_input']}")
                print(f"    预期回复: {turn['expected_response']}")
                print(f"    实际回复: {turn['actual_response']}")
                print(f"    失败原因: {turn['reason']}")
        return

    # 运行所有测试
    results, summary = await tester.run_all_tests()

    # 打印摘要
    tester.print_summary(summary)

    # 生成报告
    if args.generate_report:
        tester.generate_report(results, summary, args.output_dir)

if __name__ == "__main__":
    asyncio.run(main())
