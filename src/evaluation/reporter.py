"""组件4: 双轨评估报告器 — 聚合+冲突检测+历史追踪"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class EvalReporter:
    """聚合模拟器 + 校准模型双轨信号，生成结构化评测报告"""

    def __init__(self, history_path: Optional[Path] = None):
        if history_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            history_path = project_root / "data" / "evaluations" / "history.jsonl"
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        change_name: str,
        sim_result: dict,
        model_result: dict,
        quality: dict,
    ) -> str:
        """生成完整评测报告，返回 Markdown 格式字符串"""

        sim_delta = sim_result.get("delta", 0.0)
        model_delta = model_result.get("delta_mean", 0.0)

        conflict, pattern, recommendation = self._detect_conflict(
            sim_delta, model_delta, model_result.get("p_value", 1.0))

        lines = [
            f"# 策略评测报告 — {change_name}",
            f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## A. 一页纸结论",
            "",
            f"| 指标 | 方案A (旧) | 方案B (新) | Δ |",
            f"|------|-----------|-----------|---|",
            f"| 模拟器承诺率 | {sim_result.get('commit_rate_a', 0):.1%} | {sim_result.get('commit_rate_b', 0):.1%} | {sim_delta:+.1%} |",
            f"| 模型 P(repay) | {model_result.get('repay_prob_a', 0):.2f} | {model_result.get('repay_prob_b', 0):.2f} | {model_delta:+.2f} |",
            f"| 冲突状态 | {pattern} | | |",
            f"| 模型 AUC: {quality.get('auc', 0):.3f} | ECE: {quality.get('ece', 0):.3f} | | |",
            "",
            f"**研判建议**: {recommendation}",
            "",
        ]

        if "by_segment" in sim_result:
            lines.append("## B. 模拟器分群明细")
            lines.append("")
            lines.append("| 客群 | A(旧) | B(新) | Δ |")
            lines.append("|------|-------|-------|---|")
            for seg, (a, b) in sim_result["by_segment"].items():
                lines.append(f"| {seg} | {a:.1%} | {b:.1%} | {b-a:+.1%} |")
            lines.append("")

        lines.extend([
            "## D. 冲突研判",
            "",
            f"- **信号模式**: {pattern}",
            f"- **模拟器 Δ**: {sim_delta:+.1%}",
            f"- **模型 Δ**: {model_delta:+.2f} (p={model_result.get('p_value', 1):.3f})",
            f"- **建议**: {recommendation}",
            "",
        ])

        self._append_history(change_name, sim_delta, model_delta, conflict, pattern)

        return "\n".join(lines)

    def _detect_conflict(
        self, sim_delta: float, model_delta: float, p_value: float,
    ) -> tuple:
        """返回 (is_conflict, pattern_name, recommendation)"""
        eps = 0.01
        sim_up = sim_delta > eps
        sim_down = sim_delta < -eps
        model_up = model_delta > eps
        model_down = model_delta < -eps

        if sim_up and model_up:
            return (False, "双升 ✓✓",
                    "置信度高，建议采纳。检查分群明细是否有负向交叉（如新客升但老客降），如有则微调参数。")
        elif sim_up and not (model_up or model_down):
            return (True, "模拟器升·模型平 ✗",
                    "可能 reward hacking — 策略优化了应对模拟器而非真实行为。建议用 PSI 检查模拟器生成的对话分布是否偏离训练数据。")
        elif model_up and not (sim_up or sim_down):
            return (True, "模型升·模拟器平 ✗",
                    "模拟器可能缺少对应行为档案。建议检查该策略改动针对的客户类型是否在档案中有覆盖。")
        elif sim_down and model_down:
            return (True, "双降 ✗✗",
                    "清晰负面信号，建议回滚。如改动有强业务理由（如合规要求），保留但显式标记降幅。")
        elif sim_up and model_down:
            return (True, "信号背离 ✗",
                    "罕见情况 — 模拟器和模型完全相反。暂停推进，排查：(1) 模拟器档案是否匹配目标场景；(2) 模型训练数据是否覆盖此类策略参数范围。")
        elif sim_down and model_up:
            return (True, "信号背离 ✗",
                    "罕见情况 — 与上条同理，建议全面排查后再决策。")
        else:
            return (False, "双平 ==", "无显著变化，改动可能无效或被噪声淹没。")

    def _append_history(
        self, change_name: str, sim_delta: float, model_delta: float,
        conflict: bool, pattern: str,
    ):
        """追加一条历史记录"""
        record = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "change": change_name,
            "sim_delta": round(sim_delta, 4),
            "model_delta": round(model_delta, 4),
            "conflict": conflict,
            "pattern": pattern,
        }
        with open(self.history_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def get_history(self, limit: int = 20) -> list[dict]:
        """读取最近 N 条历史记录"""
        if not self.history_path.exists():
            return []
        records = []
        with open(self.history_path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records[-limit:]
