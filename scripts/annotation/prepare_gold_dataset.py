#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
准备黄金数据集，从有效对话中筛选代表性样本，优先选择稀有场景
"""
import json
from pathlib import Path
import re
from collections import defaultdict

# 定义场景分类关键词
SCENARIO_KEYWORDS = {
    "success": [
        "janji", "oke", "ya", "akan bayar", "tanggal", "jam",
        "baik", "siap", "tidak masalah", "nanti bayar"
    ],
    "failure": [
        "tidak mau", "tidak bisa", "jangan telepon lagi", "saya tidak punya hutang",
        "salah nomor", "tidak kenal", "gantung telepon", "tidak ada uang"
    ],
    "negotiation": [
        "perpanjang", "nanti dulu", "cicil", "kurangi", "bunga terlalu tinggi",
        "tidak bisa bayar penuh", "baru bisa bulan depan", "bisakah dikurangi"
    ],
    "high_resistance": [
        "kamu siapa", "buktikan kamu dari Extra", "saya akan laporkan",
        "jangan ganggu saya", "saya akan hubungi polisi", "ancam", "marah"
    ],
    "silent": [
        "diam", "tidak jawab", "suara bising", "hanya mendengarkan"
    ],
    "forgetful": [
        "saya lupa", "apakah benar ada hutang?", "saya tidak ingat",
        "kapan pinjam?", "berapa jumlahnya?"
    ],
    "excuse_master": [
        "saya sakit", "anak sakit", "usaha rugi", "diberhentikan",
        "bencana alam", "keluarga meninggal", "kehilangan dompet"
    ],
    "busy": [
        "saya sedang rapat", "saya sedang mengemudi", "nanti telepon kembali",
        "saya sibuk", "tidak ada waktu bicara"
    ]
}

# 催收阶段关键词
STAGE_KEYWORDS = {
    "greeting": ["halo", "selamat pagi", "selamat siang", "selamat sore", "apa kabar"],
    "identity": ["nama saya", "dari aplikasi Extra", "dengan Bapak/Ibu", "bisa bicara dengan"],
    "purpose": ["tagihan", "pinjaman", "hutang", "jatuh tempo", "pembayaran"],
    "ask_time": ["kapan bayar", "tanggal berapa", "jam berapa", "bisa bayar kapan"],
    "push": ["segera bayar", "hari ini harus bayar", "batas waktu", "denda", "bunga"],
    "negotiate": ["bagaimana jika", "bisakah", "perpanjang", "cicil"],
    "commit": ["janji", "oke", "ya", "tanggal", "jam", "pasti bayar"],
    "close": ["terima kasih", "selamat tinggal", "saya tutup telepon"]
}

def classify_dialogue(text):
    """分类对话场景"""
    text_lower = text.lower()
    categories = []

    # 检查失败场景（最高优先级）
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["failure"]):
        categories.append("failure")

    # 检查协商场景
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["negotiation"]):
        categories.append("negotiation")

    # 检查高抗拒场景
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["high_resistance"]):
        categories.append("high_resistance")

    # 检查其他用户类型
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["busy"]):
        categories.append("busy")
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["forgetful"]):
        categories.append("forgetful")
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["excuse_master"]):
        categories.append("excuse_master")
    if any(kw in text_lower for kw in SCENARIO_KEYWORDS["silent"]):
        categories.append("silent")

    # 默认是成功场景
    if not categories or any(kw in text_lower for kw in SCENARIO_KEYWORDS["success"]):
        categories.append("success")

    return categories

def analyze_dialogue_stages(text):
    """分析对话覆盖的阶段"""
    text_lower = text.lower()
    stages = []
    for stage, keywords in STAGE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            stages.append(stage)
    return stages

def estimate_resistance_level(text):
    """估算用户抗拒程度"""
    text_lower = text.lower()

    # 非常高抗拒
    high_resistance_signals = [
        "jangan telepon lagi", "saya tidak mau bayar", "saya akan laporkan",
        "tidak punya hutang", "salah nomor", "gantung telepon"
    ]
    if any(sig in text_lower for sig in high_resistance_signals):
        return "very_high"

    # 高抗拒
    medium_high_signals = [
        "tidak bisa bayar", "tidak ada uang", "perpanjang", "saya sibuk",
        "bunga terlalu tinggi", "kenapa jumlahnya begitu banyak"
    ]
    if any(sig in text_lower for sig in medium_high_signals):
        return "high"

    # 中等抗拒
    medium_signals = [
        "nanti dulu", "saya perlu cek dulu", "saya lupa", "bisakah dikurangi",
        "saya belum menerima gaji"
    ]
    if any(sig in text_lower for sig in medium_signals):
        return "medium"

    # 低抗拒
    low_signals = [
        "oke", "ya", "saya akan bayar", "tanggal", "jam", "baik",
        "saya ingat", "tidak masalah"
    ]
    if any(sig in text_lower for sig in low_signals):
        return "low"

    # 非常低抗拒
    return "very_low"

def main():
    # 加载有效对话列表
    with open("data/valid_transcripts.json", "r", encoding="utf-8") as f:
        valid_files = json.load(f)

    print(f"共有 {len(valid_files)} 个有效对话文件")

    # 分析所有对话
    analyzed_files = []
    category_counts = defaultdict(int)
    resistance_counts = defaultdict(int)
    stage_counts = defaultdict(int)

    for file_info in valid_files:
        file_path = Path("data/processed/transcripts") / file_info["file"]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 合并文本
            text = file_info["text"]
            turns = file_info["turns"]
            duration = file_info["duration"]

            # 分类
            categories = classify_dialogue(text)
            resistance_level = estimate_resistance_level(text)
            stages = analyze_dialogue_stages(text)

            # 计算优先级（稀有场景优先）
            priority = 0
            if "failure" in categories:
                priority += 10  # 失败场景最高优先级
            if "high_resistance" in categories:
                priority += 8
            if "negotiation" in categories:
                priority += 6
            if "excuse_master" in categories:
                priority += 5
            if "forgetful" in categories:
                priority += 4
            if "busy" in categories:
                priority += 3
            if "silent" in categories:
                priority += 2

            # 对话越长阶段越完整优先级越高
            priority += min(len(stages) / 8 * 3, 3)

            analyzed = {
                "file": file_info["file"],
                "text": text,
                "turns": turns,
                "duration": duration,
                "categories": categories,
                "resistance_level": resistance_level,
                "stages": stages,
                "stage_count": len(stages),
                "priority": priority,
                "collection_stage": "H2"  # 默认H2，后续可以优化
            }

            analyzed_files.append(analyzed)

            # 更新统计
            for cat in categories:
                category_counts[cat] += 1
            resistance_counts[resistance_level] += 1
            for stage in stages:
                stage_counts[stage] += 1

        except Exception as e:
            print(f"处理文件 {file_info['file']} 失败: {e}")

    # 输出统计
    print("\n=== 对话场景分布 ===")
    for cat, count in category_counts.items():
        print(f"{cat}: {count} ({count/len(analyzed_files)*100:.1f}%)")

    print("\n=== 抗拒程度分布 ===")
    for level, count in resistance_counts.items():
        print(f"{level}: {count} ({count/len(analyzed_files)*100:.1f}%)")

    print("\n=== 对话阶段分布 ===")
    for stage, count in stage_counts.items():
        print(f"{stage}: {count} ({count/len(analyzed_files)*100:.1f}%)")

    # 按优先级排序
    analyzed_files.sort(key=lambda x: x["priority"], reverse=True)

    # 选择200个样本，保证场景覆盖
    selected = []
    category_used = defaultdict(int)
    resistance_used = defaultdict(int)

    # 首先确保所有稀有场景都被选中（所有非success的都是稀有）
    for dialog in analyzed_files:
        if len(selected) >= 200:
            break

        # 优先选稀有类别：所有包含非success类别的都优先
        is_rare = any(cat != "success" for cat in dialog["categories"])
        if is_rare:
            selected.append(dialog)
            for cat in dialog["categories"]:
                category_used[cat] += 1
            resistance_used[dialog["resistance_level"]] += 1
            continue

    # 然后补充success类别，优先选对话质量高的（轮数多、阶段覆盖全、时长适中）
    # 按对话质量排序：阶段数多 > 轮数多 > 优先级高
    success_files = [d for d in analyzed_files if d not in selected and "success" in d["categories"]]
    success_files_sorted = sorted(success_files, key=lambda x: (x["stage_count"], x["turns"], x["priority"]), reverse=True)

    for dialog in success_files_sorted:
        if len(selected) >= 200:
            break

        selected.append(dialog)
        for cat in dialog["categories"]:
            category_used[cat] += 1
        resistance_used[dialog["resistance_level"]] += 1

    print(f"\n=== 已选择 {len(selected)} 个样本进行标注 ===")
    print("选择后的类别分布:")
    for cat, count in category_used.items():
        print(f"{cat}: {count}")

    print("\n抗拒程度分布:")
    for level, count in resistance_used.items():
        print(f"{level}: {count}")

    # 生成标注列表
    annotation_list = []
    for i, dialog in enumerate(selected, 1):
        annotation_item = {
            "id": f"GOLD-{i:03d}",
            "file": dialog["file"],
            "priority": dialog["priority"],
            "categories": dialog["categories"],
            "resistance_level": dialog["resistance_level"],
            "turns": dialog["turns"],
            "duration": dialog["duration"],
            "stage_count": dialog["stage_count"],
            "status": "pending",
            "notes": ""
        }
        annotation_list.append(annotation_item)

    # 保存标注列表
    output_file = Path("data/gold_dataset_annotation_list.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "description": "黄金数据集标注列表，按优先级排序",
            "total": len(annotation_list),
            "generated_at": "2026-05-03",
            "annotation_template": "data/gold_dataset_annotation_template.json",
            "items": annotation_list
        }, f, ensure_ascii=False, indent=2)

    # 生成简化版CSV方便标注
    csv_content = "ID,文件名,优先级,场景类别,抗拒程度,对话轮数,时长,阶段数,状态,备注\n"
    for item in annotation_list:
        csv_content += f"{item['id']},{item['file']},{item['priority']},{'/'.join(item['categories'])},{item['resistance_level']},{item['turns']},{item['duration']},{item['stage_count']},{item['status']},{item['notes']}\n"

    csv_file = Path("data/gold_dataset_annotation_list.csv")
    with open(csv_file, "w", encoding="utf-8-sig") as f:
        f.write(csv_content)

    print(f"\n标注列表已保存:")
    print(f"  - JSON格式: {output_file}")
    print(f"  - CSV格式: {csv_file}")
    print("\n接下来可以开始标注工作，优先标注高优先级的稀有场景样本。")

    # 打印前10个最高优先级样本预览
    print("\n=== 前10个最高优先级样本预览 ===")
    for i, item in enumerate(annotation_list[:10], 1):
        print(f"{i:2d}. {item['id']}: {item['file']} - 类别: {', '.join(item['categories'])} - 抗拒程度: {item['resistance_level']}")

if __name__ == "__main__":
    main()
