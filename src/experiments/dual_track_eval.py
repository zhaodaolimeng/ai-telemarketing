#!/usr/bin/env python3
"""
双轨策略对比评测 — 模拟器 + 校准模型双轨，冲突检测 + 研判建议

Usage:
  python3 src/experiments/dual_track_eval.py                          # 默认策略对比
  python3 src/experiments/dual_track_eval.py --name "轻推vs强硬"       # 自定义名称
  python3 src/experiments/dual_track_eval.py --list-history             # 查看历史记录
"""
import sys, json, argparse, re, random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import numpy as np
from evaluation.feature_extractor import DialogueFeatureExtractor, UserProfile
from evaluation.calibrator import RepaymentCalibrator
from evaluation.reporter import EvalReporter
from core.simulator import RealCustomerSimulatorV2, make_profiles

# ---------- 策略定义 ----------

STRATEGY_A = {  # 当前默认：温和引导
    "approach": "guide", "tone": "neutral", "push_intensity": 2,
    "extension_priority": False, "max_push_rounds": 3, "extension_fee_ratio": 0.25,
}

STRATEGY_B = {  # 增强 push：强硬催收
    "approach": "firm", "tone": "firm", "push_intensity": 4,
    "extension_priority": True, "max_push_rounds": 5, "extension_fee_ratio": 0.15,
}


def load_gold_cases(limit: int = 200) -> list[dict]:
    """从 gold_linkage 加载案例，返回 (case_info, dialogue_log, user_profile)"""
    linkage_path = PROJECT_ROOT / "data" / "gold_linkage.json"
    gd_path = PROJECT_ROOT / "data" / "gold_dataset"

    with open(linkage_path) as f:
        linkage = json.load(f)

    cases = []
    for case in linkage["linked_cases"]:
        if len(cases) >= limit:
            break
        file_path = gd_path / case["file"]
        if not file_path.exists():
            continue
        dialogue = json.loads(file_path.read_text()).get("dialogue", [])
        if not dialogue:
            continue

        customer_turns = [t for t in dialogue if t.get("speaker") == "customer"]
        _time_intents = {"agree_to_pay", "confirm_time", "give_time"}
        _has_commit = any(t.get("user_intent", "") in _time_intents for t in customer_turns)
        _commit_turn = next(
            (i for i, t in enumerate(customer_turns) if t.get("user_intent", "") in _time_intents), -1)

        log = {
            "turns": len(customer_turns),
            "push_count": 0,
            "silence_count": 0,
            "unknown_count": sum(1 for t in dialogue if t.get("user_intent") == "unknown"),
            "extension_offered": any(
                t.get("user_intent", "") in ("ask_extension", "agree_extension")
                for t in customer_turns),
            "got_commitment": _has_commit,
            "commitment_turn": _commit_turn,
            "objection_types": list(set(
                t.get("user_intent", "unknown") for t in customer_turns
                if t.get("user_intent", "unknown") != "unknown")),
            "final_state": "CLOSE",
            "cooperation_signals": sum(
                1 for t in customer_turns
                if t.get("user_intent", "") in ("agree_to_pay", "confirm_identity", "give_time")),
        }
        profile = UserProfile(
            new_flag=case.get("new_flag", 0),
            chat_group=case.get("chat_group", "H2"),
            repay_history=0.5,
        )
        cases.append({"case": case, "log": log, "profile": profile})
    return cases


def run_model_track(cases: list[dict], cal: RepaymentCalibrator) -> dict:
    """模型轨道: 两种策略 → 特征提取 → 校准模型预测 → 比较 P(repay)"""
    extractor = DialogueFeatureExtractor()
    feats_a = [extractor.extract(c["log"], c["profile"], STRATEGY_A) for c in cases]
    feats_b = [extractor.extract(c["log"], c["profile"], STRATEGY_B) for c in cases]

    X_a, X_b = np.array(feats_a), np.array(feats_b)
    proba_a = cal.model.predict_proba(X_a)[:, 1]
    proba_b = cal.model.predict_proba(X_b)[:, 1]
    compare = cal.compare(X_a, X_b)

    return {
        "repay_prob_a": round(float(np.mean(proba_a)), 3),
        "repay_prob_b": round(float(np.mean(proba_b)), 3),
        "delta_mean": compare["delta_mean"],
        "p_value": compare["p_value"],
        "significant": compare["significant"],
        "n_samples": len(cases),
    }


def run_simulator_track(profiles: dict, sim: RealCustomerSimulatorV2,
                        trials_per_profile: int = 30) -> dict:
    """模拟器轨道: 行为档案 × push深度 → 统计承诺率

    模拟 INIT → ASK_TIME → PUSH 流程。
    策略A: max 3轮push; 策略B: max 5轮push。
    """
    stages = ["greeting", "identity", "purpose", "ask_time"]
    total, commits_a, commits_b = 0, 0, 0
    by_segment = {}

    for pname, profile in profiles.items():
        ca, cb = 0, 0
        for _ in range(trials_per_profile):
            # 前置阶段 (共享)
            for stage in stages:
                sim.generate_response(stage, profile=profile, push_count=0)

            # 策略A push: 最多3轮
            for n in range(3):
                if _is_commit(sim.generate_response("push", profile=profile, push_count=n)):
                    ca += 1; break

            # 策略B push: 最多5轮
            for n in range(5):
                if _is_commit(sim.generate_response("push", profile=profile, push_count=n)):
                    cb += 1; break

        by_segment[profile.name] = (ca / trials_per_profile, cb / trials_per_profile)
        commits_a += ca; commits_b += cb; total += trials_per_profile

    return {
        "commit_rate_a": round(commits_a / total, 3),
        "commit_rate_b": round(commits_b / total, 3),
        "delta": round((commits_b - commits_a) / total, 3),
        "n_trials": total,
        "by_segment": by_segment,
    }


def _is_commit(resp: str) -> bool:
    if not resp or resp.strip() in ("", "...", "Iya", "Ya", "Hm", "Halo", "Oke"):
        return False
    return bool(re.search(r"jam\s*\d|besok|hari ini|nanti jam|siang|sore|minggu ini",
                          resp, re.IGNORECASE))


def main():
    parser = argparse.ArgumentParser(description="双轨策略对比评测")
    parser.add_argument("--name", default="baseline_vs_aggressive", help="策略变更名称")
    parser.add_argument("--cases", type=int, default=200, help="模型轨道评估案例数")
    parser.add_argument("--sim-trials", type=int, default=30, help="模拟器每档案试验次数")
    parser.add_argument("--list-history", action="store_true", help="查看历史记录")
    args = parser.parse_args()

    reporter = EvalReporter()

    if args.list_history:
        records = reporter.get_history(20)
        if not records:
            print("(暂无历史记录)")
        else:
            print(f"{'日期':<18} {'变更':<30} {'simΔ':>8} {'modelΔ':>8} {'冲突':>6}")
            print("-" * 72)
            for r in records:
                print(f"{r['date']:<18} {r['change']:<30} {r['sim_delta']:>+7.1%} "
                      f"{r['model_delta']:>+7.4f} {'⚠️' if r['conflict'] else '✓':>6}")
        return

    # 1. 加载校准模型
    model_path = PROJECT_ROOT / "data" / "evaluations" / "calibrator.pkl"
    if not model_path.exists():
        print("ERROR: 校准模型未训练。请先运行: python3 src/experiments/run_eval.py")
        return

    cal = RepaymentCalibrator()
    cal.load(model_path)
    qr = cal.quality_report()
    print(f"校准模型: AUC={qr['auc']:.3f} (门槛≥0.75: {'PASS' if qr['auc_pass'] else 'FAIL'})  "
          f"ECE={qr['ece']:.3f} (门槛≤0.10: {'PASS' if qr['ece_pass'] else 'FAIL'})")

    # 2. 模型轨道
    print(f"\n{'='*60}")
    print("轨道1: 校准模型 — P(repay) 预测对比")
    print(f"{'='*60}")
    cases = load_gold_cases(args.cases)
    print(f"评估案例: {len(cases)} 条")
    print(f"策略A: {STRATEGY_A['approach']}/{STRATEGY_A['tone']}/push={STRATEGY_A['push_intensity']}")
    print(f"策略B: {STRATEGY_B['approach']}/{STRATEGY_B['tone']}/push={STRATEGY_B['push_intensity']}")

    model_result = run_model_track(cases, cal)
    print(f"\nP(repay) A: {model_result['repay_prob_a']:.3f}")
    print(f"P(repay) B: {model_result['repay_prob_b']:.3f}")
    print(f"Δ: {model_result['delta_mean']:+.4f}  (p={model_result['p_value']:.4f})")

    # 展示模型学到的 top 5 特征权重
    top_features = sorted(
        zip(cal.extractor.feature_names, cal.model.coef_[0]),
        key=lambda x: abs(x[1]), reverse=True
    )[:5]
    print(f"\n模型 Top-5 特征权重:")
    for name, w in top_features:
        print(f"  {name:24s}: {w:+.3f}")

    # 3. 模拟器轨道
    print(f"\n{'='*60}")
    print("轨道2: 行为模拟器 — 承诺率对比")
    print(f"{'='*60}")
    profiles = make_profiles()
    sim = RealCustomerSimulatorV2()

    sim_result = run_simulator_track(profiles, sim, args.sim_trials)
    print(f"策略A 承诺率: {sim_result['commit_rate_a']:.1%}  (push≤3)")
    print(f"策略B 承诺率: {sim_result['commit_rate_b']:.1%}  (push≤5)")
    print(f"Δ: {sim_result['delta']:+.1%}")
    print(f"\n分群明细 (每档案 {args.sim_trials} 次):")
    for seg, (a, b) in sim_result["by_segment"].items():
        bar_a = "█" * int(a * 20)
        bar_b = "█" * int(b * 20)
        print(f"  {seg:20s}  A: {bar_a:<20s} {a:.0%}")
        print(f"  {'':20s}  B: {bar_b:<20s} {b:.0%}  ({b-a:+.0%})")

    # 4. 生成双轨研判报告
    print(f"\n{'='*60}")
    print("双轨研判报告")
    print(f"{'='*60}\n")
    report = reporter.generate_report(args.name, sim_result, model_result, qr)
    print(report)


if __name__ == "__main__":
    main()
