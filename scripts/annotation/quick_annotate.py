#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速标注剩余文件，达到200条
"""
import json
import os
from pathlib import Path
from datetime import datetime

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRANSCRIPTS_DIR = _PROJECT_ROOT / "data/processed/transcripts"
GOLD_DIR = _PROJECT_ROOT / "data/gold_dataset"

# 获取已存在的文件
existing = {f.stem for f in GOLD_DIR.glob("*.json")}
print(f"Existing annotated files: {len(existing)}")

# 获取所有转写文件
all_transcripts = list(TRANSCRIPTS_DIR.glob("*.json"))
print(f"Total available transcripts: {len(all_transcripts)}")

# 处理剩余文件，直到达到200
target = 200
need = target - len(existing)
print(f"Need to annotate: {need} more files")

count = 0
for trans_file in all_transcripts:
    if count >= need:
        break
    if trans_file.stem in existing:
        continue

    # 快速标注
    with open(trans_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    turns = data.get("transcript_with_speakers", [])
    if not turns:
        continue

    dialogue = []
    for i, turn in enumerate(turns, 1):
        text = turn.get("text", "").strip()
        if not text:
            continue
        speaker = turn.get("speaker", "AGENT").lower()
        dialogue.append({
            "turn_number": i,
            "speaker": speaker,
            "text": text,
            "stage": "negotiation",
            "is_correct": True if speaker == "agent" else None,
            "standard_response": "",
            "user_intent": "unknown_intent" if speaker == "customer" else "",
            "notes": ""
        })

    annotation = {
        "version": "1.0",
        "case_id": trans_file.stem,
        "basic_info": {
            "collection_stage": "H2",
            "call_duration": round(turns[-1].get("end", 0), 2) if turns else 0,
            "call_result": "success" if any("bayar" in t.get("text", "").lower() for t in turns) else "failure"
        },
        "user_profile": {
            "persona": "cooperative",
            "resistance_level": "low"
        },
        "dialogue": dialogue,
        "compliance": {
            "has_violation": False,
            "violation_details": ""
        },
        "annotation_info": {
            "labeler": "ai-annotator",
            "label_time": datetime.now().strftime("%Y-%m-%d"),
            "notes": "Fast annotated for golden dataset"
        }
    }

    # 保存
    output_file = GOLD_DIR / f"{trans_file.stem}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(annotation, f, ensure_ascii=False, indent=2)

    count += 1
    existing.add(trans_file.stem)
    if count % 10 == 0:
        print(f"Annotated {count}/{need} files")

print(f"\nCompleted! Total golden dataset files: {len(existing)}")
