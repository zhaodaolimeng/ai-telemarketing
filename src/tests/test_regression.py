#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化回归测试用例
验证系统在各种场景下的功能是否正常，特别是合规性
"""
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, ChatState
from core.compliance_checker import ComplianceChecker


class RegressionTestCase:
    """回归测试用例"""

    def __init__(self, name: str, description: str, user_inputs: List[str],
                 expected_states: List[ChatState], expected_success: bool,
                 expected_compliant: bool = True):
        self.name = name
        self.description = description
        self.user_inputs = user_inputs
        self.expected_states = expected_states
        self.expected_success = expected_success
        self.expected_compliant = expected_compliant
        self.result: Dict[str, Any] = {}


class RegressionTester:
    """回归测试器"""

    def __init__(self):
        self.test_cases: List[RegressionTestCase] = []
        self.passed = 0
        self.failed = 0
        self.compliance_checker = ComplianceChecker()
        self._init_test_cases()

    def _init_test_cases(self):
        """初始化测试用例"""

        # 测试用例1: 正常流程，用户配合，直接给出还款时间
        self.test_cases.append(RegressionTestCase(
            name="normal_cooperative_user",
            description="正常流程，用户配合，直接确认身份并给出还款时间",
            user_inputs=["Ya, ini saya.", "Saya bayar jam 3 sore ya."],
            expected_states=[ChatState.PURPOSE, ChatState.CLOSE],
            expected_success=True
        ))

        # 测试用例2: 用户现在忙
        self.test_cases.append(RegressionTestCase(
            name="user_busy_now",
            description="用户说现在忙，系统应该结束对话",
            user_inputs=["Ya, tapi saya sedang sibuk sekarang."],
            expected_states=[ChatState.CLOSE],
            expected_success=False
        ))

        # 测试用例3: 用户否认身份/错号
        self.test_cases.append(RegressionTestCase(
            name="user_deny_identity",
            description="用户否认身份，说打错电话了，系统应该结束对话",
            user_inputs=["Bukan, Anda salah nomor."],
            expected_states=[ChatState.CLOSE],
            expected_success=False
        ))

        # 测试用例4: 用户威胁要投诉到OJK
        self.test_cases.append(RegressionTestCase(
            name="user_threaten_ojk",
            description="用户威胁要投诉到OJK，系统应该礼貌回应",
            user_inputs=["Ya, tapi kalau Anda terus telepon saya akan laporkan ke OJK!"],
            expected_states=[ChatState.HANDLE_OBJECTION, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例5: 用户询问展期
        self.test_cases.append(RegressionTestCase(
            name="user_ask_extension",
            description="用户询问是否可以展期，系统应该解释展期政策",
            user_inputs=["Ya, bisa nggak saya perpanjang masa pembayaran?"],
            expected_states=[ChatState.CONFIRM_EXTENSION],
            expected_success=False
        ))

        # 测试用例6: 用户同意展期
        self.test_cases.append(RegressionTestCase(
            name="user_agree_extension",
            description="用户同意展期，然后给出还款时间",
            user_inputs=["Ya, bisa nggak saya perpanjang?", "Ya, saya setuju.", "Saya bayar besok jam 2 ya."],
            expected_states=[ChatState.CONFIRM_EXTENSION, ChatState.ASK_TIME, ChatState.CLOSE],
            expected_success=True
        ))

        # 测试用例7: 用户询问金额
        self.test_cases.append(RegressionTestCase(
            name="user_ask_amount",
            description="用户询问欠款金额，系统应该回答",
            user_inputs=["Ya, berapa total tagihan saya?"],
            expected_states=[ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例8: 用户质疑身份/以为是诈骗
        self.test_cases.append(RegressionTestCase(
            name="user_question_identity",
            description="用户质疑身份，问是谁打来的，系统应该回答",
            user_inputs=["Siapa Anda? Dari mana?", "Ini penipuan ya?"],
            expected_states=[ChatState.PURPOSE, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例9: 用户说没钱
        self.test_cases.append(RegressionTestCase(
            name="user_no_money",
            description="用户说现在没钱，系统应该给出解决方案",
            user_inputs=["Ya, tapi saya tidak punya uang sekarang."],
            expected_states=[ChatState.HANDLE_OBJECTION, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例10: 用户拒绝还款
        self.test_cases.append(RegressionTestCase(
            name="user_refuse_to_pay",
            description="用户明确拒绝还款，系统应该处理",
            user_inputs=["Saya tidak mau bayar!"],
            expected_states=[ChatState.HANDLE_OBJECTION, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例11: 用户使用口语化表达还款时间
        self.test_cases.append(RegressionTestCase(
            name="user_colloquial_time",
            description="用户使用口语化表达还款时间，系统应该能识别",
            user_inputs=["Ya", "Nanti sore jam 5 ya saya transfer."],
            expected_states=[ChatState.PURPOSE, ChatState.CLOSE],
            expected_success=True
        ))

        # 测试用例12: ASR错误场景 - "Uang"被识别成"Ufah Nau"
        self.test_cases.append(RegressionTestCase(
            name="asr_error_uang",
            description="ASR识别错误，'Uang'被识别成'Ufah Nau'，系统应该能纠正并理解",
            user_inputs=["Ya", "Saya bayar melalui aplikasi Ufah Nau ya."],
            expected_states=[ChatState.PURPOSE, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例13: ASR错误场景 - "lunas"被识别成"nasian"
        self.test_cases.append(RegressionTestCase(
            name="asr_error_lunas",
            description="ASR识别错误，'lunas'被识别成'nasian'，系统应该能纠正并理解",
            user_inputs=["Ya", "Saya mau bayar nasian hari ini."],
            expected_states=[ChatState.PURPOSE, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例14: 用户不直接确认身份，只是问候
        self.test_cases.append(RegressionTestCase(
            name="user_greet_instead_confirm",
            description="用户不直接确认身份，只是回复问候，系统应该能识别为确认身份",
            user_inputs=["Selamat pagi juga.", "Ya."],
            expected_states=[ChatState.PURPOSE, ChatState.ASK_TIME],
            expected_success=False
        ))

        # 测试用例15: 用户给出模糊时间，然后被催促后给出明确时间
        self.test_cases.append(RegressionTestCase(
            name="user_fuzzy_then_clear_time",
            description="用户先给出模糊时间，被催促后给出明确时间",
            user_inputs=["Ya", "Nanti aja ya.", "Besok jam 3 ya."],
            expected_states=[ChatState.PURPOSE, ChatState.PUSH_FOR_TIME, ChatState.CLOSE],
            expected_success=True
        ))

    async def run_test_case(self, test_case: RegressionTestCase) -> bool:
        """运行单个测试用例"""
        print(f"\nRunning test: {test_case.name}")
        print(f"Description: {test_case.description}")

        bot = CollectionChatBot(chat_group="H2", customer_name="Bapak Joko",
                                overdue_amount=500000, overdue_days=5)

        conversation = []
        states = []

        # 初始消息（机器人先说话）
        agent_response, _ = await bot.process()
        conversation.append({"role": "agent", "text": agent_response})
        print(f"Agent: {agent_response}")

        # 处理用户输入
        for user_input in test_case.user_inputs:
            print(f"User: {user_input}")
            agent_response, _ = await bot.process(user_input)
            conversation.append({"role": "user", "text": user_input})
            conversation.append({"role": "agent", "text": agent_response})
            states.append(bot.state)
            if agent_response:
                print(f"Agent: {agent_response}")

            if bot.is_finished():
                break

        # 检查结果
        success = bot.is_successful()
        commit_time = bot.commit_time

        # 合规性检查
        all_compliant = True
        violation_details = []
        for turn in conversation:
            if turn["role"] == "agent" and turn["text"]:
                compliant, violations = self.compliance_checker.check(turn["text"])
                if not compliant:
                    all_compliant = False
                    violation_details.extend(violations)

        # 验证预期
        state_match = True
        for i, expected_state in enumerate(test_case.expected_states):
            if i >= len(states) or states[i] != expected_state:
                state_match = False
                break

        success_match = success == test_case.expected_success
        compliance_match = all_compliant == test_case.expected_compliant

        test_passed = state_match and success_match and compliance_match

        # 保存结果
        test_case.result = {
            "passed": test_passed,
            "actual_states": [s.name for s in states],
            "expected_states": [s.name for s in test_case.expected_states],
            "actual_success": success,
            "expected_success": test_case.expected_success,
            "actual_compliant": all_compliant,
            "expected_compliant": test_case.expected_compliant,
            "commit_time": commit_time,
            "violations": violation_details,
            "conversation": conversation
        }

        # 输出结果
        if test_passed:
            print(f"✅ Test {test_case.name} PASSED")
            self.passed += 1
        else:
            print(f"❌ Test {test_case.name} FAILED")
            if not state_match:
                print(f"  State mismatch: Expected {[s.name for s in test_case.expected_states]}, Got {[s.name for s in states]}")
            if not success_match:
                print(f"  Success mismatch: Expected {test_case.expected_success}, Got {success}")
            if not compliance_match:
                print(f"  Compliance mismatch: Expected {test_case.expected_compliant}, Got {all_compliant}")
                if violation_details:
                    print(f"  Violations: {violation_details}")
            self.failed += 1

        return test_passed

    async def run_all_tests(self):
        """运行所有测试用例"""
        print(f"Running {len(self.test_cases)} regression tests...")

        for test_case in self.test_cases:
            await self.run_test_case(test_case)

        # 输出总结
        print(f"\n{'='*60}")
        print("REGRESSION TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {len(self.test_cases)}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success rate: {self.passed / len(self.test_cases) * 100:.1f}%")

        if self.failed > 0:
            print(f"\n❌ {self.failed} tests failed! Please check the issues above.")
            return False
        else:
            print(f"\n✅ All tests passed!")
            return True

    def generate_report(self, output_file: str = None):
        """生成测试报告"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"data/regression_report_{timestamp}.md"

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        report = f"""# 回归测试报告
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**总测试用例**: {len(self.test_cases)}
**通过**: {self.passed}
**失败**: {self.failed}
**成功率**: {self.passed / len(self.test_cases) * 100:.1f}%

---

## 测试用例详情
"""

        for test_case in self.test_cases:
            result = test_case.result
            status_icon = "✅" if result["passed"] else "❌"

            report += f"""
### {status_icon} {test_case.name}
**描述**: {test_case.description}
**结果**: {"通过" if result["passed"] else "失败"}
**预期成功**: {result["expected_success"]}
**实际成功**: {result["actual_success"]}
**预期合规**: {result["expected_compliant"]}
**实际合规**: {result["actual_compliant"]}
**预期状态**: {result["expected_states"]}
**实际状态**: {result["actual_states"]}
"""

            if not result["passed"]:
                report += "**失败原因**: "
                reasons = []
                if result["actual_success"] != result["expected_success"]:
                    reasons.append("成功状态不匹配")
                if result["actual_compliant"] != result["expected_compliant"]:
                    reasons.append("合规性不匹配")
                    if result["violations"]:
                        reasons.append(f"违规内容: {result['violations']}")
                if result["actual_states"] != result["expected_states"]:
                    reasons.append("状态流转不匹配")
                report += ", ".join(reasons) + "\n"

            # 对话日志
            report += "\n**对话日志**:\n"
            for turn in result["conversation"]:
                report += f"- {turn['role'].upper()}: {turn['text']}\n"

            report += "---\n"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\nReport saved to: {output_file}")
        return output_file


async def main():
    """主函数"""
    tester = RegressionTester()
    success = await tester.run_all_tests()
    tester.generate_report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
