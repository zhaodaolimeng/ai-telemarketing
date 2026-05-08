#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量标注黄金数据集脚本，自动处理转写错误，生成标准化标注文件
"""
import json
import os
from pathlib import Path
from datetime import datetime

# 印尼语ASR常见错误修正映射
ASR_CORRECTIONS = {
    "nasian": "lunas",
    "puluh nasian": "penuh lunas",
    "tempat": "tempo",
    "Hajianya": "tagihan Anda",
    "Ufah Nau": "Uang",
    "Kuala": "Nanti lah",
    "kemaren": "hari ini",
    "tunggu": "bayar",
    "Jalan waktu itu": "Baik, jam 10 ya"
}

# 意图标准化映射
INTENT_MAPPING = {
    "selamat pagi": "respond_to_greeting",
    "oh iya": "acknowledge_debt",
    "pilih lunas": "choose_full_repayment",
    "pilih perpanjangan": "choose_extension",
    "saya berikan": "confirm_repayment_intention",
    "jam [0-9]+": "propose_repayment_time",
    "tidak ada uang": "cannot_repay_now",
    "sibuk nanti": "user_busy",
    "salah nomor": "wrong_number",
    "laporkan OJK": "threaten_complaint",
    "mana buktinya": "question_identity"
}

# 对话阶段映射
STAGE_MAPPING = {
    "greeting": ["selamat pagi", "halo", "permisi"],
    "identity_verification": ["nama bapak", "pak ", "ibu ", "dengan bapak"],
    "purpose": ["tagihan", "jatuh tempo", "pinjaman", "bayar"],
    "negotiation": ["perpanjangan", "tidak ada uang", "nanti", "bisa tidak"],
    "ask_time": ["kapan", "jam berapa", "tanggal berapa"],
    "push": ["segera", "harus bayar", "jatuh tempo"],
    "confirm": ["oke", "baik", "ya", "saya catat"],
    "close": ["terima kasih", "sampai jumpa", "selamat tinggal"]
}

def correct_asr_errors(text):
    """修正ASR识别错误"""
    text = text.strip()
    for error, correct in ASR_CORRECTIONS.items():
        text = text.replace(error, correct)
    return text

def detect_intent(text, speaker):
    """检测用户意图，仅对customer进行标注"""
    if speaker != "customer":
        return ""
    text_lower = text.lower()
    for pattern, intent in INTENT_MAPPING.items():
        if pattern in text_lower:
            return intent
    return "unknown_intent"

def detect_stage(text):
    """检测对话阶段"""
    text_lower = text.lower()
    for stage, patterns in STAGE_MAPPING.items():
        for pattern in patterns:
            if pattern in text_lower:
                return stage
    return "negotiation"

def is_successful(dialogue):
    """判断催收是否成功"""
    success_keywords = ["bayar", "lunas", "perpanjangan", "jam ", "tanggal "]
    for turn in dialogue:
        if turn["speaker"] == "customer":
            text = turn["text"].lower()
            if any(k in text for k in success_keywords) and "tidak" not in text:
                return True
    return False

def has_violation(dialogue):
    """检查是否有合规违规"""
    violation_keywords = ["ancam", "polisi", "OJK", "keluarga", "rumah", "tekan"]
    for turn in dialogue:
        if turn["speaker"] == "agent":
            text = turn["text"].lower()
            if any(k in text for k in violation_keywords):
                return True, f"Matched violation keyword: {[k for k in violation_keywords if k in text]}"
    return False, ""

def annotate_transcript(transcript_file, output_dir):
    """标注单个转写文件"""
    with open(transcript_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    case_id = Path(transcript_file).stem
    transcript_with_speakers = data.get("transcript_with_speakers", [])
    if not transcript_with_speakers:
        return False

    # 处理对话内容
    dialogue = []
    turn_num = 1
    current_stage = "greeting"

    for turn in transcript_with_speakers:
        raw_text = turn.get("text", "").strip()
        if not raw_text:
            continue

        # 修正ASR错误
        corrected_text = correct_asr_errors(raw_text)
        speaker = turn.get("speaker", "AGENT").lower()

        # 检测阶段和意图
        stage = detect_stage(corrected_text)
        if stage:
            current_stage = stage
        intent = detect_intent(corrected_text, speaker)

        # 判断是否正确（默认agent话术正确，customer无对错）
        is_correct = True if speaker == "agent" else None

        dialogue.append({
            "turn_number": turn_num,
            "speaker": speaker,
            "text": corrected_text,
            "stage": current_stage,
            "is_correct": is_correct,
            "standard_response": "",
            "user_intent": intent,
            "notes": f"Original ASR: '{raw_text}'" if corrected_text != raw_text else ""
        })
        turn_num += 1

    # 基础信息判断
    call_duration = data.get("transcript", [])[-1].get("end", 0) if data.get("transcript") else 0
    success = is_successful(dialogue)
    has_viol, viol_details = has_violation(dialogue)

    # 生成标注文件
    annotation = {
        "version": "1.0",
        "case_id": case_id,
        "basic_info": {
            "collection_stage": "H2",
            "call_duration": round(call_duration, 2),
            "call_result": "success" if success else "failure"
        },
        "user_profile": {
            "persona": "cooperative" if success else "resistant",
            "resistance_level": "low" if success else "high"
        },
        "dialogue": dialogue,
        "compliance": {
            "has_violation": has_viol,
            "violation_details": viol_details
        },
        "annotation_info": {
            "labeler": "ai-annotator",
            "label_time": datetime.now().strftime("%Y-%m-%d"),
            "notes": f"Total {turn_num-1} turns, {'contains ASR errors' if any(t['notes'] for t in dialogue) else 'good quality transcript'}"
        }
    }

    # 保存标注文件
    output_file = output_dir / f"{case_id}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(annotation, f, ensure_ascii=False, indent=2)

    return True, annotation, annotation

def main():
    # 路径配置
    _project_root = Path(__file__).resolve().parent.parent.parent
    transcripts_dir = _project_root / "data/processed/transcripts"
    output_dir = _project_root / "data/gold_dataset"
    annotation_list_file = _project_root / "data/gold_dataset_annotation_list.json"

    # 读取现有标注列表
    with open(annotation_list_file, 'r', encoding='utf-8') as f:
        annotation_list = json.load(f)

    # 获取已标注文件
    existing_files = {f["file"] for f in annotation_list["items"] if f["status"] == "completed"}
    print(f"Existing annotated files: {len(existing_files)}")

    # 获取待标注文件（按优先级取147个）
    pending_files = [f for f in annotation_list["items"] if f["status"] == "pending"][:147]
    print(f"Files to annotate: {len(pending_files)}")

    # 批量标注
    completed = 0
    for item in pending_files:
        filename = item["file"]
        transcript_file = transcripts_dir / filename
        if not transcript_file.exists():
            print(f"File not found: {filename}")
            continue

        try:
            result = annotate_transcript(transcript_file, output_dir)
            if result:
                success, annotation = result
                # 更新标注列表
                item["status"] = "completed"
                item["notes"] = annotation["annotation_info"]["notes"]
                completed += 1
                if completed % 10 == 0:
                    print(f"Completed {completed}/{len(pending_files)} files")
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue

    # 保存更新后的标注列表
    with open(annotation_list_file, 'w', encoding='utf-8') as f:
        json.dump(annotation_list, f, ensure_ascii=False, indent=2)

    print(f"\nBatch annotation completed! Total annotated: {completed} files")
    print(f"Total gold dataset size now: {len([f for f in annotation_list['items'] if f['status'] == 'completed'])}")

if __name__ == "__main__":
    main()
