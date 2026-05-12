#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量ASR转写，基于 Faster-Whisper (CTranslate2)。
用法与之前一致：python scripts/batch_asr_transcribe.py
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_INPUT = _PROJECT_ROOT / "data/raw/recordings"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "data/processed/transcripts"


def transcribe_file(model, audio_path: Path, language: str = "id") -> Dict:
    segments_raw, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
    )

    segments = []
    full_text = ""
    for seg in segments_raw:
        words = []
        if seg.words:
            for w in seg.words:
                words.append({
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 3),
                })
        segments.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
        })
        full_text += seg.text

    transcript_with_speakers = []
    current_speaker = "AGENT"
    for seg in segments:
        s = {**seg, "speaker": current_speaker}
        transcript_with_speakers.append(s)
        current_speaker = "CUSTOMER" if current_speaker == "AGENT" else "AGENT"

    return {
        "case_id": audio_path.stem,
        "file_name": audio_path.name,
        "transcript": segments,
        "transcript_with_speakers": transcript_with_speakers,
        "full_text": full_text.strip(),
        "language": info.language,
        "duration": round(info.duration, 2),
    }


def main():
    from faster_whisper import WhisperModel

    parser = argparse.ArgumentParser(description="批量 ASR 转写 (Faster-Whisper)")
    parser.add_argument("--input", type=Path, default=_DEFAULT_INPUT,
                        help=f"输入目录 (default: {_DEFAULT_INPUT})")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT,
                        help=f"输出目录 (default: {_DEFAULT_OUTPUT})")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有转写")
    parser.add_argument("--watch", action="store_true", help="持续监听新文件")
    parser.add_argument("--interval", type=int, default=30, help="监听间隔/秒")
    parser.add_argument("--model-size", default="small", help="模型尺寸")
    parser.add_argument("--compute-type", default="int8",
                        help="量化类型: int8 / int8_float16 / float16")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"[ASR] 加载模型: faster-whisper {args.model_size} ({args.compute_type})")
    model = WhisperModel(
        args.model_size,
        device="cpu",
        compute_type=args.compute_type,
        num_workers=2,
    )

    def run_once():
        audio_files = sorted(args.input.glob("*.mp3"))
        if not audio_files:
            print("[ASR] 暂无 MP3 文件")
            return

        if not args.force:
            existing = {f.stem for f in args.output.glob("*.json")}
            new_files = [f for f in audio_files if f.stem not in existing]
            skipped = len(audio_files) - len(new_files)
            if skipped:
                print(f"[ASR] 跳过已转写: {skipped}, 待转写: {len(new_files)}")
            audio_files = new_files

        success = 0
        for i, ap in enumerate(audio_files):
            try:
                result = transcribe_file(model, ap)
                out_path = args.output / f"{result['case_id']}.json"
                out_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                dur = result.get("duration", 0)
                txt_preview = result["full_text"][:60] + "..." if len(result["full_text"]) > 60 else result["full_text"]
                print(f"  [{i+1}/{len(audio_files)}] {ap.name} ({dur}s) — {txt_preview}")
                success += 1
            except Exception as e:
                print(f"  [{i+1}/{len(audio_files)}] {ap.name} — FAILED: {e}")

        print(f"[ASR] 本轮: {success}/{len(audio_files)} 成功")

    if args.watch:
        print(f"[ASR] 监听模式: {args.input} (间隔 {args.interval}s)")
        while True:
            try:
                run_once()
            except Exception as e:
                print(f"[ASR] 本轮出错: {e}")
            time.sleep(args.interval)
    else:
        run_once()


if __name__ == "__main__":
    main()
