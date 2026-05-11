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

        log = {
            "turns": turns,
            "push_count": 0,
            "silence_count": 0,
            "unknown_count": sum(1 for t in dialogue if t.get("intent") == "unknown"),
            "extension_offered": False,
            "got_commitment": case.get("repay_type", "None") not in ("None", "empty"),
            "commitment_turn": turns if case.get("repay_type", "None") not in ("None", "empty") else -1,
            "objection_types": objection_types,
            "final_state": "CLOSE",
            "cooperation_signals": sum(1 for t in dialogue if t.get("intent") in ("agree_to_pay", "confirm_identity")),
        }

        profile = UserProfile(
            new_flag=case.get("new_flag", 0),
            chat_group=case.get("chat_group", "H2"),
            dpd=case.get("dpd", 0),
            repay_history=0.5,
        )

        label = 1 if case.get("repay_type") in ("repay", "extend") else 0

        features.append(extractor.extract(log, profile))
        labels.append(label)

    if len(features) == 0:
        print("ERROR: No training data found")
        return None

    X = np.array(features)
    y = np.array(labels)
    print(f"训练数据: {len(y)} 条, 正样本率: {y.mean():.1%}")

    cal = RepaymentCalibrator()
    result = cal.train(X, y)
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
