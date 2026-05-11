#!/usr/bin/env python3
"""
一键评测入口 — 双轨校准评测

Usage:
  python3 src/experiments/run_eval.py --train-only          # 仅训练校准模型
  python3 src/experiments/run_eval.py                        # 训练 + 质量报告
  python3 src/experiments/run_eval.py --help-details         # 详细帮助
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


def _generate_strategy_augmentations(n_per_profile: int = 5) -> tuple:
    """用模拟器生成策略变异样本，赋予策略特征梯度信号

    对 5 个行为档案，各用 n_per_profile 种策略跑模拟，
    将 commit 结果作为弱标签。策略变异使模型能学到
    "不同策略在不同档案上的效果差异"。
    """
    profiles = make_profiles()
    sim = RealCustomerSimulatorV2()
    extractor = DialogueFeatureExtractor()

    # 策略空间: 覆盖 approach × tone × push 组合
    strategy_variants = [
        {"approach": "guide", "tone": "neutral", "push_intensity": 2,
         "extension_priority": False, "max_push_rounds": 3, "extension_fee_ratio": 0.25},
        {"approach": "firm", "tone": "firm", "push_intensity": 4,
         "extension_priority": True, "max_push_rounds": 5, "extension_fee_ratio": 0.15},
        {"approach": "educate", "tone": "soft", "push_intensity": 1,
         "extension_priority": False, "max_push_rounds": 2, "extension_fee_ratio": 0.30},
        {"approach": "intervene", "tone": "urgent", "push_intensity": 5,
         "extension_priority": True, "max_push_rounds": 6, "extension_fee_ratio": 0.10},
        {"approach": "maintain", "tone": "neutral", "push_intensity": 3,
         "extension_priority": False, "max_push_rounds": 4, "extension_fee_ratio": 0.20},
    ]

    features, labels = [], []

    for profile_name, profile in profiles.items():
        # 推断 profile 对应的 user 类型
        if profile.will_repay == "payer":
            nf, cg = 2, "H2"    # 老客 H2
        elif profile.will_repay == "non_payer":
            nf, cg = 0, "S0"    # 新客 S0
        else:
            nf, cg = 0, "H2"    # conditional

        for strat in strategy_variants[:n_per_profile]:
            # 用模拟器跑一轮对话，看该 profile 在策略下是否给出承诺
            stages = ["greeting", "identity", "purpose", "ask_time"]
            for stage in stages:
                sim.generate_response(stage, profile=profile, push_count=0)

            committed = False
            for push_n in range(strat["max_push_rounds"]):
                resp = sim.generate_response("push", profile=profile, push_count=push_n)
                if resp and any(w in resp.lower() for w in
                                ["jam", "besok", "hari ini", "nanti"]):
                    committed = True
                    break

            # 标注: conditional 档案由策略决定，payer 大概率还，non_payer 大概率不还
            if profile.will_repay == "payer":
                label = 1
            elif profile.will_repay == "non_payer":
                label = 0
            else:
                label = 1 if committed else 0

            # 构造合成对话日志
            log = {
                "turns": 8 + strat["max_push_rounds"],
                "push_count": strat["max_push_rounds"] if not committed else
                              next((i for i in range(strat["max_push_rounds"])), 0),
                "silence_count": 1 if profile.response_style == "silent" else 0,
                "unknown_count": 0,
                "extension_offered": strat["extension_priority"],
                "got_commitment": committed,
                "commitment_turn": 4 if committed else -1,
                "objection_types": (["no_money"] if profile.intent_type == "excuse_prone"
                                    else ["busy"] if profile.intent_type == "false_promiser"
                                    else []),
                "final_state": "CLOSE" if committed else "FAILED",
                "cooperation_signals": (2 if committed else 0),
            }
            user = UserProfile(new_flag=nf, chat_group=cg, repay_history=0.5)

            features.append(extractor.extract(log, user, strat))
            labels.append(label)

    return np.array(features, dtype=np.float32), np.array(labels, dtype=int)


def train_calibrator():
    """用 gold_linkage 数据训练校准模型"""
    linkage_path = PROJECT_ROOT / "data" / "gold_linkage.json"
    gd_path = PROJECT_ROOT / "data" / "gold_dataset"

    if not linkage_path.exists():
        print(f"ERROR: gold_linkage.json not found at {linkage_path}")
        return None

    with open(linkage_path) as f:
        linkage = json.load(f)

    extractor = DialogueFeatureExtractor()
    features = []
    labels = []

    for case in linkage["linked_cases"]:
        file_path = gd_path / case["file"]
        if not file_path.exists():
            continue
        dialogue = json.loads(file_path.read_text()).get("dialogue", [])
        if not dialogue:
            continue

        turns = len([t for t in dialogue if t.get("speaker") == "customer"])
        objection_types = list(set(
            t.get("user_intent", "unknown") for t in dialogue
            if t.get("speaker") == "customer" and t.get("user_intent", "unknown") != "unknown"
        ))

        # 从对话内容推断特征，禁止使用 repay_type（防止数据穿越）
        customer_turns = [t for t in dialogue if t.get("speaker") == "customer"]
        # 检测客户是否在对话中口头承诺还款时间
        _time_intents = {"agree_to_pay", "confirm_time", "give_time"}
        _has_verbal_commit = any(
            t.get("user_intent", "") in _time_intents
            for t in customer_turns
        )
        _commit_turn = next(
            (i for i, t in enumerate(customer_turns)
             if t.get("user_intent", "") in _time_intents),
            -1
        )

        log = {
            "turns": len(customer_turns),
            "push_count": 0,
            "silence_count": 0,
            "unknown_count": sum(1 for t in dialogue if t.get("user_intent") == "unknown"),
            "extension_offered": any(
                t.get("user_intent", "") in ("ask_extension", "agree_extension")
                for t in customer_turns
            ),
            "got_commitment": _has_verbal_commit,
            "commitment_turn": _commit_turn,
            "objection_types": objection_types,
            "final_state": "CLOSE",
            "cooperation_signals": sum(
                1 for t in customer_turns
                if t.get("user_intent", "") in ("agree_to_pay", "confirm_identity", "give_time")
            ),
        }

        profile = UserProfile(
            new_flag=case.get("new_flag", 0),
            chat_group=case.get("chat_group", "H2"),
            repay_history=0.5,
        )

        label = 1 if case.get("repay_type") in ("repay", "extend") else 0

        features.append(extractor.extract(log, profile))
        labels.append(label)

    if len(features) == 0:
        print("ERROR: No training data found")
        return None

    X_real = np.array(features)
    y_real = np.array(labels)

    # 生成策略变异样本
    X_syn, y_syn = _generate_strategy_augmentations(n_per_profile=5)
    print(f"真实样本: {len(y_real)} 条, 正样本率: {y_real.mean():.1%}")
    print(f"合成样本: {len(y_syn)} 条, 正样本率: {y_syn.mean():.1%}")

    # 合并训练集，合成样本权重 0.3 (真实数据主导)
    X = np.vstack([X_real, X_syn])
    y = np.concatenate([y_real, y_syn])
    sample_weight = np.concatenate([
        np.ones(len(y_real)),
        np.full(len(y_syn), 0.3),
    ])

    cal = RepaymentCalibrator()
    result = cal.train(X, y, sample_weight=sample_weight)
    print(f"训练完成: AUC={result['auc']:.3f}, ECE={result['ece']:.3f}")

    model_path = PROJECT_ROOT / "data" / "evaluations" / "calibrator.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    cal.save(model_path)
    print(f"模型已保存: {model_path}")

    return cal


def main():
    parser = argparse.ArgumentParser(description="双轨校准评测")
    parser.add_argument("--train-only", action="store_true",
                        help="仅训练校准模型")
    args = parser.parse_args()

    print("训练校准模型...")
    cal = train_calibrator()
    if cal:
        qr = cal.quality_report()
        print(f"\n模型质量:")
        print(f"  AUC: {qr['auc']:.3f} (门槛≥0.75: {'PASS' if qr['auc_pass'] else 'FAIL'})")
        print(f"  ECE: {qr['ece']:.3f} (门槛≤0.10: {'PASS' if qr['ece_pass'] else 'FAIL'})")
    else:
        print("训练失败")


if __name__ == "__main__":
    main()
