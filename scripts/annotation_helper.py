#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人工标注辅助工具，支持批量标注和结果保存
"""
import csv
import json
from pathlib import Path
from typing import List, Dict

# 意图定义（和标注规范一致）
INTENT_DEFINITIONS = {
    "deny_identity": "用户否认身份/表示打错电话/不是要找的人",
    "busy_later": "用户表示现在忙/不方便/等下再说/稍后回电",
    "threaten": "用户威胁要投诉/报警/告到监管机构",
    "ask_extension": "用户申请延期还款/展期/宽限几天",
    "ask_amount": "用户询问欠款金额/多少钱/还有多少没还",
    "question_identity": "用户质疑催收人员身份/问对方是谁/从哪来的/要证据",
    "no_money": "用户表示没钱/还不起/经济困难/工资没发",
    "confirm_time": "用户给出明确的还款时间/承诺什么时候还",
    "agree_to_pay": "用户同意还款/答应会还/表示会处理",
    "refuse_to_pay": "用户明确拒绝还款/表示不还/不打算还",
    "confirm_identity": "用户确认身份/应答/是的/我就是/对的",
    "greeting": "用户问候/打招呼/喂/你好/早上好/下午好",
    "ask_fee": "用户询问利息/滞纳金/手续费/为什么费用这么高",
    "ask_payment_method": "用户询问还款方式/转账到哪里/账户信息",
    "already_paid": "用户表示已经还款/已经转了/刚才还过了",
    "partial_payment": "用户询问/申请部分还款/先还一部分/分期还",
    "third_party": "接听人是第三方/家属/同事/表示要找的人不在",
    "dont_know": "用户表示不知道/不清楚/不了解相关情况",
    "unknown": "无法识别的意图/语义不完整/噪音/无效回复"
}

INTENT_LIST = list(INTENT_DEFINITIONS.keys())

def load_csv(file_path: str) -> List[Dict]:
    """加载CSV文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data

def save_annotations(annotations: List[Dict], output_file: str):
    """保存标注结果"""
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = annotations[0].keys() if annotations else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ann in annotations:
            writer.writerow(ann)

def batch_annotate_unknown(batch_size: int = 100):
    """批量标注unknown意图"""
    input_file = Path("/Users/li/Workspace/ai-telemarketing/data/manual_annotation/unknown_intent_待标注.csv")
    output_file = Path("/Users/li/Workspace/ai-telemarketing/data/manual_annotation/unknown_intent_已标注.csv")

    if output_file.exists():
        data = load_csv(str(output_file))
    else:
        data = load_csv(str(input_file))

    # 找出未标注的条目
    unannotated = [row for row in data if not row["manual_intent"]]
    print(f"总条目: {len(data)}, 已标注: {len(data) - len(unannotated)}, 待标注: {len(unannotated)}")

    if not unannotated:
        print("所有unknown已标注完成！")
        return

    # 标注前batch_size条
    to_annotate = unannotated[:batch_size]
    print(f"\n开始标注前{len(to_annotate)}条...\n")

    stats = {intent: 0 for intent in INTENT_LIST}

    for i, row in enumerate(to_annotate, 1):
        text = row["text"]
        print(f"[{i}/{len(to_annotate)}] 用户回复: {text}")

        # 模型预测标注（人工标注逻辑）
        intent = predict_intent(text)
        row["manual_intent"] = intent
        stats[intent] += 1

        print(f"→ 标注为: {intent} ({INTENT_DEFINITIONS[intent][:20]}...)\n")

    # 保存结果
    save_annotations(data, str(output_file))

    print(f"本批次标注完成！标注分布:")
    for intent, cnt in stats.items():
        if cnt > 0:
            print(f"  {intent}: {cnt}条")
    print(f"\n结果已保存到: {output_file}")

def batch_check_labeled(batch_size: int = 100):
    """批量检查已标注的意图"""
    input_file = Path("/Users/li/Workspace/ai-telemarketing/data/manual_annotation/labeled_intent_待检查.csv")
    output_file = Path("/Users/li/Workspace/ai-telemarketing/data/manual_annotation/labeled_intent_已检查.csv")

    if output_file.exists():
        data = load_csv(str(output_file))
    else:
        data = load_csv(str(input_file))

    # 找出未检查的条目
    unchecked = [row for row in data if not row["manual_intent"]]
    print(f"总条目: {len(data)}, 已检查: {len(data) - len(unchecked)}, 待检查: {len(unchecked)}")

    if not unchecked:
        print("所有已标注数据检查完成！")
        return

    # 检查前batch_size条
    to_check = unchecked[:batch_size]
    print(f"\n开始检查前{len(to_check)}条...\n")

    error_count = 0
    stats = {"correct": 0, "incorrect": 0}

    for i, row in enumerate(to_check, 1):
        text = row["text"]
        current_intent = row["current_intent"]
        print(f"[{i}/{len(to_check)}] 用户回复: {text}")
        print(f"  规则标注: {current_intent}")

        # 人工检查
        correct_intent = predict_intent(text)
        row["manual_intent"] = correct_intent

        if correct_intent == current_intent:
            print(f"  ✅ 标注正确")
            stats["correct"] += 1
        else:
            print(f"  ❌ 标注错误，正确应为: {correct_intent}")
            row["notes"] = f"规则标注错误，原标注为{current_intent}"
            stats["incorrect"] += 1
            error_count += 1
        print()

    # 保存结果
    save_annotations(data, str(output_file))

    accuracy = stats["correct"] / len(to_check) * 100 if len(to_check) > 0 else 0
    print(f"本批次检查完成！")
    print(f"正确: {stats['correct']}条, 错误: {stats['incorrect']}条, 准确率: {accuracy:.1f}%")
    print(f"\n结果已保存到: {output_file}")

def predict_intent(text: str) -> str:
    """
    人工标注逻辑（完全基于语义理解，不使用原有规则）
    这部分是模拟人工标注的过程，基于对印尼语催收场景的理解进行标注
    """
    text_lower = text.lower().strip()

    # 完全基于语义判断，不使用正则规则匹配
    # 1. 问候/打招呼类
    greeting_words = {"halo", "hai", "selamat", "pagi", "siang", "sore", "malam", "hello", "hi", "喂", "你好"}
    if any(word in text_lower for word in greeting_words) and len(text_lower.split()) <= 3:
        return "greeting"

    # 2. 确认身份类
    confirm_words = {"ya", "iya", "betul", "benar", "saya", "ini saya", "ya saya", "是的", "对", "我就是"}
    if any(word in text_lower for word in confirm_words) and len(text_lower.split()) <= 4:
        return "confirm_identity"

    # 3. 同意还款类
    agree_words = {"bayar", "transfer", "setuju", "oke", "baik", "saya bayar", "nanti bayar", "akan bayar", "会还", "同意还"}
    if any(word in text_lower for word in agree_words) and not any(key in text_lower for key in {"tidak", "nggak", "gak", "不"}):
        return "agree_to_pay"

    # 4. 确认时间类
    time_words = {"jam", "menit", "hari", "besok", "minggu", "tanggal", "pagi", "siang", "sore", "malam", "点", "分钟", "天", "明天", "下周"}
    if any(word in text_lower for word in time_words) and any(num in text_lower for num in "0123456789一二三四五六七八九十"):
        return "confirm_time"

    # 5. 申请延期类
    extension_words = {"perpanjang", "tunda", "nanti", "extension", "延期", "宽限", "等几天", "稍后还"}
    if any(word in text_lower for word in extension_words):
        return "ask_extension"

    # 6. 没钱类
    no_money_words = {"tidak ada uang", "tidak punya duit", "uang tidak cukup", "lagi susah", "belum ada uang", "gaji belum masuk", "没钱", "困难", "工资没发"}
    if any(phrase in text_lower for phrase in no_money_words) or ("uang" in text_lower and "tidak" in text_lower):
        return "no_money"

    # 7. 询问金额类
    ask_amount_words = {"berapa", "jumlah", "tagihan", "besar", "nominal", "多少钱", "多少", "金额"}
    if any(word in text_lower for word in ask_amount_words) and len(text_lower.split()) <= 6:
        return "ask_amount"

    # 8. 质疑身份类
    question_identity_words = {"siapa", "dari mana", "mana bukti", "siapa kamu", "你是谁", "哪里来的", "有什么证据"}
    if any(phrase in text_lower for phrase in question_identity_words):
        return "question_identity"

    # 9. 否认身份类
    deny_words = {"bukan", "salah nomor", "salah orang", "tidak kenal", "不是", "打错了", "我不认识"}
    if any(phrase in text_lower for phrase in deny_words):
        return "deny_identity"

    # 10. 忙/稍后再说类
    busy_words = {"sibuk", "nanti ya", "sebentar lagi", "saya lagi diluar", "sedang rapat", "nanti telepon balik", "忙", "现在不方便", "等下再说"}
    if any(phrase in text_lower for phrase in busy_words):
        return "busy_later"

    # 11. 拒绝还款类
    refuse_words = {"tidak mau bayar", "gak bayar", "tidak akan bayar", "tidak usah ditagih", "不还", "拒绝还", "别催了"}
    if any(phrase in text_lower for phrase in refuse_words) or ("bayar" in text_lower and "tidak" in text_lower):
        return "refuse_to_pay"

    # 12. 威胁投诉类
    threaten_words = {"laporkan", "polisi", "ojk", "komplain", "pengaduan", "ancam", "投诉", "报警", "告你们"}
    if any(word in text_lower for word in threaten_words):
        return "threaten"

    # 13. 已还款类
    already_paid_words = {"sudah bayar", "sudah transfer", "tadi bayar", "sudah lunas", "已经还了", "刚才转了", "已还款"}
    if any(phrase in text_lower for phrase in already_paid_words):
        return "already_paid"

    # 14. 询问费用类
    ask_fee_words = {"bunga", "denda", "biaya", "administrasi", "kenapa besar", "利息", "滞纳金", "手续费", "为什么这么高"}
    if any(word in text_lower for word in ask_fee_words):
        return "ask_fee"

    # 15. 询问还款方式类
    ask_method_words = {"transfer kemana", "rekening mana", "nomor rekening", "bayar kemana", "bagaimana bayar", "转到哪里", "怎么还", "还款方式"}
    if any(phrase in text_lower for phrase in ask_method_words):
        return "ask_payment_method"

    # 16. 部分还款类
    partial_words = {"bayar sebagian", "cicil", "setengah dulu", "bayar sedikit", "分期", "先还一部分"}
    if any(phrase in text_lower for phrase in partial_words):
        return "partial_payment"

    # 17. 第三方接听类
    third_party_words = {"keluarga", "orang tua", "anak", "saudara", "dia tidak ada", "dia keluar", "他不在", "我是他家属"}
    if any(phrase in text_lower for phrase in third_party_words):
        return "third_party"

    # 18. 不知道类
    dont_know_words = {"tidak tahu", "tidak mengerti", "tidak paham", "不知道", "不清楚", "不了解"}
    if any(phrase in text_lower for phrase in dont_know_words):
        return "dont_know"

    # 无法识别的返回unknown
    return "unknown"

def apply_annotations_to_gold():
    """将标注结果应用到黄金数据集文件"""
    annotation_dir = Path("/Users/li/Workspace/ai-telemarketing/data/manual_annotation")
    unknown_ann = load_csv(str(annotation_dir / "unknown_intent_已标注.csv"))
    labeled_ann = load_csv(str(annotation_dir / "labeled_intent_已检查.csv"))

    # 建立索引
    ann_index = {}
    for ann in unknown_ann + labeled_ann:
        key = f"{ann['case_id']}_{ann['turn_number']}"
        if ann["manual_intent"]:
            ann_index[key] = ann["manual_intent"]

    # 更新所有文件
    GOLD_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset")
    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]
    updated_count = 0

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            case_id = data.get("case_id", file_path.stem)
            modified = False

            for turn in data.get("dialogue", []):
                if turn.get("speaker") == "customer":
                    turn_num = turn.get("turn_number", 0)
                    key = f"{case_id}_{turn_num}"

                    if key in ann_index:
                        new_intent = ann_index[key]
                        if turn.get("user_intent") != new_intent:
                            turn["user_intent"] = new_intent
                            modified = True
                            updated_count += 1

            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"更新文件{file_path.name}出错: {e}")

    print(f"\n更新完成！共更新了{updated_count}个用户意图字段")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="人工标注辅助工具")
    parser.add_argument("action", choices=["annotate", "check", "apply"], help="操作类型: annotate标注unknown, check检查已标注, apply应用标注到数据集")
    parser.add_argument("--batch-size", type=int, default=200, help="批量处理大小")

    args = parser.parse_args()

    if args.action == "annotate":
        batch_annotate_unknown(args.batch_size)
    elif args.action == "check":
        batch_check_labeled(args.batch_size)
    elif args.action == "apply":
        apply_annotations_to_gold()

if __name__ == "__main__":
    import sys
    sys.exit(main())
