#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量转写所有剩余文件
"""
import json
from pathlib import Path
from scripts.transcribe import transcribe_audio, diarize_speakers, merge_transcript_and_diarization


def main():
    print("="*70)
    print("批量转写所有剩余音频文件")
    print("="*70)

    chat_sample_dir = Path("data/chat-sample")
    transcripts_dir = Path("data/processed/transcripts")
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    # 找到所有文件
    all_audio = sorted(list(chat_sample_dir.glob("*.mp3")) + list(chat_sample_dir.glob("*.wav")))
    transcribed = set([f.stem for f in transcripts_dir.glob("*.json")])

    # 筛选未转写的
    untranscribed = []
    for audio in all_audio:
        if audio.stem not in transcribed:
            untranscribed.append(audio)

    print(f"总音频数: {len(all_audio)}")
    print(f"已转写: {len(transcribed)}")
    print(f"待转写: {len(untranscribed)}")

    # 转写所有剩余的
    to_transcribe = untranscribed
    print(f"\n开始转写: {len(to_transcribe)} 个文件...")

    success_count = 0
    for i, audio_file in enumerate(to_transcribe, 1):
        try:
            transcript = transcribe_audio(str(audio_file))
            diarization = diarize_speakers(str(audio_file), transcript)
            merged = merge_transcript_and_diarization(transcript, diarization)

            result = {
                "case_id": audio_file.stem,
                "file_name": audio_file.name,
                "transcript": merged,
                "full_text": " ".join([seg["text"] for seg in merged])
            }
            output_file = transcripts_dir / f"{audio_file.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            success_count += 1
            if i % 10 == 0:
                print(f"  [{i}/{len(to_transcribe)}] 已转写 {i} 个文件...")
        except Exception as e:
            print(f"  错误处理 {audio_file.name}: {e}")

    print("\n" + "="*70)
    print(f"完成！本次成功: {success_count}/{len(to_transcribe)}")
    print(f"总已转写: {len(transcribed) + success_count}")
    print("="*70)


if __name__ == "__main__":
    main()
