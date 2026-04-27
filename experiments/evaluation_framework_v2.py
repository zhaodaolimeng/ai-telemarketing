#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版智能催收对话系统测评框架
使用增强版客户模拟器，包含更多拒绝借口和抗拒程度分级
"""
import sys
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

sys.path.append(str(Path(__file__).parent))

from real_customer_simulator_v2 import RealCustomerSimulatorV2, GOLDEN_TEST_CASES_V2
from collection_chatbot_v3 import CollectionChatBot, ChatState


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
    resistance_level: Optional[str] = None
    push_count: int = 0
    stage_completion: Dict[str, bool] = None
    timestamp: str = None


class EvaluationFrameworkV2:
    """增强版智能催收对话系统测评框架"""

    def __init__(self, use_tts: bool = False):
        self.simulator = RealCustomerSimulatorV2()
        self.use_tts = use_tts
        self.results: List[EvaluationResult] = []

        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "true_positive": 0,
            "true_negative": 0,
            "false_positive": 0,
            "false_negative": 0,
            "by_group": {"H2": {"total": 0, "success": 0},
                         "H1": {"total": 0, "success": 0},
                         "S0": {"total": 0, "success": 0}},
            "by_persona": {},
            "by_resistance_level": {
                "very_low": {"total": 0, "success": 0},
                "low": {"total": 0, "success": 0},
                "medium": {"total": 0, "success": 0},
                "high": {"total": 0, "success": 0},
                "very_high": {"total": 0, "success": 0}
            }
        }

    async def run_single_test(
        self,
        chat_group: str,
        persona: str,
        description: str,
        expected_success: bool,
        resistance_level: str = "medium",
        max_turns: int = 20
    ) -> EvaluationResult:
        """运行单个测试"""

        bot = CollectionChatBot(chat_group)
        session_id = bot.session_id

        print(f"\n  {'=' * 70}")
        print(f"  场景: {description}")
        print(f"  抗拒程度: {resistance_level}")
        print(f"  {'=' * 70}")

        conversation_log = []
        stage_completion = {
            "greeting": False,
            "identity": False,
            "purpose": False,
            "ask_time": False
        }

        current_persona = persona
        push_count = 0

        # 开始对话
        agent_text, audio_file = await bot.process(use_tts=self.use_tts)
        print(f"  Agent: {agent_text}")
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

            # 计算被追问次数
            if "jam berapa" in agent_text.lower() or "kapan" in agent_text.lower():
                push_count += 1

            # 客户回应
            customer_text = self.simulator.generate_response(
                stage=current_stage,
                chat_group=chat_group,
                persona=persona,
                resistance_level=resistance_level,
                last_agent_text=agent_text,
                push_count=push_count
            )

            print(f"  Customer: {customer_text}")
            conversation_log.append({
                "role": "customer",
                "text": customer_text,
                "timestamp": datetime.now().isoformat()
            })

            # 机器人回应
            agent_text, audio_file = await bot.process(customer_text, use_tts=self.use_tts)

            if agent_text:
                print(f"  Agent: {agent_text}")
                conversation_log.append({
                    "role": "agent",
                    "text": agent_text,
                    "timestamp": datetime.now().isoformat()
                })

            # 更新当前阶段
            current_stage = self._get_stage_from_state(bot.state)
            if current_stage in stage_completion:
                stage_completion[current_stage] = True

        # 对话结束
        success = bot.is_successful()
        commit_time = bot.commit_time

        print(f"\n  结果: {'✅ 成功' if success else '❌ 失败'}")
        if commit_time:
            print(f"  约定时间: {commit_time}")
        print(f"  对话轮数: {len(conversation_log)}")
        print(f"  追问次数: {push_count}")

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
            resistance_level=resistance_level,
            push_count=push_count,
            stage_completion=stage_completion,
            timestamp=datetime.now().isoformat()
        )

        self.results.append(result)
        self._update_stats(result)

        return result

    def _get_stage_from_state(self, state: ChatState) -> str:
        """从状态获取阶段名称"""
        stage_map = {
            ChatState.INIT: "greeting",
            ChatState.GREETING: "greeting",
            ChatState.IDENTIFY: "identity",
            ChatState.PURPOSE: "purpose",
            ChatState.ASK_TIME: "ask_time",
            ChatState.PUSH_FOR_TIME: "push",
            ChatState.COMMIT_TIME: "commit",
            ChatState.CONFIRM: "confirm",
            ChatState.CLOSE: "close",
        }
        return stage_map.get(state, "greeting")

    def _update_stats(self, result: EvaluationResult):
        """更新统计数据"""
        self.stats["total"] += 1

        if result.success:
            self.stats["success"] += 1
        else:
            self.stats["failed"] += 1

        if result.success and result.expected_success:
            self.stats["true_positive"] += 1
        elif not result.success and not result.expected_success:
            self.stats["true_negative"] += 1
        elif result.success and not result.expected_success:
            self.stats["false_positive"] += 1
        elif not result.success and result.expected_success:
            self.stats["false_negative"] += 1

        self.stats["by_group"][result.chat_group]["total"] += 1
        if result.success:
            self.stats["by_group"][result.chat_group]["success"] += 1

        if result.persona not in self.stats["by_persona"]:
            self.stats["by_persona"][result.persona] = {"total": 0, "success": 0}
        self.stats["by_persona"][result.persona]["total"] += 1
        if result.success:
            self.stats["by_persona"][result.persona]["success"] += 1

        if result.resistance_level:
            self.stats["by_resistance_level"][result.resistance_level]["total"] += 1
            if result.success:
                self.stats["by_resistance_level"][result.resistance_level]["success"] += 1

    async def run_full_evaluation(self, num_additional_tests: int = 20):
        """运行完整测评"""
        print("=" * 70)
        print("增强版智能催收对话系统测评")
        print("=" * 70)

        print("\n【阶段1】Golden测试用例")
        print("-" * 70)

        for test_case in GOLDEN_TEST_CASES_V2:
            chat_group, persona, description, expected_success, resistance_level = test_case
            await self.run_single_test(
                chat_group, persona, description, expected_success, resistance_level
            )

        if num_additional_tests > 0:
            print(f"\n【阶段2】额外随机测试 ({num_additional_tests}个)")
            print("-" * 70)

            chat_groups = ["H2", "H1", "S0"]
            personas = ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful", "excuse_master"]
            resistance_levels = ["very_low", "low", "medium", "high", "very_high"]

            for i in range(num_additional_tests):
                chat_group = random.choice(chat_groups)
                persona = random.choice(personas)
                resistance_level = random.choice(resistance_levels)

                expected_success = resistance_level in ["very_low", "low"] or \
                                  (resistance_level == "medium" and persona in ["cooperative", "busy"])

                await self.run_single_test(
                    chat_group, persona, f"随机测试-{i+1}",
                    expected_success, resistance_level
                )

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

        print(f"\n📈 按催收阶段统计:")
        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {group:3}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n👥 按客户类型统计:")
        for persona, data in self.stats["by_persona"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {persona:12}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n🎚️ 按抗拒程度统计:")
        for level, data in self.stats["by_resistance_level"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {level:10}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n🎯 预测准确率:")
        tp, tn = self.stats["true_positive"], self.stats["true_negative"]
        fp, fn = self.stats["false_positive"], self.stats["false_negative"]
        total_correct = tp + tn
        accuracy = total_correct / total * 100 if total > 0 else 0
        print(f"  准确预测: {total_correct}/{total} ({accuracy:.1f}%)")
        print(f"  - 真阳性: {tp}")
        print(f"  - 真阴性: {tn}")
        print(f"  - 假阳性: {fp}")
        print(f"  - 假阴性: {fn}")

    def _save_report(self):
        """保存报告"""
        output_dir = Path("data/evaluations")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report_file = output_dir / f"evaluation_report_v2_{timestamp}.json"
        report_data = {
            "metadata": {
                "timestamp": timestamp,
                "total_tests": len(self.results),
                "version": "v2",
                "use_tts": self.use_tts
            },
            "summary": self.stats,
            "results": [asdict(r) for r in self.results]
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        md_file = output_dir / f"evaluation_summary_v2_{timestamp}.md"
        md_content = self._generate_markdown_summary()

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n📄 报告已保存:")
        print(f"  - 详细JSON: {report_file}")
        print(f"  - 摘要MD: {md_file}")

    def _generate_markdown_summary(self) -> str:
        """生成Markdown摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        md = f"""# 增强版智能催收对话系统测评报告

**测评时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试总数**: {total}
**总体成功率**: {success_rate:.1f}%

---

## 总体结果

| 指标 | 数值 |
|-----|------|
| 总测试数 | {total} |
| 成功 | {success} |
| 失败 | {self.stats['failed']} |
| 成功率 | {success_rate:.1f}% |

---

## 按催收阶段统计

| 阶段 | 测试数 | 成功 | 成功率 |
|-----|--------|-----|--------|
"""

        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {group} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        md += f"""
---

## 按客户类型统计

| 客户类型 | 测试数 | 成功 | 成功率 |
|---------|--------|-----|--------|
"""

        for persona, data in self.stats["by_persona"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {persona} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        md += f"""
---

## 按抗拒程度统计

| 抗拒程度 | 测试数 | 成功 | 成功率 |
|---------|--------|-----|--------|
"""

        for level, data in self.stats["by_resistance_level"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {level} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        tp, tn = self.stats["true_positive"], self.stats["true_negative"]
        fp, fn = self.stats["false_positive"], self.stats["false_negative"]
        total_correct = tp + tn
        accuracy = total_correct / total * 100 if total > 0 else 0

        md += f"""
---

## 预测准确率

| 指标 | 数值 |
|-----|------|
| 真阳性 | {tp} |
| 真阴性 | {tn} |
| 假阳性 | {fp} |
| 假阴性 | {fn} |
| 总准确率 | {accuracy:.1f}% |

---

## 测评框架特点

✅ 7种客户类型: cooperative, busy, negotiating, silent, forgetful, resistant, excuse_master

✅ 5种抗拒程度: very_low, low, medium, high, very_high

✅ 40+种拒绝借口: 经济困难、时间忙碌、家庭问题、质疑争议等

✅ 借口链条: 从轻度抗拒到重度抗拒的渐进式借口

✅ 追问计数: 跟踪被追问次数，模拟真实对话压力

---

## 结论"""

        if success_rate >= 75:
            md += "\n✅ **优秀** - 系统表现良好！"
        elif success_rate >= 60:
            md += "\n⚠️ **良好** - 系统基本可用"
        else:
            md += "\n❌ **需要改进** - 系统表现未达预期"

        return md


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="增强版智能催收对话系统测评框架")
    parser.add_argument("--use-tts", action="store_true", help="启用TTS语音合成")
    parser.add_argument("--num-tests", type=int, default=20, help="额外测试数量")

    args = parser.parse_args()

    framework = EvaluationFrameworkV2(use_tts=args.use_tts)
    await framework.run_full_evaluation(num_additional_tests=args.num_tests)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
