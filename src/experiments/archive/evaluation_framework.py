#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能催收对话系统测评框架
基于真实对话数据的完整测评
"""
import sys
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# 导入我们的模块
sys.path.append(str(Path(__file__).parent.parent.parent))

from experiments.archive.real_customer_simulator import RealCustomerSimulator, GOLDEN_TEST_CASES
from core.chatbot import CollectionChatBot, ChatState, get_stage_from_state


@dataclass
class EvaluationResult:
    """测评结果"""
    session_id: str
    chat_group: str
    persona: str
    description: str
    success: bool
    commit_time: Optional[str]
    conversation_length: int
    conversation_log: List[Dict]
    expected_success: bool
    stage_completion: Dict[str, bool]
    timestamp: str


class EvaluationFramework:
    """智能催收对话系统测评框架"""

    def __init__(self, use_tts: bool = False):
        self.simulator = RealCustomerSimulator()
        self.use_tts = use_tts
        self.results: List[EvaluationResult] = []

        # 测评统计
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "true_positive": 0,  # 预测成功实际成功
            "true_negative": 0,  # 预测失败实际失败
            "false_positive": 0,  # 预测成功实际失败
            "false_negative": 0,  # 预测失败实际成功
            "by_group": {"H2": {"total": 0, "success": 0},
                         "H1": {"total": 0, "success": 0},
                         "S0": {"total": 0, "success": 0}},
            "by_persona": {}
        }

    async def run_single_test(
        self,
        chat_group: str,
        persona: str,
        description: str,
        expected_success: bool,
        max_turns: int = 15
    ) -> EvaluationResult:
        """运行单个测试"""

        bot = CollectionChatBot(chat_group)
        session_id = bot.session_id

        print(f"\n  {'=' * 60}")
        print(f"  场景: {description}")
        print(f"  {'=' * 60}")

        conversation_log = []
        stage_completion = {
            "greeting": False,
            "identity": False,
            "purpose": False,
            "ask_time": False
        }

        # 开始对话 - 机器人先说话
        agent_text, audio_file = await bot.process(use_tts=self.use_tts)
        print(f"  坐席: {agent_text}")
        conversation_log.append({
            "role": "agent",
            "text": agent_text,
            "timestamp": datetime.now().isoformat()
        })

        current_stage = "greeting"
        stage_completion["greeting"] = True

        # 对话循环
        for turn in range(max_turns):
            if bot.is_finished():
                break

            # 客户回应
            customer_text = self.simulator.generate_response(
                stage=current_stage,
                chat_group=chat_group,
                persona=persona,
                last_agent_text=agent_text
            )

            print(f"  客户: {customer_text}")
            conversation_log.append({
                "role": "customer",
                "text": customer_text,
                "timestamp": datetime.now().isoformat()
            })

            # 机器人回应
            agent_text, audio_file = await bot.process(customer_text, use_tts=self.use_tts)

            if agent_text:
                print(f"  坐席: {agent_text}")
                conversation_log.append({
                    "role": "agent",
                    "text": agent_text,
                    "timestamp": datetime.now().isoformat()
                })

            # 更新当前阶段
            current_stage = get_stage_from_state(bot.state)
            if current_stage in stage_completion:
                stage_completion[current_stage] = True

        # 对话结束
        success = bot.is_successful()
        commit_time = bot.commit_time

        print(f"\n  结果: {'✅ 成功' if success else '❌ 失败'}")
        if commit_time:
            print(f"  约定时间: {commit_time}")
        print(f"  对话轮数: {len(conversation_log)}")

        result = EvaluationResult(
            session_id=session_id,
            chat_group=chat_group,
            persona=persona,
            description=description,
            success=success,
            commit_time=commit_time,
            conversation_length=len(conversation_log),
            conversation_log=conversation_log,
            expected_success=expected_success,
            stage_completion=stage_completion,
            timestamp=datetime.now().isoformat()
        )

        self.results.append(result)
        self._update_stats(result)

        return result

    def _update_stats(self, result: EvaluationResult):
        """更新统计数据"""
        self.stats["total"] += 1

        if result.success:
            self.stats["success"] += 1
        else:
            self.stats["failed"] += 1

        # 更新分类统计
        if result.success and result.expected_success:
            self.stats["true_positive"] += 1
        elif not result.success and not result.expected_success:
            self.stats["true_negative"] += 1
        elif result.success and not result.expected_success:
            self.stats["false_positive"] += 1
        elif not result.success and result.expected_success:
            self.stats["false_negative"] += 1

        # 按分组统计
        self.stats["by_group"][result.chat_group]["total"] += 1
        if result.success:
            self.stats["by_group"][result.chat_group]["success"] += 1

        # 按persona统计
        if result.persona not in self.stats["by_persona"]:
            self.stats["by_persona"][result.persona] = {"total": 0, "success": 0}
        self.stats["by_persona"][result.persona]["total"] += 1
        if result.success:
            self.stats["by_persona"][result.persona]["success"] += 1

    async def run_full_evaluation(self, num_additional_tests: int = 10):
        """运行完整测评"""
        print("=" * 70)
        print("智能催收对话系统测评")
        print("=" * 70)

        # 1. 先运行Golden测试用例
        print("\n【阶段1】Golden测试用例")
        print("-" * 70)

        for test_case in GOLDEN_TEST_CASES:
            chat_group, persona, description, expected_success = test_case
            await self.run_single_test(
                chat_group, persona, description, expected_success
            )

        # 2. 运行更多随机测试
        if num_additional_tests > 0:
            print(f"\n【阶段2】额外随机测试 ({num_additional_tests}个)")
            print("-" * 70)

            chat_groups = ["H2", "H1", "S0"]
            personas = ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful"]

            for i in range(num_additional_tests):
                chat_group = random.choice(chat_groups)
                persona = random.choice(personas)

                # 简单的期望成功率
                expected_success = persona != "resistant" or chat_group != "S0"

                await self.run_single_test(
                    chat_group, persona,
                    f"随机测试-{i+1}",
                    expected_success
                )

        # 3. 生成报告
        print("\n" + "=" * 70)
        print("测评完成！生成报告...")
        print("=" * 70)

        self._print_summary()
        self._save_report()

    def _print_summary(self):
        """打印摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        print(f"\n📊 总体结果:")
        print(f"  总测试数: {total}")
        print(f"  成功: {success} ({success_rate:.1f}%)")
        print(f"  失败: {self.stats['failed']}")

        print(f"\n📈 分类统计:")

        # 按chat group
        print(f"\n  按催收阶段:")
        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"    {group:3}: {data['success']}/{data['total']} ({rate:.1f}%)")

        # 按persona
        print(f"\n  按客户类型:")
        for persona, data in self.stats["by_persona"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"    {persona:12}: {data['success']}/{data['total']} ({rate:.1f}%)")

        # 预测准确率
        print(f"\n🎯 预测准确率:")
        tp = self.stats["true_positive"]
        tn = self.stats["true_negative"]
        total_correct = tp + tn
        accuracy = total_correct / total * 100 if total > 0 else 0
        print(f"  准确预测: {total_correct}/{total} ({accuracy:.1f}%)")
        print(f"  - 真阳性 (成功且预期成功): {tp}")
        print(f"  - 真阴性 (失败且预期失败): {tn}")
        print(f"  - 假阳性 (成功但预期失败): {self.stats['false_positive']}")
        print(f"  - 假阴性 (失败但预期成功): {self.stats['false_negative']}")

    def _save_report(self):
        """保存报告到文件"""
        output_dir = Path("data/evaluations")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存详细结果
        report_file = output_dir / f"evaluation_report_{timestamp}.json"

        report_data = {
            "metadata": {
                "timestamp": timestamp,
                "total_tests": len(self.results),
                "use_tts": self.use_tts
            },
            "summary": self.stats,
            "results": [asdict(r) for r in self.results]
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 保存markdown摘要
        md_file = output_dir / f"evaluation_summary_{timestamp}.md"
        md_content = self._generate_markdown_summary()

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n📄 报告已保存:")
        print(f"  - 详细JSON: {report_file}")
        print(f"  - 摘要MD: {md_file}")

    def _generate_markdown_summary(self) -> str:
        """生成markdown摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        md = f"""# 智能催收对话系统测评报告

**测评时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试总数**: {total}
**总体成功率**: {success_rate:.1f}% ({success}/{total})

---

## 总体结果

| 指标 | 数值 |
|-----|-----|
| 总测试数 | {total} |
| 成功 | {success} |
| 失败 | {self.stats['failed']} |
| 成功率 | {success_rate:.1f}% |

---

## 按催收阶段统计

| 阶段 | 测试数 | 成功 | 成功率 |
|-----|-------|-----|--------|
"""

        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {group} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        md += """
---

## 按客户类型统计

| 客户类型 | 测试数 | 成功 | 成功率 |
|---------|-------|-----|--------|
"""

        for persona, data in self.stats["by_persona"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {persona} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        md += f"""
---

## 预测准确率

| 指标 | 数值 |
|-----|-----|
| 真阳性 (成功且预期成功) | {self.stats["true_positive"]} |
| 真阴性 (失败且预期失败) | {self.stats["true_negative"]} |
| 假阳性 (成功但预期失败) | {self.stats["false_positive"]} |
| 假阴性 (失败但预期成功) | {self.stats["false_negative"]} |
| **总准确率** | {(self.stats["true_positive"] + self.stats["true_negative"]) / total * 100:.1f}% |

---

## 结论

"""

        if success_rate >= 80:
            md += "✅ **优秀** - 系统表现良好，达到预期目标！\n"
        elif success_rate >= 70:
            md += "⚠️ **良好** - 系统基本可用，还有提升空间\n"
        else:
            md += "❌ **需要改进** - 系统表现未达预期，需要优化\n"

        return md


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能催收对话系统测评框架")
    parser.add_argument("--use-tts", action="store_true", help="启用TTS语音合成")
    parser.add_argument("--num-tests", type=int, default=10, help="额外测试数量")

    args = parser.parse_args()

    # 运行测评
    framework = EvaluationFramework(use_tts=args.use_tts)
    await framework.run_full_evaluation(num_additional_tests=args.num_tests)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
