#!/usr/bin/env python3
"""
P15-H02 评测: 静态策略 vs LLM 策略路由双轨对比

对比"get_strategy_profile 静态查表" vs "LLM 分析画像动态输出策略"。
"""
import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import numpy as np
from evaluation.feature_extractor import DialogueFeatureExtractor, UserProfile
from evaluation.calibrator import RepaymentCalibrator
from evaluation.reporter import EvalReporter
from core.simulator import RealCustomerSimulatorV2, make_profiles
from core.strategy_profile import get_strategy_profile, profile_to_dict
from core.llm_strategy_router import LlmStrategyRouter, static_fallback
from core.llm_config import LLMConfig


def _profile_to_strategy(profile) -> dict:
    if hasattr(profile, "approach"):
        return profile_to_dict(profile)
    return profile


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
        user_profile_dict = {
            "new_flag": nf, "chat_group": cg, "dpd": dpd_val,
            "repay_history": case.get("repay_history", 0.5),
            "income_ratio": case.get("income_ratio", 1.0),
            "product_name": case.get("product_name", ""),
            "approved_amount": case.get("approved_amount", 500000),
            "marital_status": case.get("marital_status", ""),
            "loan_seq": case.get("loan_seq", 1),
            "call_hour": case.get("call_hour", 12),
        }
        cases.append({
            "case": case, "log": log, "profile": profile,
            "user_profile_dict": user_profile_dict,
            "nf": nf, "cg": cg, "dpd": dpd_val,
        })
    return cases


def main():
    parser = argparse.ArgumentParser(description="P15-H02 LLM 策略路由评测")
    parser.add_argument("--cases", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true",
                        help="仅验证管道，不实际调用 LLM（LLM 轨道使用静态 fallback）")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    model_path = PROJECT_ROOT / "data" / "evaluations" / "calibrator.pkl"
    cal = RepaymentCalibrator()
    cal.load(model_path)
    qr = cal.quality_report()
    print(f"模型: AUC={qr['auc']:.3f} ECE={qr['ece']:.3f}")

    # 设置 LLM 路由器
    llm_config = LLMConfig.from_env()
    if args.dry_run:
        llm_config.strategy_routing_enabled = False
        print("[DRY-RUN] LLM 路由已禁用，两个轨道均使用静态策略\n")
    else:
        print(f"LLM 路由: enabled={llm_config.strategy_routing_enabled} "
              f"provider={llm_config.provider}\n")

    router = LlmStrategyRouter(llm_config)

    cases = load_gold_cases(args.cases)
    extractor = DialogueFeatureExtractor()

    # ─── 为每个 case 解析策略 ───
    static_strats = []
    llm_strats = []
    field_agreements = {"approach": 0, "tone": 0, "push_intensity": 0, "extension_priority": 0}
    push_diffs = []

    for c in cases:
        nf, cg, dpd = c["nf"], c["cg"], c["dpd"]
        static = _profile_to_strategy(get_strategy_profile(nf, cg, dpd=dpd))
        static_strats.append(static)

        llm = _profile_to_strategy(router.route(c["user_profile_dict"]))
        llm_strats.append(llm)

        # 字段一致性统计
        if static["approach"] == llm["approach"]:
            field_agreements["approach"] += 1
        if static["tone"] == llm["tone"]:
            field_agreements["tone"] += 1
        if static["push_intensity"] == llm["push_intensity"]:
            field_agreements["push_intensity"] += 1
        if static["extension_priority"] == llm["extension_priority"]:
            field_agreements["extension_priority"] += 1
        push_diffs.append(llm["push_intensity"] - static["push_intensity"])

    # ─── 模型轨道 ───
    feats_static = [extractor.extract(c["log"], c["profile"], s) for c, s in zip(cases, static_strats)]
    feats_llm = [extractor.extract(c["log"], c["profile"], s) for c, s in zip(cases, llm_strats)]
    X_static, X_llm = np.array(feats_static), np.array(feats_llm)

    proba_static = cal.model.predict_proba(X_static)[:, 1]
    proba_llm = cal.model.predict_proba(X_llm)[:, 1]
    compare = cal.compare(X_static, X_llm)

    print("轨道1: 校准模型 P(repay)")
    print(f"  静态策略: {float(np.mean(proba_static)):.3f}")
    print(f"  LLM 路由: {float(np.mean(proba_llm)):.3f}")
    print(f"  Δ: {compare['delta_mean']:+.4f} (p={compare['p_value']:.4f})")
    if compare['significant']:
        print("  → 差异统计显著 (p<0.05)")

    # 按客群分解
    from collections import defaultdict
    seg_groups = defaultdict(list)
    for i, c in enumerate(cases):
        seg_groups[f"nf={c['nf']}_{c['cg']}"].append((proba_static[i], proba_llm[i]))
    print("\n  分群明细:")
    print(f"  {'客群':<18} {'静态P(repay)':>12} {'LLM P(repay)':>12} {'Δ':>10}")
    print(f"  {'─'*52}")
    for key in sorted(seg_groups.keys()):
        a_vals, b_vals = zip(*seg_groups[key])
        a_mean, b_mean = np.mean(a_vals), np.mean(b_vals)
        print(f"  {key:<18} {a_mean:>11.3f} {b_mean:>11.3f} {b_mean-a_mean:>+9.3f}")

    # ─── 字段一致性 ───
    nc = len(cases)
    print(f"\n轨道1.5: 字段一致性 (静态 vs LLM)")
    for field in ["approach", "tone", "push_intensity", "extension_priority"]:
        agree = field_agreements[field]
        print(f"  {field:25s}: {agree}/{nc} = {agree/nc:.0%}")
    print(f"  push_intensity MAE: {np.mean(np.abs(push_diffs)):.2f}")

    # ─── 模拟器轨道 ───
    profiles = make_profiles()
    sim = RealCustomerSimulatorV2()
    stages = ["greeting", "identity", "purpose", "ask_time"]

    # 静态策略映射 (与 validate_segmentation.py 一致)
    seg_map = {
        "silent_payer": get_strategy_profile(1, "H1"),
        "excuse_master": get_strategy_profile(0, "S0"),
        "false_promiser": get_strategy_profile(0, "H2"),
        "knowing_delayer": get_strategy_profile(2, "S0"),
        "hopeless": get_strategy_profile(0, "S0", dpd=3),
    }

    # LLM 策略映射 (用 router 为每个 persona 构造画像)
    llm_map = {}
    persona_profiles = {
        "silent_payer": {"new_flag": 1, "chat_group": "H1", "dpd": 3, "repay_history": 0.7, "loan_seq": 2},
        "excuse_master": {"new_flag": 0, "chat_group": "S0", "dpd": 5, "repay_history": 0.4, "loan_seq": 1},
        "false_promiser": {"new_flag": 0, "chat_group": "H2", "dpd": 1, "repay_history": 0.5, "loan_seq": 1},
        "knowing_delayer": {"new_flag": 2, "chat_group": "S0", "dpd": 10, "repay_history": 0.3, "loan_seq": 5},
        "hopeless": {"new_flag": 0, "chat_group": "S0", "dpd": 15, "repay_history": 0.1, "loan_seq": 1},
    }
    for pname, prof in persona_profiles.items():
        llm_map[pname] = _profile_to_strategy(router.route(prof))

    n_trials = 40
    commits_static, commits_llm = 0, 0
    by_profile = {}

    for pname, profile in profiles.items():
        static_strat = _profile_to_strategy(seg_map[pname])
        llm_strat = llm_map[pname]
        ca, cb = 0, 0
        for _ in range(n_trials):
            for stage in stages:
                sim.generate_response(stage, profile=profile, push_count=0)
            for r in range(static_strat["max_push_rounds"]):
                resp = sim.generate_response("push", profile=profile, push_count=r)
                if resp and any(w in resp.lower() for w in ["jam", "besok", "hari ini", "nanti"]):
                    ca += 1; break
            for r in range(llm_strat["max_push_rounds"]):
                resp = sim.generate_response("push", profile=profile, push_count=r)
                if resp and any(w in resp.lower() for w in ["jam", "besok", "hari ini", "nanti"]):
                    cb += 1; break

        by_profile[profile.name] = (ca / n_trials, cb / n_trials)
        commits_static += ca; commits_llm += cb

    total = n_trials * len(profiles)
    sim_result = {
        "commit_rate_a": round(commits_static / total, 3),
        "commit_rate_b": round(commits_llm / total, 3),
        "delta": round((commits_llm - commits_static) / total, 3),
        "n_trials": total,
        "by_segment": by_profile,
    }

    print(f"\n轨道2: 模拟器承诺率")
    print(f"  静态策略: {sim_result['commit_rate_a']:.1%}")
    print(f"  LLM 路由: {sim_result['commit_rate_b']:.1%}")
    print(f"  Δ: {sim_result['delta']:+.1%}")
    for seg, (a, b) in by_profile.items():
        print(f"  {seg:20s}: {a:.0%} → {b:.0%}  ({b-a:+.0%})")

    # ─── 双轨研判 ───
    model_result = {
        "repay_prob_a": round(float(np.mean(proba_static)), 3),
        "repay_prob_b": round(float(np.mean(proba_llm)), 3),
        "delta_mean": compare["delta_mean"],
        "p_value": compare["p_value"],
        "significant": compare["significant"],
        "field_agreements": {k: v / nc for k, v in field_agreements.items()},
        "push_intensity_mae": float(np.mean(np.abs(push_diffs))),
    }
    print(f"\n{'='*60}")
    reporter = EvalReporter()
    report = reporter.generate_report("static_vs_llm_routing", sim_result, model_result, qr)
    print(report)

    # 保存结果
    if args.output:
        output_path = PROJECT_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_data = {
            "config": {"cases": len(cases), "dry_run": args.dry_run},
            "model_track": model_result,
            "simulator_track": sim_result,
            "calibrator_quality": qr,
        }
        output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2))
        print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
