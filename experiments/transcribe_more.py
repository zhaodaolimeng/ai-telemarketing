#!/usr/bin/env python3
"""
批量转写更多文件（每次50个，避免时间过长）
"""
import json
from pathlib import Path
from scripts.transcribe import transcribe_audio


def main():
    print("="*70)
    print("批量转写更多音频文件")
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

    # 本次转写50个
    batch_size = 50
    to_transcribe = untranscribed[:batch_size]
    print(f"\n本次转写: {len(to_transcribe)} 个文件...")

    success_count = 0
    for i, audio_file in enumerate(to_transcribe, 1):
        try:
            transcript = transcribe_audio(str(audio_file))
            result = {
                "case_id": audio_file.stem,
                "file_name": audio_file.name,
                "transcript": transcript,
                "full_text": " ".join([seg["text"] for seg in transcript])
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
