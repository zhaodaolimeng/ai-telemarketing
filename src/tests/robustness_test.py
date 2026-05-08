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
        passed, reason, root_cause = self._check_response(test_case, response)

        # 获取合规违规详情
        checker = get_compliance_checker()
        _, violations = checker.check(response)
        violation_summary = [
            {"rule_id": v["rule_id"], "severity": v["severity"], "description": v["description"]}
            for v in violations
        ]

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
            "root_cause": root_cause,
            "violations": violation_summary,
            "timestamp": datetime.now().isoformat()
        }

        return result

    def _check_response(self, test_case: TestCase, response: str) -> Tuple[bool, str, str]:
        """检查回复是否符合要求，返回 (通过, 原因, 根因类别)"""
        if not response:
            return False, "机器人没有回复", "no_response"

        # 检查合规要求（强制要求，不满足直接失败）
        compliance_passed, compliance_reason = self._check_compliance(test_case.compliance_requirements, response)
        if not compliance_passed:
            return False, f"合规检查失败: {compliance_reason}", "compliance_violation"

        # 检查预期要求
        expected_passed, expected_reason = self._check_expected(test_case.expected_requirements, response)
        if not expected_passed:
            return False, f"预期要求未满足: {expected_reason}", "expectation_mismatch"

        return True, "所有检查通过", "passed"

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

    def _build_root_cause_stats(self) -> Dict:
        """聚合失败根因分布"""
        causes = {}
        for r in self.results:
            if not r["passed"]:
                rc = r.get("root_cause", "unknown")
                causes[rc] = causes.get(rc, 0) + 1
        return causes

    def _build_compliance_aggregation(self) -> Dict:
        """聚合合规违规统计"""
        agg = {"high_rules": {}, "medium_rules": {}, "low_rules": {}, "total_violations": 0}
        for r in self.results:
            for v in r.get("violations", []):
                agg["total_violations"] += 1
                sev_key = f"{v['severity']}_rules"
                rule_id = v["rule_id"]
                agg[sev_key][rule_id] = agg[sev_key].get(rule_id, 0) + 1
        return agg

    def _generate_recommendations(self, summary: Dict, root_causes: Dict) -> List[str]:
        """基于失败模式生成改进建议"""
        recs = []
        total = summary["total_count"]
        passed = summary["passed_count"]
        pass_rate = summary["pass_rate"]

        if root_causes.get("compliance_violation", 0) > 0:
            n = root_causes["compliance_violation"]
            recs.append(f"🔴 合规违规 ({n}例): 审查高风险话术，确保脚本不包含威胁、辱骂、虚假承诺等内容。"
                        f"重点检查 compliance_checker.py 中标记的 high severity 规则。")

        if root_causes.get("expectation_mismatch", 0) > 0:
            n = root_causes["expectation_mismatch"]
            recs.append(f"🟠 预期不符 ({n}例): 状态机或话术模板未覆盖当前场景的预期行为。"
                        f"建议扩展 chatbot.py 中对应状态的处理逻辑，或补充针对性话术。")

        if root_causes.get("no_response", 0) > 0:
            n = root_causes["no_response"]
            recs.append(f"🟡 无回复 ({n}例): 机器人未生成任何回复，可能为 unknown 意图兜底失效。"
                        f"检查 fallback_detector.py 触发条件和 LLM 降级链是否正常。")

        # 按类别分析
        category_stats = summary.get("category_stats", {})
        weak_categories = []
        for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]["passed"] / max(x[1]["total"], 1)):
            cat_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            if cat_rate < 70.0:
                weak_categories.append((cat, cat_rate))
        if weak_categories:
            names = ", ".join(f"{c}({r:.0f}%)" for c, r in weak_categories[:3])
            recs.append(f"🔵 弱项类别 ({len(weak_categories)}个): {names}。"
                        f"建议针对此类场景扩充话术库、增加状态机分支。")

        if pass_rate < 50:
            recs.append("🚨 整体通过率<50%: 建议优先修复合规违规和 no_response 问题后再重新测试。")
        elif pass_rate < 80:
            recs.append("⚠️ 整体通过率<80%: 除合规修复外，需持续优化状态机话术覆盖。")
        elif pass_rate < 95:
            recs.append("📈 整体通过率<95%: 距离上线标准差一步之遥，重点处理剩余失败案例。")
        else:
            recs.append("✅ 整体通过率≥95%，鲁棒性达到上线标准。")

        return recs

    def generate_report(self, summary: Dict, output_dir: Optional[str] = None) -> str:
        """生成增强版测试报告（含根因分析、合规聚合、改进建议）"""
        if output_dir is None:
            output_dir = Path("data/robustness_tests")
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root_causes = self._build_root_cause_stats()
        compliance_agg = self._build_compliance_aggregation()
        recommendations = self._generate_recommendations(summary, root_causes)

        # ---- JSON 报告 ----
        json_file = output_dir / f"robustness_test_{timestamp}.json"
        report_data = {
            "meta": {
                "test_time": datetime.now().isoformat(),
                "total_cases": len(self.test_cases),
                "version": "2.0"
            },
            "summary": summary,
            "root_cause_distribution": root_causes,
            "compliance_aggregation": {
                "total_violations": compliance_agg["total_violations"],
                "high": compliance_agg["high_rules"],
                "medium": compliance_agg["medium_rules"],
                "low": compliance_agg["low_rules"]
            },
            "recommendations": recommendations,
            "detailed_results": self.results
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # ---- Markdown 报告 ----
        md_file = output_dir / f"robustness_test_{timestamp}.md"
        total = summary["total_count"]
        passed = summary["passed_count"]
        failed = summary["failed_count"]
        pass_rate = summary["pass_rate"]

        md = f"""# 鲁棒性测试报告

**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试版本:** 2.0 (含根因分析 + 合规聚合 + 改进建议)

---

## 📊 总体结果

| 指标 | 数值 |
|------|------|
| 总测试用例数 | {total} |
| 通过用例数 | {passed} |
| 失败用例数 | {failed} |
| 通过率 | {pass_rate}% |

### 状态判定
{"✅ 通过 (≥95%)" if pass_rate >= 95 else "⚠️ 待优化 (80%-95%)" if pass_rate >= 80 else "❌ 未通过 (<80%)"}

---

## 🔍 根因分布

| 根因类别 | 数量 | 占比 |
|----------|------|------|
"""
        root_cause_labels = {
            "passed": "✅ 通过",
            "compliance_violation": "🔴 合规违规",
            "expectation_mismatch": "🟠 预期不符",
            "no_response": "🟡 无回复",
            "unknown": "❓ 未知",
        }
        for rc, count in sorted(root_causes.items(), key=lambda x: -x[1]):
            label = root_cause_labels.get(rc, rc)
            md += f"| {label} | {count} | {count / max(total, 1) * 100:.1f}% |\n"

        md += f"""
---

## 🛡️ 合规聚合

| 严重级别 | 违规次数 |
|----------|----------|
| 🔴 高风险 | {sum(compliance_agg['high_rules'].values())} |
| 🟠 中风险 | {sum(compliance_agg['medium_rules'].values())} |
| 🟡 低风险 | {sum(compliance_agg['low_rules'].values())} |
| **合计** | **{compliance_agg['total_violations']}** |

"""
        if compliance_agg["high_rules"]:
            md += "### 高频高风险违规规则\n| 规则ID | 次数 |\n|--------|------|\n"
            for rid, cnt in sorted(compliance_agg["high_rules"].items(), key=lambda x: -x[1]):
                md += f"| {rid} | {cnt} |\n"

        if compliance_agg["medium_rules"]:
            md += "\n### 高频中风险违规规则\n| 规则ID | 次数 |\n|--------|------|\n"
            for rid, cnt in sorted(compliance_agg["medium_rules"].items(), key=lambda x: -x[1]):
                md += f"| {rid} | {cnt} |\n"

        md += f"""
---

## 📈 按类别统计

| 类别 | 总数 | 通过数 | 通过率 |
|------|------|--------|--------|
"""
        for category, stats in summary["category_stats"].items():
            cat_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            icon = "✅" if cat_rate >= 95 else "⚠️" if cat_rate >= 70 else "❌"
            md += f"| {icon} {category} | {stats['total']} | {stats['passed']} | {cat_rate:.1f}% |\n"

        md += """
## 🎯 按难度统计

| 难度 | 总数 | 通过数 | 通过率 |
|------|------|--------|--------|
"""
        for difficulty in sorted(summary["difficulty_stats"].keys()):
            stats = summary["difficulty_stats"][difficulty]
            diff_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            md += f"| {difficulty} | {stats['total']} | {stats['passed']} | {diff_rate:.1f}% |\n"

        md += """
---

## 💡 改进建议

"""
        for i, rec in enumerate(recommendations, 1):
            md += f"{i}. {rec}\n"

        md += """
---

## ❌ 失败用例详情

| 用例ID | 类别 | 难度 | 用户输入 | 中文翻译 | 机器人回复 | 失败原因 | 根因 |
|--------|------|------|----------|----------|------------|----------|------|
"""
        root_cause_labels_short = {
            "compliance_violation": "合规违规",
            "expectation_mismatch": "预期不符",
            "no_response": "无回复",
        }
        for result in self.results:
            if not result["passed"]:
                rc_label = root_cause_labels_short.get(result.get("root_cause", ""), result.get("root_cause", "-"))
                md += (f'| {result["case_id"]} | {result["category"]} | {result["difficulty"]} | '
                       f'{result["user_input"][:40]} | {result["chinese_translation"][:30]} | '
                       f'{result["response"][:50]} | {result["reason"][:60]} | {rc_label} |\n')

        md += """
---

## 📋 测试覆盖说明

| 覆盖维度 | 详情 |
|----------|------|
| 高风险场景 | 恶意对抗、极端抗拒、逻辑陷阱、异常输入、身份质疑 共 5 大类 |
| 合规检查 | 11 条内置规则 (6条高风险 + 5条中风险 + 3条低风险) |
| 难度分级 | 1(简单) ~ 5(极端) |
| 判断标准 | 合规为强制项 (违反即失败) + 预期要求为优化项 |
"""

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md)

        # 存储历史快照用于趋势对比
        history_file = output_dir / "history.json"
        history = []
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append({
            "timestamp": datetime.now().isoformat(),
            "pass_rate": pass_rate,
            "total": total,
            "passed": passed,
            "failed": failed,
            "root_causes": root_causes,
        })
        # 保留最近 20 次记录
        history = history[-20:]
        history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2))

        print(f"\n📋 测试报告已生成:")
        print(f"  - JSON报告: {json_file}")
        print(f"  - Markdown报告: {md_file}")
        print(f"  - 历史记录: {history_file} ({len(history)} 次)")

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
