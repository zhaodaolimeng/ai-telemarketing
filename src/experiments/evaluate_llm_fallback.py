#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Fallback 边界场景效果对比评估 (P14-08)
对比三种方案在边界场景下的成功率、合规率、延迟:
  A: 纯规则 (无 LLM, 无 ML 分类器)
  B: 规则 + ML 分类器降级
  C: 规则 + LLM Fallback (四级降级链)
"""
import sys
import asyncio
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, ChatState
from core.compliance_checker import get_compliance_checker


# ============================================================
# 边界场景定义
# ============================================================

@dataclass
class BoundaryScenario:
    """边界测试场景"""
    scenario_id: str
    name: str
    description: str
    chat_group: str
    customer_name: str
    customer_inputs: List[str]  # 客户回复序列
    expected_time: Optional[str] = None  # 期望的还款时间
    difficult_round: int = -1  # 最困难的轮次 (0-indexed)
    failure_modes: List[str] = field(default_factory=list)  # 预测的失败模式


BOUNDARY_SCENARIOS = [
    BoundaryScenario(
        scenario_id="B-001",
        name="混合抗拒",
        description="客户提出多重困难: 生病+没钱+忘记日期",
        chat_group="H2",
        customer_name="Pak Budi",
        customer_inputs=[
            "Halo, selamat pagi",
            "Iya, ini saya sendiri",
            "Waduh, saya lagi sakit sekarang, belum ada uang juga. Lupa lagi tanggal berapa harus bayar.",
            "Iya deh, mungkin nanti jam 3 sore saya coba transfer.",
            "Iya, saya janji.",
        ],
        expected_time="jam 3 sore",
        difficult_round=2,
        failure_modes=["unknown", "repeat_question"],
    ),
    BoundaryScenario(
        scenario_id="B-002",
        name="话题偏离",
        description="客户一直谈论与还款无关的话题(家庭问题)",
        chat_group="H1",
        customer_name="Bu Siti",
        customer_inputs=[
            "Halo",
            "Iya betul, ini saya",
            "Anak saya lagi ujian, suami saya lagi keluar kota. Saya pusing mikirin ini semua.",
            "Belum tau deh kapan bisa bayar, lagi banyak masalah keluarga.",
            "Maaf ya, saya lagi banyak pikiran. Nanti saya coba bayar jam 4 sore deh.",
        ],
        expected_time="jam 4 sore",
        difficult_round=2,
        failure_modes=["irrelevant_response", "no_time_detected"],
    ),
    BoundaryScenario(
        scenario_id="B-003",
        name="模糊短回复",
        description="客户持续只用一两个词回复, 不给明确时间",
        chat_group="H2",
        customer_name="Pak Agus",
        customer_inputs=[
            "Pagi",
            "Iya",
            "Mungkin",
            "Gak tau",
            "Entah",
            "Nanti aja",
            "Jam 5 deh",
        ],
        expected_time="jam 5",
        difficult_round=2,
        failure_modes=["too_short", "unknown", "looping"],
    ),
    BoundaryScenario(
        scenario_id="B-004",
        name="情绪爆发",
        description="客户突然发怒, 使用激烈言辞后平静下来",
        chat_group="S0",
        customer_name="Pak Rudi",
        customer_inputs=[
            "Halo? Siapa ini?",
            "Oh dari Extra...",
            "KALIAN TELEPON TERUS! SAYA JUGA PUNYA KESULITAN! JANGAN GANGGU SAYA TERUS!",
            "...(hening)...",
            "Maaf tadi emosi. Saya lagi stress.",
            "Iya, nanti jam 2 siang saya bayar.",
        ],
        expected_time="jam 2 siang",
        difficult_round=2,
        failure_modes=["emotional_response", "hangup_too_early"],
    ),
    BoundaryScenario(
        scenario_id="B-005",
        name="砍价协商",
        description="客户不直接说时间, 而是反复砍价/要求减免",
        chat_group="H1",
        customer_name="Bu Dewi",
        customer_inputs=[
            "Halo, iya ini saya",
            "Bunganya bisa dikurangi gak? Saya cuma bisa bayar setengahnya.",
            "Kalau gak bisa ya saya gak bayar dulu. Lagian bunganya tinggi banget.",
            "Ya udah deh, saya bayar jam 6 sore nanti. Tapi jangan telpon-telpon terus ya.",
        ],
        expected_time="jam 6 sore",
        difficult_round=1,
        failure_modes=["negotiation_rejected", "no_alternative"],
    ),
    BoundaryScenario(
        scenario_id="B-006",
        name="错误号码",
        description="客户声称打错了/不认识借款人",
        chat_group="H2",
        customer_name="Pak Hendra",
        customer_inputs=[
            "Halo?",
            "Saya gak kenal siapa yang kamu cari. Salah nomor ini.",
            "Saya bilang salah nomor! Jangan telepon lagi!",
            "Iya terserah, saya gak mau tau.",
        ],
        expected_time=None,
        difficult_round=1,
        failure_modes=["wrong_number", "continued_harassment"],
    ),
    BoundaryScenario(
        scenario_id="B-007",
        name="请求重组",
        description="客户主动请求债务重组/延期",
        chat_group="S0",
        customer_name="Pak Dedi",
        customer_inputs=[
            "Halo pak",
            "Iya benar, ini saya",
            "Saya mau jujur, kondisi keuangan saya lagi sulit. Apa bisa diangsur? Atau ada kebijakan restrukturisasi?",
            "Kalau bisa diangsur 3 kali, saya bisa mulai bayar minggu depan.",
            "Baik, saya setuju. Nanti akan saya transfer yang pertama jam 10 pagi hari Senin.",
        ],
        expected_time="jam 10 pagi hari Senin",
        difficult_round=2,
        failure_modes=["no_restructuring_info", "missed_commitment"],
    ),
    BoundaryScenario(
        scenario_id="B-008",
        name="多轮沉默",
        description="客户连续多轮不说话后突然给时间",
        chat_group="H2",
        customer_name="Bu Fitri",
        customer_inputs=[
            "Halo",
            "Iya",
            "...",
            "...",
            "Jam 4 sore ya.",
        ],
        expected_time="jam 4 sore",
        difficult_round=2,
        failure_modes=["silence_timeout", "hangup_on_silence"],
    ),
    BoundaryScenario(
        scenario_id="B-009",
        name="信息纠错",
        description="客户纠正机器人错误信息(金额/日期)",
        chat_group="H1",
        customer_name="Pak Andi",
        customer_inputs=[
            "Halo, selamat siang",
            "Iya ini saya",
            "Tunggu, jumlah pinjaman saya bukan 10 juta, tapi cuma 5 juta. Dan jatuh temponya tanggal 20, bukan tanggal 15.",
            "Iya betul. Saya transfer jam 8 malam tanggal 20 ya.",
        ],
        expected_time="jam 8 malam tanggal 20",
        difficult_round=2,
        failure_modes=["wrong_info_not_corrected", "confidence_loss"],
    ),
    BoundaryScenario(
        scenario_id="B-010",
        name="第三方接听",
        description="接电话的不是本人而是家属",
        chat_group="H2",
        customer_name="Pak Tono",
        customer_inputs=[
            "Halo?",
            "Ini istrinya. Suami saya lagi keluar.",
            "Saya kurang tau soal pinjaman. Nanti saya sampaikan ya.",
            "Baik, nanti suami saya yang hubungi balik. Jam 5 sore dia pulang.",
        ],
        expected_time="jam 5 sore",
        difficult_round=1,
        failure_modes=["privacy_violation", "wrong_persona"],
    ),
]


# ============================================================
# 评测运行器
# ============================================================

@dataclass
class EvalResult:
    """单个场景的评测结果"""
    scenario_id: str
    scenario_name: str
    approach: str  # "rule_only" | "rule_ml" | "rule_llm"
    success: bool
    compliant: bool
    total_turns: int
    latency_ms: List[float] = field(default_factory=list)
    llm_turns_used: int = 0
    final_state: str = ""
    commit_time: Optional[str] = None
    violations: List[Dict] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_ms:
            return 0.0
        return sum(self.latency_ms) / len(self.latency_ms)


class FallbackEvaluator:
    """LLM Fallback 效果对比评估器"""

    def __init__(self):
        self.results: List[EvalResult] = []
        self.checker = get_compliance_checker()

    async def run_scenario(
        self, scenario: BoundaryScenario, approach: str
    ) -> EvalResult:
        """用指定方案运行一个边界场景"""
        bot = CollectionChatBot(scenario.chat_group, scenario.customer_name)

        # 按方案配置 bot
        if approach == "rule_llm":
            bot.enable_llm_fallback()
        elif approach == "rule_ml":
            # 仅 ML 分类器，不启用 LLM
            bot.enable_ml_classifier = True
        # rule_only: 默认配置，不使用 LLM 和 ML

        latencies = []
        llm_turns = 0
        all_violations = []

        try:
            # 初始问候
            t0 = time.perf_counter()
            agent, _ = await bot.process()
            latencies.append((time.perf_counter() - t0) * 1000)

            # 逐轮对话
            for i, customer_input in enumerate(scenario.customer_inputs):
                t0 = time.perf_counter()
                agent, _ = await bot.process(customer_input)
                latencies.append((time.perf_counter() - t0) * 1000)

                if bot.llm_used_this_turn:
                    llm_turns += 1
                    bot.llm_used_this_turn = False  # 重置标志

                # 收集合规违规
                if agent:
                    _, violations = self.checker.check(agent)
                    all_violations.extend(violations)

                if bot.is_finished():
                    break

            # 检查整体合规性
            has_high = any(v["severity"] == "high" for v in all_violations)
            compliant = not has_high

            return EvalResult(
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.name,
                approach=approach,
                success=bot.is_successful(),
                compliant=compliant,
                total_turns=len(bot.conversation),
                latency_ms=latencies,
                llm_turns_used=llm_turns,
                final_state=bot.state.name if bot.state else "",
                commit_time=bot.commit_time,
                violations=[{"rule_id": v["rule_id"], "severity": v["severity"]}
                            for v in all_violations],
            )

        except Exception as e:
            return EvalResult(
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.name,
                approach=approach,
                success=False,
                compliant=False,
                total_turns=0,
                latency_ms=latencies,
                error=str(e),
            )

    async def run_all(self) -> Dict:
        """运行所有场景 × 所有方案的对比测试"""
        approaches = [
            ("rule_only", "纯规则"),
            ("rule_llm", "规则+LLM"),
        ]

        print(f"开始对比评估: {len(BOUNDARY_SCENARIOS)} 个场景 × {len(approaches)} 种方案")
        print("=" * 70)

        for scenario in BOUNDARY_SCENARIOS:
            print(f"\n📋 {scenario.scenario_id} {scenario.name}: {scenario.description}")
            for approach_key, approach_label in approaches:
                result = await self.run_scenario(scenario, approach_key)
                self.results.append(result)
                icon = "✓" if result.success else "✗"
                llm_info = f", LLM轮次={result.llm_turns_used}" if approach_key == "rule_llm" else ""
                print(f"  {icon} {approach_label}: "
                      f"success={result.success}, compliant={result.compliant}, "
                      f"turns={result.total_turns}, avg_lat={result.avg_latency_ms:.0f}ms"
                      f"{llm_info}")
                if result.error:
                    print(f"    ⚠️ 错误: {result.error}")

        return self._build_summary()

    def _build_summary(self) -> Dict:
        """构建汇总对比"""
        approaches = ["rule_only", "rule_llm"]
        labels = {"rule_only": "纯规则", "rule_llm": "规则+LLM"}
        summary = {}

        for approach in approaches:
            subset = [r for r in self.results if r.approach == approach]
            if not subset:
                continue

            success_count = sum(1 for r in subset if r.success)
            compliant_count = sum(1 for r in subset if r.compliant)
            total = len(subset)
            latencies = [r.avg_latency_ms for r in subset if r.latency_ms]
            llm_turns = sum(r.llm_turns_used for r in subset)

            summary[approach] = {
                "label": labels[approach],
                "success_rate": round(success_count / total * 100, 1),
                "compliance_rate": round(compliant_count / total * 100, 1),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "total_turns": sum(r.total_turns for r in subset),
                "avg_turns": round(sum(r.total_turns for r in subset) / total, 1),
                "llm_turns_used": llm_turns,
                "errors": sum(1 for r in subset if r.error),
            }

        return summary

    def generate_report(self, summary: Dict, output_dir: Optional[str] = None) -> str:
        """生成对比评估报告"""
        if output_dir is None:
            output_dir = Path("data/llm_fallback_evals")
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # ---- JSON 报告 ----
        json_file = output_dir / f"llm_fallback_eval_{timestamp}.json"
        report_data = {
            "meta": {
                "test_time": datetime.now().isoformat(),
                "num_scenarios": len(BOUNDARY_SCENARIOS),
                "num_approaches": 2,
                "version": "1.0",
            },
            "summary": summary,
            "detailed_results": [
                {
                    "scenario_id": r.scenario_id,
                    "scenario_name": r.scenario_name,
                    "approach": r.approach,
                    "success": r.success,
                    "compliant": r.compliant,
                    "total_turns": r.total_turns,
                    "avg_latency_ms": round(r.avg_latency_ms, 1),
                    "llm_turns_used": r.llm_turns_used,
                    "final_state": r.final_state,
                    "commit_time": r.commit_time,
                    "violations": r.violations,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # ---- Markdown 报告 ----
        md_file = output_dir / f"llm_fallback_eval_{timestamp}.md"
        rl = summary.get("rule_only", {})
        ll = summary.get("rule_llm", {})

        md = f"""# LLM Fallback 边界场景效果对比评估

**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试场景:** {len(BOUNDARY_SCENARIOS)} 个边界场景
**对比方案:** 纯规则 vs 规则+LLM (四级降级链)

---

## 📊 总体对比

| 指标 | 纯规则 | 规则+LLM | 提升 |
|------|--------|----------|------|
| 成功率 | {rl.get('success_rate', 0)}% | {ll.get('success_rate', 0)}% | +{round(ll.get('success_rate', 0) - rl.get('success_rate', 0), 1)}% |
| 合规率 | {rl.get('compliance_rate', 0)}% | {ll.get('compliance_rate', 0)}% | +{round(ll.get('compliance_rate', 0) - rl.get('compliance_rate', 0), 1)}% |
| 平均延迟 | {rl.get('avg_latency_ms', 0)}ms | {ll.get('avg_latency_ms', 0)}ms | {round(ll.get('avg_latency_ms', 0) - rl.get('avg_latency_ms', 0), 1)}ms |
| 平均轮次 | {rl.get('avg_turns', 0)} | {ll.get('avg_turns', 0)} | {round(ll.get('avg_turns', 0) - rl.get('avg_turns', 0), 1)} |
| LLM 调用次数 | - | {ll.get('llm_turns_used', 0)} | - |

### 关键发现

"""
        # 成功率分析
        success_diff = round(ll.get('success_rate', 0) - rl.get('success_rate', 0), 1)
        if success_diff > 10:
            md += f"- 🟢 **成功率大幅提升** (+{success_diff}%): LLM Fallback 在边界场景下显著提高了成功率\n"
        elif success_diff > 0:
            md += f"- 🟡 **成功率小幅提升** (+{success_diff}%): LLM Fallback 对部分边界场景有改善\n"
        elif success_diff == 0:
            md += "- ⚪ **成功率无变化**: LLM Fallback 未引入额外失败\n"
        else:
            md += f"- 🔴 **成功率下降** ({success_diff}%): 需排查 LLM Fallback 是否引入新问题\n"

        # 延迟分析
        latency_diff = round(ll.get('avg_latency_ms', 0) - rl.get('avg_latency_ms', 0), 1)
        if latency_diff > 200:
            md += f"- 🟠 **延迟增加** (+{latency_diff}ms): LLM 调用增加了响应延迟, 需关注用户体验\n"
        elif latency_diff > 0:
            md += f"- 🟡 **延迟小幅增加** (+{latency_diff}ms): 在可接受范围内\n"
        else:
            md += "- 🟢 **延迟无显著增加**: LLM 响应速度良好\n"

        # 合规分析
        if ll.get('compliance_rate', 0) >= 100:
            md += "- 🟢 **合规率 100%**: 合规后置过滤有效拦截了所有高风险内容\n"
        elif ll.get('compliance_rate', 0) >= rl.get('compliance_rate', 0):
            md += f"- 🟡 **合规率持平** ({ll.get('compliance_rate', 0)}%): LLM 未引入新的合规风险\n"

        md += f"""
---

## 📋 分场景详情

| 场景ID | 场景名称 | 纯规则 | 规则+LLM | LLM轮次 | 关键观察 |
|--------|----------|--------|----------|---------|----------|
"""
        # 按场景合并结果
        scene_results: Dict[str, Dict] = {}
        for r in self.results:
            if r.scenario_id not in scene_results:
                scene_results[r.scenario_id] = {}
            scene_results[r.scenario_id][r.approach] = r

        for scenario in BOUNDARY_SCENARIOS:
            sid = scenario.scenario_id
            sr = scene_results.get(sid, {})
            r_rule = sr.get("rule_only")
            r_llm = sr.get("rule_llm")

            rule_icon = "✅" if r_rule and r_rule.success else "❌"
            llm_icon = "✅" if r_llm and r_llm.success else "❌"
            llm_turns = r_llm.llm_turns_used if r_llm else 0

            # 关键观察
            observations = []
            if r_rule and r_llm:
                if not r_rule.success and r_llm.success:
                    observations.append("LLM 挽救失败")
                elif r_rule.success and not r_llm.success:
                    observations.append("⚠️ LLM 引入失败")
                if r_llm.llm_turns_used > 0:
                    observations.append(f"LLM调用{llm_turns}次")
            if r_llm and r_llm.commit_time:
                observations.append(f"时间={r_llm.commit_time}")

            md += (f"| {sid} | {scenario.name[:10]} | {rule_icon} | {llm_icon} | "
                   f"{llm_turns} | {'; '.join(observations) or '-'} |\n")

        md += f"""
---

## 🔍 失败场景分析

"""
        # 收集所有失败
        rule_failures = [r for r in self.results
                         if r.approach == "rule_only" and not r.success]
        llm_failures = [r for r in self.results
                        if r.approach == "rule_llm" and not r.success]

        if rule_failures:
            md += f"### 纯规则失败 ({len(rule_failures)}):\n"
            for r in rule_failures:
                md += f"- **{r.scenario_id} {r.scenario_name}**: state={r.final_state}"
                if r.violations:
                    md += f", violations={[v['rule_id'] for v in r.violations]}"
                md += "\n"

        if llm_failures:
            md += f"\n### 规则+LLM 失败 ({len(llm_failures)}):\n"
            for r in llm_failures:
                md += f"- **{r.scenario_id} {r.scenario_name}**: state={r.final_state}"
                if r.llm_turns_used > 0:
                    md += f", LLM已调用{r.llm_turns_used}次"
                if r.violations:
                    md += f", violations={[v['rule_id'] for v in r.violations]}"
                md += "\n"

        md += f"""
---

## 💡 结论与建议

1. **整体效果**: LLM Fallback 在 {len(BOUNDARY_SCENARIOS)} 个边界场景中,
   成功率从 {rl.get('success_rate', 0)}% {'提升' if success_diff >= 0 else '下降'}至 {ll.get('success_rate', 0)}%。
2. **延迟代价**: LLM 调用增加约 {abs(latency_diff)}ms 额外延迟, {'需要在生产环境中持续监控' if latency_diff > 100 else '在可接受范围内'}。
3. **合规保障**: 合规后置过滤{'有效' if ll.get('compliance_rate', 0) >= 100 else '基本'}保证了 LLM 输出的安全性。
4. **推荐策略**: {'建议在边界场景中优先启用 LLM Fallback' if success_diff > 0 else '需要进一步调优 LLM Fallback 触发策略和 prompt' if success_diff == 0 else '需要修复 LLM Fallback 引入的新问题后再启用'}。
"""

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md)

        print(f"\n📋 对比评估报告已生成:")
        print(f"  - JSON报告: {json_file}")
        print(f"  - Markdown报告: {md_file}")

        return str(md_file)


# ============================================================
# 主入口
# ============================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM Fallback 边界场景效果对比评估")
    parser.add_argument("--scenario", help="只运行指定场景ID")
    parser.add_argument("--output-dir", default=None, help="报告输出目录")
    args = parser.parse_args()

    evaluator = FallbackEvaluator()

    if args.scenario:
        scenario = next(
            (s for s in BOUNDARY_SCENARIOS if s.scenario_id == args.scenario), None
        )
        if not scenario:
            print(f"找不到场景: {args.scenario}")
            return 1

        print(f"单场景测试: {scenario.scenario_id} {scenario.name}")
        for approach in ["rule_only", "rule_llm"]:
            result = await evaluator.run_scenario(scenario, approach)
            evaluator.results.append(result)
            print(f"  {approach}: success={result.success}, "
                  f"compliant={result.compliant}, avg_lat={result.avg_latency_ms:.0f}ms")
    else:
        await evaluator.run_all()

    summary = evaluator._build_summary()
    evaluator.generate_report(summary, args.output_dir)

    # 打印汇总
    print("\n" + "=" * 70)
    print("评估完成")
    print("=" * 70)
    for approach, stats in summary.items():
        print(f"\n{stats['label']}:")
        print(f"  成功率: {stats['success_rate']}%")
        print(f"  合规率: {stats['compliance_rate']}%")
        print(f"  平均延迟: {stats['avg_latency_ms']}ms")
        print(f"  平均轮次: {stats['avg_turns']}")
        print(f"  LLM 调用次数: {stats['llm_turns_used']}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
