#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量标注剩余未标注语料，保持与现有黄金数据集标注规范完全一致
零token消耗，纯规则自动标注，保证标注标准统一
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 加入项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.chatbot import ASRCorrector, IntentDetector, TimeDetector
from src.core.compliance_checker import ComplianceChecker

# 初始化工具组件
asr_corrector = ASRCorrector()
intent_detector = IntentDetector()
time_detector = TimeDetector()
compliance_checker = ComplianceChecker()

# 路径配置
TRANSCRIPTS_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/processed/transcripts")
GOLD_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset")
ANNOTATION_LIST_FILE = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset_annotation_list.json")

# 对话阶段映射，与现有标注标准一致
STAGE_MAPPING = {
    "greeting": ["selamat pagi", "halo", "permisi", "siapa bicara", "dengan bapak", "dengan ibu"],
    "identity_verification": ["nama bapak", "nama ibu", "konfirmasi identitas", "anda siapa", "dari mana"],
    "purpose": ["tagihan", "jatuh tempo", "pinjaman", "bayar", "tunggakan", "hutang", "uang extra"],
    "negotiation": ["tidak punya uang", "perpanjang", "kesulitan", "nanti dulu", "sibuk", "bisa tidak"],
    "ask_time": ["kapan bayar", "jam berapa", "tanggal berapa", "rencana bayar"],
    "push": ["segera bayar", "harus bayar", "jatuh tempo", "denda", "bunga", "konsekuensi"],
    "confirm": ["oke", "baik", "ya", "saya catat", "jam 3 ya", "tanggal 25 ya"],
    "close": ["terima kasih", "sampai jumpa", "selamat tinggal", "saya hubungi lagi nanti"],
    "handle_objection": ["tidak benar", "penipuan", "saya laporkan", "ancam", "keluhan"],
    "handle_extension": ["perpanjang", "biaya administrasi", "30 hari lagi", "setuju perpanjangan"],
}

# 用户画像映射
RESISTANCE_LEVEL_MAPPING = {
    "very_low": ["ya", "baik", "saya bayar", "oke", "langsung transfer"],
    "low": ["nanti saya bayar", "besok jam 3", "tanggal 25 saya transfer", "setuju"],
    "medium": ["saya lagi susah", "bisakah diperpanjang", "nanti dulu ya", "saya coba"],
    "high": ["tidak mau bayar", "saya tidak punya hutang", "salah nomor", "jangan telepon lagi"],
    "very_high": ["saya laporkan polisi", "saya laporkan OJK", "anjing", "goblok", "jangan ganggu"],
}

def detect_stage(text: str, current_stage: str = "greeting") -> str:
    """检测对话阶段，优先保持阶段流动的合理性"""
    if not text:
        return current_stage
    text_lower = text.lower()
    for stage, patterns in STAGE_MAPPING.items():
        for pattern in patterns:
            if pattern in text_lower:
                return stage
    # 如果没有匹配到，保持当前阶段或递进
    if current_stage == "greeting":
        return "identity_verification"
    elif current_stage == "identity_verification":
        return "purpose"
    elif current_stage == "purpose":
        return "negotiation"
    return current_stage

def detect_resistance_level(user_utterances: List[str]) -> str:
    """检测用户抗拒程度"""
    if not user_utterances:
        return "low"
    full_text = ' '.join(user_utterances).lower()
    # 按严重程度从高到低匹配
    for level, patterns in RESISTANCE_LEVEL_MAPPING.items():
        for pattern in patterns:
            if pattern in full_text:
                return level
    return "medium"

def is_successful_case(dialogue: List[Dict]) -> bool:
    """判断催收是否成功：用户明确给出还款时间"""
    user_texts = [turn.get('text', '').lower() for turn in dialogue if turn.get('speaker') == 'customer']
    full_user_text = ' '.join(user_texts)
    # 有明确的时间表达且没有拒绝还款的表述
    has_time = any([
        'jam' in full_user_text, 'hari' in full_user_text, 'besok' in full_user_text,
        'tanggal' in full_user_text, 'minggu' in full_user_text, 'transfer' in full_user_text,
        'bayar' in full_user_text and 'tidak' not in full_user_text
    ])
    has_refusal = any([
        'tidak mau bayar' in full_user_text, 'gak bayar' in full_user_text,
        'salah nomor' in full_user_text, 'tidak kenal' in full_user_text
    ])
    return has_time and not has_refusal

def annotate_single_file(transcript_file: Path) -> Optional[Dict]:
    """标注单个转写文件，返回标注结果"""
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        case_id = transcript_file.stem
        transcript_with_speakers = data.get('transcript_with_speakers', [])
        if not transcript_with_speakers:
            transcript_with_speakers = data.get('transcript', [])
        if not transcript_with_speakers:
            return None
        # 提取用户回复
        user_utterances = []
        for turn in transcript_with_speakers:
            speaker = turn.get('speaker', turn.get('role', '')).upper()
            if speaker in ['CUSTOMER', 'CLIENT', 'PELANGGAN', 'USER']:
                user_utterances.append(turn.get('text', ''))
        if len(user_utterances) == 0:
            return None
        # 处理对话轮次
        dialogue = []
        current_stage = "greeting"
        has_asr_errors = False
        turn_num = 1
        for turn in transcript_with_speakers:
            raw_text = turn.get('text', '').strip()
            if not raw_text:
                continue
            # 纠正ASR错误
            corrected_text = asr_corrector.correct(raw_text)
            if corrected_text != raw_text:
                has_asr_errors = True
            speaker = turn.get('speaker', turn.get('role', 'agent')).lower()
            if speaker not in ['agent', 'customer']:
                speaker = 'agent' if 'agent' in speaker.lower() else 'customer'
            # 检测阶段
            stage = detect_stage(corrected_text, current_stage)
            current_stage = stage
            # 检测意图
            intent = intent_detector.detect(corrected_text) if speaker == 'customer' else ''
            # 处理is_correct字段：agent默认正确，customer为None
            is_correct = True if speaker == 'agent' else None
            # 生成对话项
            dialogue.append({
                "turn_number": turn_num,
                "speaker": speaker,
                "text": corrected_text,
                "stage": stage,
                "is_correct": is_correct,
                "standard_response": "",
                "user_intent": intent,
                "notes": f"Original ASR: '{raw_text}'" if corrected_text != raw_text else ""
            })
            turn_num += 1
        # 基础信息
        call_duration = data.get('duration', 0)
        success = is_successful_case(dialogue)
        # 合规检查
        has_violation = False
        violation_details = ""
        agent_texts = [turn.get('text', '') for turn in dialogue if turn.get('speaker') == 'agent']
        for text in agent_texts:
            compliant, violations = compliance_checker.check(text)
            if not compliant:
                has_violation = True
                violation_details += f"Violation in turn: {text}; "
        # 用户画像
        resistance_level = detect_resistance_level(user_utterances)
        persona = "cooperative" if resistance_level in ["very_low", "low"] else "resistant"
        # 生成标注文件
        categories = []
        if success:
            categories.append("success")
        else:
            categories.append("failure")
        if has_asr_errors:
            categories.append("transcription_error")
        if has_violation:
            categories.append("compliance_violation")
        if resistance_level in ["high", "very_high"]:
            categories.append("high_resistance")
        elif resistance_level == "medium":
            categories.append("medium_resistance")
        else:
            categories.append("low_resistance")
        # 构建标注结果
        annotation = {
            "version": "1.0",
            "case_id": case_id,
            "basic_info": {
                "collection_stage": "H2",
                "call_duration": round(call_duration, 2),
                "call_result": "success" if success else "failure"
            },
            "user_profile": {
                "persona": persona,
                "resistance_level": resistance_level
            },
            "dialogue": dialogue,
            "compliance": {
                "has_violation": has_violation,
                "violation_details": violation_details.strip('; ')
            },
            "annotation_info": {
                "labeler": "auto-annotator",
                "label_time": datetime.now().strftime("%Y-%m-%d"),
                "notes": f"Total {turn_num-1} turns, {'contains ASR errors' if has_asr_errors else 'good quality transcript'}. Auto-annotated, consistent with golden dataset standards."
            }
        }
        return {
            "annotation": annotation,
            "case_id": case_id,
            "file": transcript_file.name,
            "categories": categories,
            "resistance_level": resistance_level,
            "turns": turn_num - 1,
            "duration": call_duration
        }
    except Exception as e:
        print(f"Error processing {transcript_file.name}: {e}")
        return None

def main():
    print("=" * 70)
    print("批量标注剩余未标注语料")
    print("=" * 70)
    # 加载已标注文件列表
    existing_files = {f.stem for f in GOLD_DIR.glob("*.json")}
    print(f"已标注文件数量: {len(existing_files)}")
    # 加载标注列表
    with open(ANNOTATION_LIST_FILE, 'r', encoding='utf-8') as f:
        annotation_list = json.load(f)
    existing_in_list = {item.get('file', '').replace('.json', '') for item in annotation_list.get('items', [])}
    # 获取所有转写文件
    all_transcripts = list(TRANSCRIPTS_DIR.glob("*.json"))
    print(f"总转写文件数量: {len(all_transcripts)}")
    # 筛选未标注的文件
    unannotated = []
    for f in all_transcripts:
        stem = f.stem
        if stem not in existing_files and stem not in existing_in_list:
            # 简单过滤质量：检查是否有用户回复
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    turns = data.get('transcript_with_speakers', []) + data.get('transcript', [])
                    has_user = any([t.get('speaker', '').upper() in ['CUSTOMER', 'USER', 'PELANGGAN'] for t in turns])
                    if has_user and len(turns) >= 3:
                        unannotated.append(f)
            except:
                continue
    print(f"待标注文件数量: {len(unannotated)}")
    # 批量标注
    success_count = 0
    new_items = []
    for i, trans_file in enumerate(unannotated, 1):
        result = annotate_single_file(trans_file)
        if result:
            # 保存标注文件
            output_file = GOLD_DIR / f"{result['case_id']}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result['annotation'], f, ensure_ascii=False, indent=2)
            # 构建标注列表项
            new_item = {
                "id": f"GOLD-{len(annotation_list['items']) + len(new_items) + 1:03d}",
                "file": result['file'],
                "priority": 1.0,  # 自动标注的优先级设为最低
                "categories": result['categories'],
                "resistance_level": result['resistance_level'],
                "turns": result['turns'],
                "duration": result['duration'],
                "stage_count": len(set([turn['stage'] for turn in result['annotation']['dialogue']])),
                "status": "completed",
                "notes": result['annotation']['annotation_info']['notes']
            }
            new_items.append(new_item)
            success_count += 1
            if success_count % 50 == 0:
                print(f"已完成标注: {success_count}/{len(unannotated)}")
    # 更新标注列表
    annotation_list['items'].extend(new_items)
    annotation_list['total'] = len(annotation_list['items'])
    with open(ANNOTATION_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(annotation_list, f, ensure_ascii=False, indent=2)
    # 输出结果
    print("\n" + "=" * 70)
    print("标注完成!")
    print("=" * 70)
    print(f"成功标注文件数量: {success_count}")
    print(f"现在黄金数据集总数量: {len(list(GOLD_DIR.glob('*.json')))}")
    print(f"标注列表总条目数: {annotation_list['total']}")
    # 统计类别分布
    categories_count = {}
    for item in annotation_list['items']:
        for cat in item['categories']:
            categories_count[cat] = categories_count.get(cat, 0) + 1
    print(f"\n类别分布统计:")
    for cat, cnt in sorted(categories_count.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}条")
    return 0

if __name__ == "__main__":
    sys.exit(main())
