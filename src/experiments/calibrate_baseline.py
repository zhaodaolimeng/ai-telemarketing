#!/usr/bin/env python3
"""
P15-G01: 校准基线计算
对比 gold_dataset 标注的 call_result（代理指标）与 CSV 的 repay_type（业务真值），
计算人工坐席的精准率/召回率/校准系数，作为 chatbot 效果的上限参照。
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_csv(path: Path) -> dict:
    """加载 CSV，key=case_id"""
    records = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            mobile = row.get("mobile", "").strip()
            call_time = row.get("call_time", "").strip()
            ct = call_time.replace("-", "").replace(" ", "").replace(":", "")
            records[f"{mobile}-{ct}"] = row
    return records


def analyze(gold_dir: Path, csv_records: dict) -> dict:
    """交叉分析 gold 标注与 CSV 真值"""
    tp = fp = tn = fn = 0
    stage_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "total": 0})
    repay_type_stats = defaultdict(lambda: {"total": 0, "success": 0})
    resistance_stats = defaultdict(lambda: {"total": 0, "repay": 0})

    matched = 0
    details = []

    for gf in gold_dir.glob("*.json"):
        case_id = gf.stem
        if case_id not in csv_records:
            continue
        data = json.loads(gf.read_text())
        if "dialogue" not in data:
            continue

        matched += 1
        bi = data.get("basic_info", {})
        up = data.get("user_profile", {})
        row = csv_records[case_id]

        # 代理指标：标注的 call_result
        call_result = bi.get("call_result", "failure")
        proxy_success = (call_result == "success")

        # 业务真值
        repay_type = row.get("repay_type", "").strip()
        actual_repay = (repay_type == "repay")

        # 混淆矩阵
        if proxy_success and actual_repay:
            tp += 1
        elif proxy_success and not actual_repay:
            fp += 1
        elif not proxy_success and not actual_repay:
            tn += 1
        else:
            fn += 1

        # 按阶段
        stage = bi.get("collection_stage", "H2")
        stage_stats[stage]["total"] += 1
        if proxy_success and actual_repay:
            stage_stats[stage]["tp"] += 1
        elif proxy_success and not actual_repay:
            stage_stats[stage]["fp"] += 1
        elif not proxy_success and not actual_repay:
            stage_stats[stage]["tn"] += 1
        else:
            stage_stats[stage]["fn"] += 1

        # 按 repay_type
        rt_key = repay_type or "empty"
        repay_type_stats[rt_key]["total"] += 1
        if proxy_success:
            repay_type_stats[rt_key]["success"] += 1

        # 按抗拒等级
        rl = up.get("resistance_level", "unknown")
        resistance_stats[rl]["total"] += 1
        if actual_repay:
            resistance_stats[rl]["repay"] += 1

        details.append({
            "case_id": case_id,
            "loan_no": row.get("loan_no", ""),
            "stage": stage,
            "call_result": call_result,
            "repay_type": repay_type,
            "resistance": rl,
            "persona": up.get("persona", ""),
            "amount": row.get("approved_amount", ""),
            "dpd": row.get("dpd", ""),
        })

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / total if total > 0 else 0
    base_rate = (tp + fn) / total if total > 0 else 0
    calibration_ratio = precision / base_rate if base_rate > 0 else 0

    analysis = {
        "total_matched": matched,
        "confusion_matrix": {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "tp_desc": "标注成功 & 实际还款",
            "fp_desc": "标注成功 & 未还款（虚假承诺）",
            "tn_desc": "标注失败 & 未还款",
            "fn_desc": "标注失败 & 实际还款（漏网之鱼）",
        },
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "base_rate": round(base_rate, 4),
        "calibration_ratio": round(calibration_ratio, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0,
        "by_stage": {},
        "by_repay_type": {},
        "by_resistance": {},
    }

    for stage in ("H2", "H1", "S0"):
        s = stage_stats.get(stage)
        if not s or s["total"] == 0:
            continue
        s_tp, s_fp, s_tn, s_fn = s["tp"], s["fp"], s["tn"], s["fn"]
        s_prec = s_tp / (s_tp + s_fp) if (s_tp + s_fp) > 0 else 0
        s_rec = s_tp / (s_tp + s_fn) if (s_tp + s_fn) > 0 else 0
        s_f1 = 2 * s_prec * s_rec / (s_prec + s_rec) if (s_prec + s_rec) > 0 else 0
        s_base = (s_tp + s_fn) / s["total"] if s["total"] > 0 else 0
        analysis["by_stage"][stage] = {
            "total": s["total"],
            "precision": round(s_prec, 4),
            "recall": round(s_rec, 4),
            "f1": round(s_f1, 4),
            "base_rate": round(s_base, 4),
            "fp_count": s_fp,
            "fp_rate": round(s_fp / (s_fp + s_tp), 4) if (s_fp + s_tp) > 0 else 0,
        }

    for rt, stats in sorted(repay_type_stats.items()):
        label = {"repay": "实际还款", "extend": "展期", "empty": "未还款"}.get(rt, rt)
        analysis["by_repay_type"][rt] = {
            "label": label,
            "total": stats["total"],
            "proxy_success": stats["success"],
            "proxy_success_rate": round(stats["success"] / stats["total"], 4) if stats["total"] > 0 else 0,
        }

    for rl, stats in sorted(resistance_stats.items()):
        analysis["by_resistance"][rl] = {
            "total": stats["total"],
            "repay_count": stats["repay"],
            "repay_rate": round(stats["repay"] / stats["total"], 4) if stats["total"] > 0 else 0,
        }

    return analysis, details


def main():
    import argparse
    parser = argparse.ArgumentParser(description="P15-G01 校准基线计算")
    parser.add_argument("--output", type=str, default="data/processed/calibration_baseline.json",
                        help="输出文件路径")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    gold_dir = project_root / "data/raw/gold_dataset"
    csv_path = project_root / "data/raw/cases/fetched_leads_deduped.csv"
    output_path = project_root / args.output

    print("P15-G01: 校准基线计算")
    print(f"  Gold目录: {gold_dir}")
    print(f"  CSV: {csv_path}")

    csv_records = load_csv(csv_path)
    print(f"  CSV 记录: {len(csv_records)}")

    analysis, details = analyze(gold_dir, csv_records)

    print("\n" + "=" * 60)
    print("人工坐席校准基线")
    print("=" * 60)
    print(f"匹配案例: {analysis['total_matched']}")
    print(f"基础还款率: {analysis['base_rate']:.1%}")
    print()
    cm = analysis['confusion_matrix']
    print(f"混淆矩阵:")
    print(f"  TP (承诺→还款):     {cm['tp']:>5}  ({cm['tp_desc']})")
    print(f"  FP (承诺→未还):     {cm['fp']:>5}  ({cm['fp_desc']})")
    print(f"  TN (无承诺→未还):   {cm['tn']:>5}  ({cm['tn_desc']})")
    print(f"  FN (无承诺→还款):   {cm['fn']:>5}  ({cm['fn_desc']})")
    print()
    print(f"精准率 (Precision):   {analysis['precision']:.1%}  ← 承诺还款的用户中，真正还款的比例")
    print(f"召回率 (Recall):      {analysis['recall']:.1%}  ← 实际还款者中，被坐席拿到承诺的比例")
    print(f"F1:                  {analysis['f1']:.1%}")
    print(f"假阳性率 (FPR):       {analysis['false_positive_rate']:.1%}  ← 虚假承诺率（核心校准指标）")
    print(f"校准系数:             {analysis['calibration_ratio']:.2f}x  ← 代理指标相对基准的提升倍数")

    print("\n按催收阶段:")
    for stage in ("H2", "H1", "S0"):
        if stage in analysis["by_stage"]:
            s = analysis["by_stage"][stage]
            print(f"  {stage}: prec={s['precision']:.1%}, rec={s['recall']:.1%}, "
                  f"f1={s['f1']:.1%}, fp_rate={s['fp_rate']:.1%}, n={s['total']}")

    print("\n按 repay_type (代理指标成功率):")
    for rt, stats in analysis["by_repay_type"].items():
        print(f"  {stats['label']} ({rt}): {stats['total']}条, "
              f"坐席标注成功 {stats['proxy_success_rate']:.1%}")

    print("\n按抗拒等级 (实际还款率):")
    for rl, stats in analysis["by_resistance"].items():
        print(f"  {rl}: {stats['total']}条, 还款率 {stats['repay_rate']:.1%}")

    # 保存完整结果
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "meta": {
            "task": "P15-G01",
            "description": "校准基线：gold标注 call_result(代理指标) vs CSV repay_type(业务真值)",
            "total_matched": analysis["total_matched"],
        },
        "analysis": analysis,
        "details": details[:200],  # 前200条详情
    }, ensure_ascii=False, indent=2))
    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
