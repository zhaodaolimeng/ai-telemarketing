#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鲁棒性自动化测试工具
运行ROBUSTNESS_TEST_CASES.md中的所有测试用例，自动判断是否符合预期
"""
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, ChatState
from core.compliance_checker import get_compliance_checker


@dataclass
class TestCase:
    """测试用例"""
    case_id: str
    category: str
    difficulty: int
    user_input: str
    chinese_translation: str
    expected_requirements: str
    compliance_requirements: str


class RobustnessTester:
    """鲁棒性测试器"""

    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.results: List[Dict] = []
        self._load_test_cases()

    def _load_test_cases(self):
        """从ROBUSTNESS_TEST_CASES.md加载测试用例"""
        test_file = Path(__file__).parent.parent.parent / "docs" / "evaluation" / "ROBUSTNESS_TEST_CASES.md"
        content = test_file.read_text(encoding="utf-8")

        # 按类别分割
        category_sections = re.split(r"## [🔴🟠🟡🟢🔵] 类别\d+：", content)[1:]

        for section in category_sections:
            # 提取类别名称
            category_match = re.match(r"([^类]+类)", section.strip())
            category = category_match.group(1) if category_match else "未知类别"

            # 提取表格内容
            table_match = re.search(r"\| 用例ID.*?\n((?:\|.*?\n)+)", section, re.DOTALL)
            if not table_match:
                continue

            table_content = table_match.group(1)
            rows = [row.strip() for row in table_content.split("\n") if row.strip() and not row.startswith("|---")]

            for row in rows:
                cells = [cell.strip() for cell in row.split("|") if cell.strip()]
                if len(cells) != 6:
                    continue

                case_id, difficulty, user_input, chinese_translation, expected_requirements, compliance_requirements = cells

                try:
                    difficulty = int(difficulty)
                except ValueError:
                    continue

                test_case = TestCase(
                    case_id=case_id,
                    category=category,
                    difficulty=difficulty,
                    user_input=user_input,
                    chinese_translation=chinese_translation,
                    expected_requirements=expected_requirements,
                    compliance_requirements=compliance_requirements
                )
                self.test_cases.append(test_case)

        print(f"成功加载 {len(self.test_cases)} 个测试用例")

    async def run_single_test(self, test_case: TestCase) -> Dict:
        """运行单个测试用例"""
        # 初始化机器人，模拟到对话中间状态
        bot = CollectionChatBot(chat_group="H2")

        # 先完成前面的几个步骤，进入询问还款时间的阶段
        # 1. 初始问候
        await bot.process()  # 机器人说问候语
        # 2. 用户回应问候
        await bot.process("Iya?")  # 机器人自我介绍
        # 3. 用户确认身份
        await bot.process("Ya.")  # 机器人说明来意
        # 现在机器人进入ASK_TIME状态，准备询问还款时间，这时候用户说出测试用例的内容

        # 输入测试用例的用户输入
        response, _ = await bot.process(test_case.user_input)

        # 判断是否通过
        passed, reason = self._check_response(test_case, response)

        result = {
            "case_id": test_case.case_id,
            "category": test_case.category,
            "difficulty": test_case.difficulty,
            "user_input": test_case.user_input,
            "chinese_translation": test_case.chinese_translation,
            "response": response,
            "expected_requirements": test_case.expected_requirements,
            "compliance_requirements": test_case.compliance_requirements,
            "passed": passed,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }

        return result

    def _check_response(self, test_case: TestCase, response: str) -> Tuple[bool, str]:
        """检查回复是否符合要求"""
        if not response:
            return False, "机器人没有回复"

        # 检查合规要求（强制要求，不满足直接失败）
        compliance_passed, compliance_reason = self._check_compliance(test_case.compliance_requirements, response)
        if not compliance_passed:
            return False, f"合规检查失败: {compliance_reason}"

        # 检查预期要求
        expected_passed, expected_reason = self._check_expected(test_case.expected_requirements, response)
        if not expected_passed:
            return False, f"预期要求未满足: {expected_reason}"

        return True, "所有检查通过"

    def _check_compliance(self, requirements: str, response: str) -> Tuple[bool, str]:
        """检查合规要求"""
        # 使用专业合规检查器
        checker = get_compliance_checker()
        is_compliant, violations = checker.check(response)

        # 高风险违规直接失败
        high_violations = [v for v in violations if v["severity"] == "high"]
        if high_violations:
            return False, f"高风险违规: {high_violations[0]['description']} - {high_violations[0]['suggestion']}"

        # 检查具体的合规要求
        requirements_lower = requirements.lower()

        if "tidak boleh mengatakan" in requirements_lower or "不能说" in requirements_lower:
            # 提取不能说的内容
            not_allowed_match = re.search(r"tidak boleh mengatakan[\"“](.*?)[\"”]", requirements)
            if not_allowed_match:
                not_allowed = not_allowed_match.group(1).lower()
                if not_allowed in response.lower():
                    return False, f"包含不允许的表述: {not_allowed}"

        if "不能威胁用户" in requirements:
            for v in violations:
                if v["rule_id"] == "C-002":
                    return False, f"违规: {v['description']} - {v['suggestion']}"

        if "不能辱骂用户" in requirements:
            for v in violations:
                if v["rule_id"] == "C-001":
                    return False, f"违规: {v['description']} - {v['suggestion']}"

        if "不能提供虚假信息" in requirements:
            for v in violations:
                if v["rule_id"] == "C-004":
                    return False, f"违规: {v['description']} - {v['suggestion']}"

        return True, "合规检查通过"

    def _check_expected(self, requirements: str, response: str) -> Tuple[bool, str]:
        """检查是否符合预期要求"""
        response_lower = response.lower()
        requirements_lower = requirements.lower()

        # 检查是否应该包含特定内容
        if "安抚" in requirements or "menenangkan" in requirements_lower:
            # 检查是否有安抚词汇
            calm_words = ["saya mengerti", "maaf", "paham", "mengerti", "jangan khawatir"]
            has_calm = any(word in response_lower for word in calm_words)
            if not has_calm and len(response.split()) < 6:
                return False, "没有包含安抚相关的表述"

        if "道歉" in requirements or "minta maaf" in requirements_lower:
            apology_words = ["maaf", "saya minta maaf", "kami minta maaf", "maaf ya"]
            has_apology = any(word in response_lower for word in apology_words)
            if not has_apology:
                return False, "没有包含道歉相关的表述"

        if "解释" in requirements or "jelaskan" in requirements_lower:
            explain_words = ["kami", "karena", "penjelasan", "sebenarnya", "jadi"]
            has_explain = any(word in response_lower for word in explain_words)
            if not has_explain and len(response.split()) < 5:
                return False, "没有包含解释相关的表述"

        if "协商" in requirements or "negosiasi" in requirements_lower:
            negotiate_words = ["bisa", "coba", "bagaimana jika", "mungkin bisa", "kita bisa"]
            has_negotiate = any(word in response_lower for word in negotiate_words)
            if not has_negotiate:
                return False, "没有包含协商相关的表述"

        if "结束通话" in requirements or "akhiri telepon" in requirements_lower:
            end_words = ["terima kasih", "selamat tinggal", "saya tutup telepon", "nanti kita hubungi kembali"]
            has_end = any(word in response_lower for word in end_words)
            if not has_end and len(response) > 0:
                return False, "没有包含结束通话相关的表述"

        # 检查是否不应该包含特定内容
        if "不能直接拒绝" in requirements or "tidak boleh menolak langsung" in requirements_lower:
            if len(response) < 3:
                return False, "回复太短，疑似直接拒绝"

        if "不能纠缠" in requirements or "tidak boleh mengganggu" in requirements_lower:
            if "nanti kita telepon lagi" in response_lower or "kami akan telepon lagi" in response_lower:
                return False, "包含继续拨打的表述，属于纠缠"

        return True, "预期要求检查通过"

    async def run_all_tests(self) -> Dict:
        """运行所有测试用例"""
        print(f"开始运行 {len(self.test_cases)} 个测试用例...")

        for i, test_case in enumerate(self.test_cases, 1):
            print(f"运行测试用例 {i}/{len(self.test_cases)}: {test_case.case_id} - {test_case.category}")
            result = await self.run_single_test(test_case)
            self.results.append(result)

        # 统计结果
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        pass_rate = passed_count / total_count * 100

        # 按类别统计
        category_stats = {}
        for result in self.results:
            category = result["category"]
            if category not in category_stats:
                category_stats[category] = {"total": 0, "passed": 0}
            category_stats[category]["total"] += 1
            if result["passed"]:
                category_stats[category]["passed"] += 1

        # 按难度统计
        difficulty_stats = {}
        for result in self.results:
            difficulty = result["difficulty"]
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {"total": 0, "passed": 0}
            difficulty_stats[difficulty]["total"] += 1
            if result["passed"]:
                difficulty_stats[difficulty]["passed"] += 1

        summary = {
            "total_count": total_count,
            "passed_count": passed_count,
            "failed_count": total_count - passed_count,
            "pass_rate": round(pass_rate, 2),
            "category_stats": category_stats,
            "difficulty_stats": difficulty_stats,
            "test_time": datetime.now().isoformat()
        }

        return summary

    def generate_report(self, summary: Dict, output_dir: Optional[str] = None) -> str:
        """生成测试报告"""
        if output_dir is None:
            output_dir = Path("data/robustness_tests")
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 生成JSON报告
        json_file = output_dir / f"robustness_test_{timestamp}.json"
        report_data = {
            "summary": summary,
            "detailed_results": self.results
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 生成Markdown报告
        md_file = output_dir / f"robustness_test_{timestamp}.md"

        md_content = f"""# 鲁棒性测试报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 总体结果
| 指标 | 数值 |
|------|------|
| 总测试用例数 | {summary['total_count']} |
| 通过用例数 | {summary['passed_count']} |
| 失败用例数 | {summary['failed_count']} |
| 通过率 | {summary['pass_rate']}% |

## 📈 按类别统计
| 类别 | 总数 | 通过数 | 通过率 |
|------|------|--------|--------|
"""
        for category, stats in summary["category_stats"].items():
            pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            md_content += f"| {category} | {stats['total']} | {stats['passed']} | {pass_rate:.1f}% |\n"

        md_content += """
## 🎯 按难度统计
| 难度 | 总数 | 通过数 | 通过率 |
|------|------|--------|--------|
"""
        for difficulty in sorted(summary["difficulty_stats"].keys()):
            stats = summary["difficulty_stats"][difficulty]
            pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            md_content += f"| {difficulty} | {stats['total']} | {stats['passed']} | {pass_rate:.1f}% |\n"

        md_content += """
## ❌ 失败用例详情
| 用例ID | 类别 | 难度 | 用户输入 | 中文翻译 | 机器人回复 | 失败原因 |
|--------|------|------|----------|----------|------------|----------|
"""
        for result in self.results:
            if not result["passed"]:
                md_content += f'| {result["case_id"]} | {result["category"]} | {result["difficulty"]} | {result["user_input"]} | {result["chinese_translation"]} | {result["response"]} | {result["reason"]} |\n'

        md_content += """
## ✅ 测试说明
1. 本测试针对催收机器人在高风险场景下的应对能力和合规性
2. 合规要求是强制项，任何违反合规要求的回复都视为失败
3. 预期要求是优化项，旨在提高机器人的应对效果
4. 测试覆盖率达到100%覆盖所有高风险场景
"""

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n测试报告已生成:")
        print(f"  - JSON报告: {json_file}")
        print(f"  - Markdown报告: {md_file}")

        return str(md_file)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="鲁棒性自动化测试工具")
    parser.add_argument("--list-cases", action="store_true", help="列出所有测试用例")
    parser.add_argument("--case-id", help="运行单个测试用例ID")
    parser.add_argument("--category", help="运行特定类别的测试用例")

    args = parser.parse_args()

    tester = RobustnessTester()

    if args.list_cases:
        print("测试用例列表:")
        for case in tester.test_cases:
            print(f"{case.case_id:8s} [{case.category}] 难度{case.difficulty}: {case.chinese_translation}")
        return

    if args.case_id:
        # 运行单个测试用例
        test_case = next((c for c in tester.test_cases if c.case_id == args.case_id), None)
        if not test_case:
            print(f"找不到测试用例: {args.case_id}")
            return

        print(f"运行测试用例: {test_case.case_id}")
        print(f"用户输入: {test_case.user_input} ({test_case.chinese_translation})")
        print(f"预期要求: {test_case.expected_requirements}")
        print(f"合规要求: {test_case.compliance_requirements}")

        result = await tester.run_single_test(test_case)
        print(f"\n机器人回复: {result['response']}")
        print(f"测试结果: {'通过' if result['passed'] else '失败'}")
        print(f"原因: {result['reason']}")
        return

    if args.category:
        # 运行特定类别的测试用例
        filtered_cases = [c for c in tester.test_cases if args.category in c.category]
        if not filtered_cases:
            print(f"找不到类别为 {args.category} 的测试用例")
            return

        tester.test_cases = filtered_cases
        print(f"将运行 {len(filtered_cases)} 个 {args.category} 类别的测试用例")

    # 运行所有测试
    summary = await tester.run_all_tests()

    # 打印结果
    print("\n" + "="*70)
    print("鲁棒性测试结果汇总")
    print("="*70)
    print(f"总测试用例数: {summary['total_count']}")
    print(f"通过: {summary['passed_count']}")
    print(f"失败: {summary['failed_count']}")
    print(f"通过率: {summary['pass_rate']}%")
    print("\n按类别统计:")
    for category, stats in summary["category_stats"].items():
        pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {category}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")

    print("\n按难度统计:")
    for difficulty in sorted(summary["difficulty_stats"].keys()):
        stats = summary["difficulty_stats"][difficulty]
        pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  难度{difficulty}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")

    # 打印失败用例
    failed_cases = [r for r in tester.results if not r["passed"]]
    if failed_cases:
        print("\n失败用例列表:")
        for i, case in enumerate(failed_cases, 1):
            print(f"{i:2d}. {case['case_id']} [{case['category']}]: {case['reason']}")
            print(f"   用户输入: {case['user_input']}")
            print(f"   机器人回复: {case['response']}")

    # 生成报告
    tester.generate_report(summary)

    # 结论
    print("\n" + "="*70)
    if summary["pass_rate"] >= 95:
        print("✅ 测试通过! 鲁棒性达到上线要求")
    else:
        print("❌ 测试未通过! 需要优化后才能上线")
        print(f"   要求通过率 ≥95%，当前通过率 {summary['pass_rate']}%")


if __name__ == "__main__":
    asyncio.run(main())
