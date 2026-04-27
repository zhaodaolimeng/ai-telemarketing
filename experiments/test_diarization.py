#!/usr/bin/env python3
"""
测试说话人分离功能
"""
from pathlib import Path
from scripts.transcribe import diarize_speakers, transcribe_audio, merge_transcript_and_diarization
import json


def main():
    print("=" * 60)
    print("测试说话人分离功能")
    print("=" * 60)

    # 测试文件
    audio_file = Path("data/chat-sample/628214113416508-20260415071920.mp3")
    if not audio_file.exists():
        print(f"文件不存在: {audio_file}")
        return

    print(f"\n处理文件: {audio_file.name}")
    print("\n1. 转写音频...")
    transcript = transcribe_audio(str(audio_file))
    print(f"   得到 {len(transcript)} 个片段")

    print("\n2. 说话人分离...")
    diarization = diarize_speakers(str(audio_file))
    print(f"   得到 {len(diarization)} 个说话人片段")

    print("\n3. 合并结果...")
    merged = merge_transcript_and_diarization(transcript, diarization)

    print("\n4. 显示前几个合并结果:")
    print("-" * 60)
    for i, seg in enumerate(merged[:10]):
        print(f"[{i+1}] [{seg['start']:.2f}s->{seg['end']:.2f}s] {seg['speaker']:10}: {seg['text']}")

    # 保存结果
    output_file = Path("data/processed/test_diarization_result.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "file_name": audio_file.name,
            "transcript_with_speakers": merged
        }, f, ensure_ascii=False, indent=2)

    print(f"\n完整结果已保存到: {output_file}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
