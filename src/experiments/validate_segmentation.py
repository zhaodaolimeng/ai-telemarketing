#!/usr/bin/env python3
"""
P15-B01 验证: 统一策略 vs 分群策略双轨对比

对比"所有客群用同一套默认策略" vs "9种客群×DPD三档差异化策略"。
"""
import sys, json, argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import numpy as np
from evaluation.feature_extractor import DialogueFeatureExtractor, UserProfile
from evaluation.calibrator import RepaymentCalibrator
from evaluation.reporter import EvalReporter
from core.simulator import RealCustomerSimulatorV2, make_profiles
from core.strategy_profile import get_strategy_profile, StrategyProfile

# 统一策略：对所有客群使用 nf=0_H2 默认
UNIFORM_STRATEGY = {
    "approach": "educate", "tone": "soft", "push_intensity": 2,
    "extension_priority": False, "max_push_rounds": 3, "extension_fee_ratio": 0.25,
}


def _profile_to_strategy(profile: StrategyProfile) -> dict:
    return {
        "approach": profile.approach,
        "tone": profile.tone,
        "push_intensity": profile.push_intensity,
        "extension_priority": profile.extension_priority,
        "max_push_rounds": profile.max_push_rounds,
        "extension_fee_ratio": profile.extension_fee_ratio,
    }


def load_gold_cases(limit: int = 300) -> list[dict]:
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
            "push_count": 0, "silence_count": 0,
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
        nf = case.get("new_flag", 0)
        cg = case.get("chat_group", "H2")
        dpd_val = case.get("dpd", 0)
        profile = UserProfile(new_flag=nf, chat_group=cg, repay_history=0.5)
        segmented_strat = _profile_to_strategy(get_strategy_profile(nf, cg, dpd_val))
        cases.append({
            "case": case, "log": log, "profile": profile,
            "uniform": UNIFORM_STRATEGY, "segmented": segmented_strat,
            "nf": nf, "cg": cg, "dpd": dpd_val,
        })
    return cases


def main():
    parser = argparse.ArgumentParser(description="P15-B01 策略验证")
    parser.add_argument("--cases", type=int, default=300)
    args = parser.parse_args()

    model_path = PROJECT_ROOT / "data" / "evaluations" / "calibrator.pkl"
    cal = RepaymentCalibrator()
    cal.load(model_path)
    qr = cal.quality_report()
    print(f"模型: AUC={qr['auc']:.3f} ECE={qr['ece']:.3f}\n")

    cases = load_gold_cases(args.cases)
    extractor = DialogueFeatureExtractor()

    # ─── 模型轨道 ───
    feats_uniform = [extractor.extract(c["log"], c["profile"], c["uniform"]) for c in cases]
    feats_segmented = [extractor.extract(c["log"], c["profile"], c["segmented"]) for c in cases]
    X_u, X_s = np.array(feats_uniform), np.array(feats_segmented)

    proba_u = cal.model.predict_proba(X_u)[:, 1]
    proba_s = cal.model.predict_proba(X_s)[:, 1]
    compare = cal.compare(X_u, X_s)

    print("轨道1: 校准模型 P(repay)")
    print(f"  统一策略: {float(np.mean(proba_u)):.3f}")
    print(f"  分群策略: {float(np.mean(proba_s)):.3f}")
    print(f"  Δ: {compare['delta_mean']:+.4f} (p={compare['p_value']:.4f})")
    if compare['significant']:
        print("  → 差异统计显著 (p<0.05)")

    # 按客群分解
    from collections import defaultdict
    seg_groups = defaultdict(list)
    for i, c in enumerate(cases):
        seg_groups[f"nf={c['nf']}_{c['cg']}"].append((proba_u[i], proba_s[i]))
    print("\n  分群明细:")
    print(f"  {'客群':<18} {'统一P(repay)':>12} {'分群P(repay)':>12} {'Δ':>10}")
    print(f"  {'─'*52}")
    for key in sorted(seg_groups.keys()):
        u_vals, s_vals = zip(*seg_groups[key])
        u_mean, s_mean = np.mean(u_vals), np.mean(s_vals)
        print(f"  {key:<18} {u_mean:>11.3f} {s_mean:>11.3f} {s_mean-u_mean:>+9.3f}")

    # ─── 模拟器轨道 ───
    profiles = make_profiles()
    sim = RealCustomerSimulatorV2()
    stages = ["greeting", "identity", "purpose", "ask_time"]

    # 策略A: 统一 H2 默认温和
    uni_strat = _profile_to_strategy(get_strategy_profile(0, "H2"))
    # 策略B: 分群（按 profile 行为特征匹配策略，而非还款率）
    # silent_payer 需要至少 3 轮 push 才能解冻 → 不能用极轻型
    # excuse_master 借口多但还款意愿有条件 → 需要展期+部分还款方案
    # knowing_delayer 老客故意拖 → 后果强调有效
    seg_map = {
        "silent_payer": get_strategy_profile(1, "H1"),        # 新转老 H1: push=2, 3轮, 关系型 (足够解冻)
        "excuse_master": get_strategy_profile(0, "S0"),       # 新客 S0: 展期优先+部分还款
        "false_promiser": get_strategy_profile(0, "H2"),      # 新客 H2: 教育为主
        "knowing_delayer": get_strategy_profile(2, "S0"),     # 老客 S0: 后果强调
        "hopeless": get_strategy_profile(0, "S0", dpd=3),     # 新客 S0 DPD 1-7 (非极端)
    }

    n_trials = 40
    commits_uni, commits_seg = 0, 0
    by_profile = {}

    for pname, profile in profiles.items():
        seg_strat = _profile_to_strategy(seg_map[pname])
        ca, cb = 0, 0
        for _ in range(n_trials):
            for stage in stages:
                sim.generate_response(stage, profile=profile, push_count=0)
            # 统一策略 push (3轮)
            for n in range(uni_strat["max_push_rounds"]):
                resp = sim.generate_response("push", profile=profile, push_count=n)
                if resp and any(w in resp.lower() for w in ["jam", "besok", "hari ini", "nanti"]):
                    ca += 1; break
            # 分群策略 push
            for n in range(seg_strat["max_push_rounds"]):
                resp = sim.generate_response("push", profile=profile, push_count=n)
                if resp and any(w in resp.lower() for w in ["jam", "besok", "hari ini", "nanti"]):
                    cb += 1; break

        by_profile[profile.name] = (ca / n_trials, cb / n_trials)
        commits_uni += ca; commits_seg += cb

    total = n_trials * len(profiles)
    sim_result = {
        "commit_rate_a": round(commits_uni / total, 3),
        "commit_rate_b": round(commits_seg / total, 3),
        "delta": round((commits_seg - commits_uni) / total, 3),
        "n_trials": total,
        "by_segment": by_profile,
    }

    print(f"\n轨道2: 模拟器承诺率")
    print(f"  统一策略: {sim_result['commit_rate_a']:.1%}")
    print(f"  分群策略: {sim_result['commit_rate_b']:.1%}")
    print(f"  Δ: {sim_result['delta']:+.1%}")
    for seg, (a, b) in by_profile.items():
        print(f"  {seg:20s}: {a:.0%} → {b:.0%}  ({b-a:+.0%})")

    # ─── 双轨研判 ───
    model_result = {
        "repay_prob_a": round(float(np.mean(proba_u)), 3),
        "repay_prob_b": round(float(np.mean(proba_s)), 3),
        "delta_mean": compare["delta_mean"],
        "p_value": compare["p_value"],
        "significant": compare["significant"],
    }
    print(f"\n{'='*60}")
    reporter = EvalReporter()
    report = reporter.generate_report("uniform_vs_segmented", sim_result, model_result, qr)
    print(report)


if __name__ == "__main__":
    main()
