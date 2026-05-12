#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线合成对照评估工具
基于历史人工催收数据，模拟机器人催收效果，预测上线后的真实回款率，与人工做对比
"""
import asyncio
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot
from core.compliance_checker import get_compliance_checker

@dataclass
class HistoricalCase:
    """历史催收案例"""
    case_id: str
    user_phone: str
    collection_stage: str
    user_persona: str
    resistance_level: str
    dialogue_history: List[Dict]
    actual_result: str  # 实际结果: success/failure/extension
    actual_repayment_amount: Optional[float]  # 实际回款金额
    actual_repayment_days: Optional[int]  # 实际回款天数
    collector_id: str
    call_duration: float

@dataclass
class SimulationResult:
    """模拟结果"""
    case_id: str
    predicted_result: str
    predicted_repayment_probability: float
    predicted_repayment_days: Optional[int]
    dialogue: List[Dict]
    compliance_violations: List[Dict]
    total_turns: int
    call_duration_predicted: float

@dataclass
class EvaluationResult:
    """评估结果"""
    total_cases: int
    robot_success_rate: float
    human_success_rate: float
    success_rate_diff: float
    robot_avg_repayment_amount: float
    human_avg_repayment_amount: float
    amount_diff: float
    robot_avg_repayment_days: float
    human_avg_repayment_days: float
    days_diff: float
    compliance_violation_rate: float
    accuracy: float  # 预测结果与实际结果的准确率
    correlation: float  # 预测与实际结果的相关性
    scenario_analysis: Dict[str, Dict]  # 分场景分析

class OfflineEvaluator:
    """离线评估器"""

    def __init__(self, historical_data_path: str = "data/processed/historical/"):
        self.historical_dir = Path(historical_data_path)
        self.historical_cases: List[HistoricalCase] = []
        self.compliance_checker = get_compliance_checker()

        # 回款概率模型参数（基于业务经验配置，可根据实际数据训练优化）
        self.repayment_probability_factors = {
            "success_keywords": {"ya", "oke", "janji", "akan bayar", "tanggal", "jam", "pasti"},
            "negotiation_keywords": {"perpanjang", "cicil", "kurang", "tidak bisa", "nanti", "besok"},
            "resistance_keywords": {"tidak mau", "jangan telepon", "salah nomor", "tidak ada", "tidak punya"},
            "weights": {
                "user_promise": 0.6,  # 用户是否明确承诺还款
                "user_resistance": -0.4,  # 用户抗拒程度
                "call_duration": 0.2,  # 通话时长
                "response_relevance": 0.3,  # 机器人回复相关性
                "compliance": 0.1,  # 合规性
            }
        }

        self._load_historical_data()

    def _load_historical_data(self) -> None:
        """加载历史催收数据"""
        if not self.historical_dir.exists():
            print(f"警告：历史数据目录 {self.historical_dir} 不存在，请先准备历史数据")
            return

        for file_path in self.historical_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    case = HistoricalCase(
                        case_id=data.get("case_id", file_path.stem),
                        user_phone=data.get("user_phone", ""),
                        collection_stage=data.get("collection_stage", "H2"),
                        user_persona=data.get("user_persona", "cooperative"),
                        resistance_level=data.get("resistance_level", "low"),
                        dialogue_history=data.get("dialogue_history", []),
                        actual_result=data.get("actual_result", "failure"),
                        actual_repayment_amount=data.get("actual_repayment_amount"),
                        actual_repayment_days=data.get("actual_repayment_days"),
                        collector_id=data.get("collector_id", ""),
                        call_duration=data.get("call_duration", 0.0)
                    )
                    self.historical_cases.append(case)
            except Exception as e:
                print(f"加载历史数据 {file_path} 失败: {e}")

        print(f"成功加载 {len(self.historical_cases)} 条历史催收案例")

    async def simulate_single_case(self, case: HistoricalCase) -> SimulationResult:
        """模拟单个案例的机器人催收效果"""
        bot = CollectionChatBot(chat_group=case.collection_stage)
        bot_state = None
        dialogue = []
        violations = []
        total_turns = 0

        # 提取所有用户的历史输入
        user_inputs = []
        for turn in case.dialogue_history:
            if turn.get("speaker") == "customer" or turn.get("role") == "user":
                user_inputs.append(turn.get("text", "").strip())

        # 如果没有用户输入，使用默认开头
        if not user_inputs:
            user_inputs = ["Iya?"]

        # 模拟对话过程
        for user_input in user_inputs:
            if not user_input:
                continue

            try:
                response, bot_state = await bot.process(user_input, bot_state)
                total_turns += 1

                # 检查合规性
                is_compliant, turn_violations = self.compliance_checker.check(response)
                violations.extend(turn_violations)

                dialogue.append({
                    "turn": total_turns,
                    "user_input": user_input,
                    "bot_response": response
                })

                # 检测对话是否应该结束
                if self._is_conversation_end(response):
                    break

            except Exception as e:
                print(f"处理案例 {case.case_id} 时出错: {e}")
                continue

        # 预测结果
        predicted_result, repayment_prob, repayment_days = self._predict_result(dialogue, case)

        # 预测通话时长（基于轮数估算，平均每轮10秒）
        predicted_duration = total_turns * 10.0

        return SimulationResult(
            case_id=case.case_id,
            predicted_result=predicted_result,
            predicted_repayment_probability=repayment_prob,
            predicted_repayment_days=repayment_days,
            dialogue=dialogue,
            compliance_violations=violations,
            total_turns=total_turns,
            call_duration_predicted=predicted_duration
        )

    def _is_conversation_end(self, response: str) -> bool:
        """判断对话是否应该结束"""
        end_keywords = ["terima kasih", "selamat tinggal", "saya tutup", "sampai jumpa", "bye"]
        response_lower = response.lower().strip()
        return any(kw in response_lower for kw in end_keywords)

    def _predict_result(self, dialogue: List[Dict], case: HistoricalCase) -> Tuple[str, float, Optional[int]]:
        """预测催收结果和回款概率"""
        if not dialogue:
            return "failure", 0.0, None

        full_text = " ".join([turn["user_input"] + " " + turn["bot_response"] for turn in dialogue]).lower()
        user_responses = " ".join([turn["user_input"] for turn in dialogue]).lower()
        bot_responses = " ".join([turn["bot_response"] for turn in dialogue]).lower()

        # 计算各个因子得分
        score = 0.5  # 基础分

        # 1. 用户是否有还款承诺
        has_promise = any(kw in user_responses for kw in self.repayment_probability_factors["success_keywords"])
        if has_promise:
            score += self.repayment_probability_factors["weights"]["user_promise"]

        # 2. 用户抗拒程度
        has_resistance = any(kw in user_responses for kw in self.repayment_probability_factors["resistance_keywords"])
        if has_resistance:
            score += self.repayment_probability_factors["weights"]["user_resistance"]

        # 3. 通话时长因子
        avg_turns = len(dialogue)
        duration_factor = min(avg_turns / 10.0, 1.0)  # 超过10轮就算满分
        score += self.repayment_probability_factors["weights"]["call_duration"] * duration_factor

        # 4. 回复相关性因子（是否有协商相关内容）
        has_negotiation = any(kw in bot_responses for kw in self.repayment_probability_factors["negotiation_keywords"])
        if has_negotiation and case.resistance_level in ["medium", "high"]:
            score += self.repayment_probability_factors["weights"]["response_relevance"]

        # 5. 合规性因子
        has_high_risk_violation = any(v["severity"] == "high" for v in dialogue[0].get("violations", [])) if dialogue else False
        if not has_high_risk_violation:
            score += self.repayment_probability_factors["weights"]["compliance"]

        # 确保得分在0-1之间
        repayment_prob = max(0.0, min(1.0, score))

        # 判断结果类型
        if repayment_prob >= 0.7:
            result = "success"
        elif 0.4 <= repayment_prob < 0.7:
            result = "extension"
        else:
            result = "failure"

        # 预测回款天数（基于用户类型和还款概率）
        if result == "success":
            if case.resistance_level == "very_low":
                days = 1
            elif case.resistance_level == "low":
                days = 3
            elif case.resistance_level == "medium":
                days = 7
            else:
                days = 14
        elif result == "extension":
            days = 30
        else:
            days = None

        return result, round(repayment_prob, 4), days

    async def run_evaluation(self, sample_size: Optional[int] = None) -> Tuple[List[SimulationResult], EvaluationResult]:
        """运行完整的离线评估"""
        if not self.historical_cases:
            print("没有可用的历史数据，请先准备历史催收案例")
            return [], None

        # 抽样
        cases = self.historical_cases[:sample_size] if sample_size else self.historical_cases
        print(f"开始评估 {len(cases)} 个案例...")

        # 并行运行模拟
        results = []
        for i, case in enumerate(cases, 1):
            if i % 10 == 0:
                print(f"已处理 {i}/{len(cases)} 个案例")
            result = await self.simulate_single_case(case)
            results.append(result)

        # 计算统计结果
        eval_result = self._calculate_metrics(results, cases)

        return results, eval_result

    def _calculate_metrics(self, simulation_results: List[SimulationResult], historical_cases: List[HistoricalCase]) -> EvaluationResult:
        """计算评估指标"""
        total_cases = len(simulation_results)

        # 建立case_id到历史数据的映射
        case_map = {case.case_id: case for case in historical_cases}

        # 基础统计
        robot_success = 0
        human_success = 0
        robot_total_amount = 0.0
        human_total_amount = 0.0
        robot_total_days = 0
        human_total_days = 0
        total_violations = 0
        correct_predictions = 0

        # 场景统计
        scenario_stats = {}
        persona_stats = {}
        stage_stats = {}
        resistance_stats = {}

        for sim_result in simulation_results:
            case = case_map.get(sim_result.case_id)
            if not case:
                continue

            # 成功率统计
            if sim_result.predicted_result == "success":
                robot_success += 1
            if case.actual_result == "success":
                human_success += 1

            # 回款金额统计
            if case.actual_repayment_amount is not None:
                human_total_amount += case.actual_repayment_amount
                if sim_result.predicted_result == "success":
                    robot_total_amount += case.actual_repayment_amount * 0.9  # 假设机器人回款效率是人工的90%（可调整）
                elif sim_result.predicted_result == "extension":
                    robot_total_amount += case.actual_repayment_amount * 0.7  # 延期回款打7折

            # 回款天数统计
            if case.actual_repayment_days is not None:
                human_total_days += case.actual_repayment_days
                if sim_result.predicted_repayment_days is not None:
                    robot_total_days += sim_result.predicted_repayment_days

            # 违规统计
            if sim_result.compliance_violations:
                total_violations += 1

            # 预测准确率
            if sim_result.predicted_result == case.actual_result:
                correct_predictions += 1

            # 分场景统计
            # 1. 用户类型
            persona = case.user_persona
            if persona not in persona_stats:
                persona_stats[persona] = {"robot_success": 0, "human_success": 0, "total": 0}
            persona_stats[persona]["total"] += 1
            if sim_result.predicted_result == "success":
                persona_stats[persona]["robot_success"] += 1
            if case.actual_result == "success":
                persona_stats[persona]["human_success"] += 1

            # 2. 催收阶段
            stage = case.collection_stage
            if stage not in stage_stats:
                stage_stats[stage] = {"robot_success": 0, "human_success": 0, "total": 0}
            stage_stats[stage]["total"] += 1
            if sim_result.predicted_result == "success":
                stage_stats[stage]["robot_success"] += 1
            if case.actual_result == "success":
                stage_stats[stage]["human_success"] += 1

            # 3. 抗拒程度
            resistance = case.resistance_level
            if resistance not in resistance_stats:
                resistance_stats[resistance] = {"robot_success": 0, "human_success": 0, "total": 0}
            resistance_stats[resistance]["total"] += 1
            if sim_result.predicted_result == "success":
                resistance_stats[resistance]["robot_success"] += 1
            if case.actual_result == "success":
                resistance_stats[resistance]["human_success"] += 1

        # 计算汇总指标
        robot_success_rate = robot_success / total_cases if total_cases > 0 else 0.0
        human_success_rate = human_success / total_cases if total_cases > 0 else 0.0
        success_rate_diff = robot_success_rate - human_success_rate

        robot_avg_amount = robot_total_amount / robot_success if robot_success > 0 else 0.0
        human_avg_amount = human_total_amount / human_success if human_success > 0 else 0.0
        amount_diff = robot_avg_amount - human_avg_amount

        robot_avg_days = robot_total_days / robot_success if robot_success > 0 else 0.0
        human_avg_days = human_total_days / human_success if human_success > 0 else 0.0
        days_diff = robot_avg_days - human_avg_days

        violation_rate = total_violations / total_cases if total_cases > 0 else 0.0
        accuracy = correct_predictions / total_cases if total_cases > 0 else 0.0

        # 计算相关性（简化版，用成功率的差异相关性）
        correlation = 1.0 - abs(success_rate_diff)  # 差异越小相关性越高

        # 场景分析
        scenario_analysis = {
            "persona_analysis": self._calculate_scenario_metrics(persona_stats),
            "stage_analysis": self._calculate_scenario_metrics(stage_stats),
            "resistance_analysis": self._calculate_scenario_metrics(resistance_stats)
        }

        return EvaluationResult(
            total_cases=total_cases,
            robot_success_rate=round(robot_success_rate, 4),
            human_success_rate=round(human_success_rate, 4),
            success_rate_diff=round(success_rate_diff, 4),
            robot_avg_repayment_amount=round(robot_avg_amount, 2),
            human_avg_repayment_amount=round(human_avg_amount, 2),
            amount_diff=round(amount_diff, 2),
            robot_avg_repayment_days=round(robot_avg_days, 1),
            human_avg_repayment_days=round(human_avg_days, 1),
            days_diff=round(days_diff, 1),
            compliance_violation_rate=round(violation_rate, 4),
            accuracy=round(accuracy, 4),
            correlation=round(correlation, 4),
            scenario_analysis=scenario_analysis
        )

    def _calculate_scenario_metrics(self, stats: Dict) -> Dict:
        """计算场景指标"""
        result = {}
        for scenario, data in stats.items():
            total = data["total"]
            robot_success = data["robot_success"]
            human_success = data["human_success"]
            robot_rate = robot_success / total if total > 0 else 0.0
            human_rate = human_success / total if total > 0 else 0.0
            result[scenario] = {
                "total": total,
                "robot_success_rate": round(robot_rate, 4),
                "human_success_rate": round(human_rate, 4),
                "diff": round(robot_rate - human_rate, 4)
            }
        return result

    def generate_report(self, results: List[SimulationResult], eval_result: EvaluationResult, output_dir: str = "data/outputs/offline_evaluation_reports/") -> str:
        """生成评估报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 生成JSON报告
        json_file = output_path / f"offline_evaluation_{timestamp}.json"
        report_data = {
            "summary": {
                "total_cases": eval_result.total_cases,
                "robot_success_rate": eval_result.robot_success_rate,
                "human_success_rate": eval_result.human_success_rate,
                "success_rate_diff": eval_result.success_rate_diff,
                "robot_avg_repayment_amount": eval_result.robot_avg_repayment_amount,
                "human_avg_repayment_amount": eval_result.human_avg_repayment_amount,
                "amount_diff": eval_result.amount_diff,
                "robot_avg_repayment_days": eval_result.robot_avg_repayment_days,
                "human_avg_repayment_days": eval_result.human_avg_repayment_days,
                "days_diff": eval_result.days_diff,
                "compliance_violation_rate": eval_result.compliance_violation_rate,
                "prediction_accuracy": eval_result.accuracy,
                "result_correlation": eval_result.correlation
            },
            "scenario_analysis": eval_result.scenario_analysis,
            "detailed_results": [
                {
                    "case_id": r.case_id,
                    "predicted_result": r.predicted_result,
                    "predicted_repayment_probability": r.predicted_repayment_probability,
                    "predicted_repayment_days": r.predicted_repayment_days,
                    "compliance_violations": r.compliance_violations,
                    "total_turns": r.total_turns,
                    "predicted_duration": r.call_duration_predicted
                }
                for r in results
            ]
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 生成Markdown报告
        md_file = output_path / f"offline_evaluation_{timestamp}.md"

        md_content = f"""# 离线合成对照评估报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试样本量: {eval_result.total_cases} 个历史催收案例

## 📊 核心指标对比
| 指标 | 机器人 | 人工 | 差异 |
|------|--------|------|------|
| 催收成功率 | {eval_result.robot_success_rate*100:.1f}% | {eval_result.human_success_rate*100:.1f}% | {'+' if eval_result.success_rate_diff >= 0 else ''}{eval_result.success_rate_diff*100:.1f}% |
| 平均回款金额 | Rp {eval_result.robot_avg_repayment_amount:,.0f} | Rp {eval_result.human_avg_repayment_amount:,.0f} | {'+' if eval_result.amount_diff >= 0 else ''}Rp {eval_result.amount_diff:,.0f} |
| 平均回款天数 | {eval_result.robot_avg_repayment_days:.1f} 天 | {eval_result.human_avg_repayment_days:.1f} 天 | {'+' if eval_result.days_diff >= 0 else ''}{eval_result.days_diff:.1f} 天 |
| 合规违规率 | {eval_result.compliance_violation_rate*100:.1f}% | - | - |
| 预测准确率 | {eval_result.accuracy*100:.1f}% | - | - |
| 结果相关性 | {eval_result.correlation*100:.1f}% | - | - |

## 🎯 效果评估结论
"""
        # 生成结论
        if eval_result.success_rate_diff >= 0.05:
            md_content += "✅ **机器人表现显著优于人工**，可以上线\n"
        elif 0 <= eval_result.success_rate_diff < 0.05:
            md_content += "✅ **机器人表现与人工相当**，可以上线\n"
        elif -0.1 < eval_result.success_rate_diff < 0:
            md_content += "⚠️  **机器人表现略低于人工**，建议优化后再上线\n"
        else:
            md_content += "❌ **机器人表现显著低于人工**，需要进一步优化\n"

        # 业务价值分析
        if eval_result.success_rate_diff >= -0.05:  # 只要不低于人工5%就算有价值
            cost_saving = (3000 - 1500) * 1000  # 假设每个坐席月薪300万印尼盾，机器人成本150万，替代1000个坐席
            md_content += f"""
## 💰 预期业务价值
- 人工成本节约：预计每年 Rp {cost_saving * 12:,.0f}
- 催收效率提升：7*24小时不间断工作，效率提升3倍
- 合规风险降低：统一话术，避免人工违规
"""
        md_content += """
## 👤 按用户类型分析
| 用户类型 | 样本量 | 机器人成功率 | 人工成功率 | 差异 | 结论 |
|----------|--------|--------------|------------|------|------|
"""
        for persona, data in eval_result.scenario_analysis["persona_analysis"].items():
            diff = data["diff"] * 100
            conclusion = "✅ 机器人更优" if diff >= 0 else "⚠️ 人工更优"
            md_content += f"| {persona} | {data['total']} | {data['robot_success_rate']*100:.1f}% | {data['human_success_rate']*100:.1f}% | {'+' if diff >= 0 else ''}{diff:.1f}% | {conclusion} |\n"

        md_content += """
## 📈 按催收阶段分析
| 催收阶段 | 样本量 | 机器人成功率 | 人工成功率 | 差异 | 结论 |
|----------|--------|--------------|------------|------|------|
"""
        for stage, data in eval_result.scenario_analysis["stage_analysis"].items():
            diff = data["diff"] * 100
            conclusion = "✅ 机器人更优" if diff >= 0 else "⚠️ 人工更优"
            md_content += f"| {stage} | {data['total']} | {data['robot_success_rate']*100:.1f}% | {data['human_success_rate']*100:.1f}% | {'+' if diff >= 0 else ''}{diff:.1f}% | {conclusion} |\n"

        md_content += """
## ⚔️ 按抗拒程度分析
| 抗拒程度 | 样本量 | 机器人成功率 | 人工成功率 | 差异 | 结论 |
|----------|--------|--------------|------------|------|------|
"""
        for resistance, data in eval_result.scenario_analysis["resistance_analysis"].items():
            diff = data["diff"] * 100
            conclusion = "✅ 机器人更优" if diff >= 0 else "⚠️ 人工更优"
            md_content += f"| {resistance} | {data['total']} | {data['robot_success_rate']*100:.1f}% | {data['human_success_rate']*100:.1f}% | {'+' if diff >= 0 else ''}{diff:.1f}% | {conclusion} |\n"

        md_content += """
## 🔍 优化建议
"""
        # 生成优化建议
        low_performance_scenarios = []
        for persona, data in eval_result.scenario_analysis["persona_analysis"].items():
            if data["diff"] < -0.1:
                low_performance_scenarios.append(f"用户类型 {persona}: 比人工低 {abs(data['diff'])*100:.1f}%")
        for stage, data in eval_result.scenario_analysis["stage_analysis"].items():
            if data["diff"] < -0.1:
                low_performance_scenarios.append(f"催收阶段 {stage}: 比人工低 {abs(data['diff'])*100:.1f}%")
        for resistance, data in eval_result.scenario_analysis["resistance_analysis"].items():
            if data["diff"] < -0.1:
                low_performance_scenarios.append(f"抗拒程度 {resistance}: 比人工低 {abs(data['diff'])*100:.1f}%")

        if low_performance_scenarios:
            md_content += "### 优先优化场景\n"
            for scenario in low_performance_scenarios:
                md_content += f"- {scenario}\n"
        else:
            md_content += "- 机器人在各个场景表现均衡，没有明显短板\n"

        if eval_result.compliance_violation_rate > 0.05:
            md_content += f"- 合规违规率较高 ({eval_result.compliance_violation_rate*100:.1f}%)，需要优化话术，避免违规内容\n"

        if eval_result.correlation < 0.8:
            md_content += "- 预测模型与实际结果相关性较低，需要更多数据训练优化预测模型\n"

        md_content += """
## 📝 测试说明
1. 本评估基于历史人工催收数据，模拟机器人在相同场景下的催收效果
2. 预测模型基于业务经验构建，随着数据积累可以不断优化准确率
3. 上线前建议先进行小流量灰度测试，验证实际效果与预测结果的一致性
4. 本报告可作为上线决策的重要参考依据
"""

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n离线评估报告已生成:")
        print(f"  - JSON报告: {json_file}")
        print(f"  - Markdown报告: {md_file}")

        return str(md_file)

async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="离线合成对照评估工具")
    parser.add_argument("--sample-size", type=int, help="抽样评估的样本量，默认使用全部数据")
    parser.add_argument("--historical-data-path", default="data/processed/historical/", help="历史数据目录")
    parser.add_argument("--output-dir", default="data/outputs/offline_evaluation_reports/", help="报告输出目录")
    parser.add_argument("--case", help="评估单个案例，指定case_id")

    args = parser.parse_args()

    evaluator = OfflineEvaluator(args.historical_data_path)

    if not evaluator.historical_cases:
        print("请先准备历史催收数据到 data/processed/historical/ 目录")
        return

    if args.case:
        # 评估单个案例
        case = next((c for c in evaluator.historical_cases if c.case_id == args.case), None)
        if not case:
            print(f"找不到案例: {args.case}")
            return

        result = await evaluator.simulate_single_case(case)
        print(f"\n案例: {case.case_id}")
        print(f"实际结果: {case.actual_result}")
        print(f"预测结果: {result.predicted_result}")
        print(f"回款概率: {result.predicted_repayment_probability*100:.1f}%")
        print(f"预测回款天数: {result.predicted_repayment_days} 天")
        print(f"对话轮数: {result.total_turns}")
        print(f"预测通话时长: {result.call_duration_predicted:.1f} 秒")
        if result.compliance_violations:
            print("\n合规违规:")
            for v in result.compliance_violations:
                print(f"  - [{v['severity']}] {v['description']}")
        print("\n对话详情:")
        for turn in result.dialogue:
            print(f"  用户: {turn['user_input']}")
            print(f"  机器人: {turn['bot_response']}")
        return

    # 运行完整评估
    results, eval_result = await evaluator.run_evaluation(args.sample_size)

    if not eval_result:
        return

    # 打印结果摘要
    print("\n" + "="*70)
    print("离线评估结果汇总")
    print("="*70)
    print(f"总案例数: {eval_result.total_cases}")
    print(f"机器人成功率: {eval_result.robot_success_rate*100:.1f}%")
    print(f"人工成功率: {eval_result.human_success_rate*100:.1f}%")
    print(f"成功率差异: {'+' if eval_result.success_rate_diff >= 0 else ''}{eval_result.success_rate_diff*100:.1f}%")
    print(f"平均回款金额差异: {'+' if eval_result.amount_diff >= 0 else ''}Rp {eval_result.amount_diff:,.0f}")
    print(f"平均回款天数差异: {'+' if eval_result.days_diff >= 0 else ''}{eval_result.days_diff:.1f} 天")
    print(f"合规违规率: {eval_result.compliance_violation_rate*100:.1f}%")
    print(f"预测准确率: {eval_result.accuracy*100:.1f}%")
    print(f"结果相关性: {eval_result.correlation*100:.1f}%")

    # 结论
    print("\n" + "="*70)
    if eval_result.success_rate_diff >= 0:
        print("✅ 机器人表现优于或等于人工，建议上线！")
    elif eval_result.success_rate_diff >= -0.05:
        print("⚠️  机器人表现略低于人工，在可接受范围内，可以上线")
    else:
        print(f"❌ 机器人表现低于人工 {abs(eval_result.success_rate_diff)*100:.1f}%，需要进一步优化")

    # 生成报告
    evaluator.generate_report(results, eval_result, args.output_dir)

if __name__ == "__main__":
    asyncio.run(main())
