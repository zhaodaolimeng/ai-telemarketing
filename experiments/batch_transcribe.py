#!/usr/bin/env python3
"""
批量转写新增音频
"""
import json
from pathlib import Path
from scripts.transcribe import transcribe_audio, diarize_speakers, merge_transcript_and_diarization


def main():
    print("="*60)
    print("批量转写音频文件")
    print("="*60)

    chat_sample_dir = Path("data/chat-sample")
    transcripts_dir = Path("data/processed/transcripts")
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    # 找到所有文件
    all_audio = sorted(list(chat_sample_dir.glob("*.mp3")) + list(chat_sample_dir.glob("*.wav")))
    transcribed = [f.stem for f in transcripts_dir.glob("*.json")]

    # 筛选未转写的
    untranscribed = []
    for audio in all_audio:
        if audio.stem not in transcribed:
            untranscribed.append(audio)

    print(f"总音频数: {len(all_audio)}")
    print(f"已转写: {len(transcribed)}")
    print(f"待转写: {len(untranscribed)}")

    # 先转写20个测试
    to_transcribe = untranscribed[:20] if untranscribed else []
    print(f"\n将转写 {len(to_transcribe)} 个文件...")

    success_count = 0
    for i, audio_file in enumerate(to_transcribe, 1):
        print(f"\n[{i}/{len(to_transcribe)}] {audio_file.name}")
        try:
            transcript = transcribe_audio(str(audio_file))
            diarization = diarize_speakers(str(audio_file))
            merged = merge_transcript_and_diarization(transcript, diarization)

            result = {
                "case_id": audio_file.stem,
                "file_name": audio_file.name,
                "transcript": transcript,
                "transcript_with_speakers": merged,
                "full_text": " ".join([seg["text"] for seg in transcript])
            }

            output_file = transcripts_dir / f"{audio_file.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"  OK 保存到: {output_file}")
            success_count += 1

        except Exception as e:
            print(f"  ERROR 失败: {e}")

    print("\n" + "="*60)
    print(f"完成！成功: {success_count}/{len(to_transcribe)}")
    print("="*60)


if __name__ == "__main__":
    main()
