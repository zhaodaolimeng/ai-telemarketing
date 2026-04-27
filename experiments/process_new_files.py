#!/usr/bin/env python3
"""
处理新增的音频文件 - 转写 + 结合标签分析
"""
import pandas as pd
import json
from pathlib import Path
from scripts.transcribe import transcribe_audio, diarize_speakers, merge_transcript_and_diarization


def read_labels(label_file: Path):
    """读取标签文件"""
    print(f"读取标签文件: {label_file}")
    df = pd.read_excel(label_file)
    print(f"  共 {len(df)} 条标签")
    print(f"  列: {list(df.columns)}")
    return df


def get_untranscribed_files(chat_sample_dir: Path, transcripts_dir: Path):
    """获取还没转写的文件列表"""
    all_audio = list(chat_sample_dir.glob("*.mp3")) + list(chat_sample_dir.glob("*.wav"))
    transcribed = [f.stem for f in transcripts_dir.glob("*.json")]

    untranscribed = []
    for audio in all_audio:
        if audio.stem not in transcribed:
            untranscribed.append(audio)

    return sorted(untranscribed)


def transcribe_new_files(audio_files: list, output_dir: Path):
    """转写新增的音频文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, audio_file in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] 转写: {audio_file.name}")

        try:
            # 转写
            transcript = transcribe_audio(str(audio_file))
            print(f"  得到 {len(transcript)} 个片段")

            # 说话人分离
            diarization = diarize_speakers(str(audio_file))
            merged = merge_transcript_and_diarization(transcript, diarization)

            result = {
                "case_id": audio_file.stem,
                "file_name": audio_file.name,
                "transcript": transcript,
                "transcript_with_speakers": merged,
                "full_text": " ".join([seg["text"] for seg in transcript])
            }

            # 保存
            output_file = output_dir / f"{audio_file.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            results.append(result)
            print(f"  已保存: {output_file}")

        except Exception as e:
            print(f"  处理失败: {e}")

    return results


def quick_analysis(labels_df, transcripts_dir: Path):
    """结合标签进行快速分析"""
    print("\n" + "="*60)
    print("快速分析")
    print("="*60)

    # 基本统计
    print(f"\n标签总数: {len(labels_df)}")

    # 检查列名并统计
    print("\n标签列:")
    for col in labels_df.columns:
        print(f"  - {col}")
        if labels_df[col].dtype == "object":
            print(f"    唯一值: {labels_df[col].nunique()}")

    # 尝试找结果相关列
    result_cols = [c for c in labels_df.columns if "result" in c.lower() or "keputusan" in c.lower() or "hasil" in c.lower()]
    if result_cols:
        print(f"\n结果列: {result_cols}")
        for col in result_cols:
            print(f"\n{col} 分布:")
            print(labels_df[col].value_counts())

    # 读取已转写的文件，统计数据
    transcript_files = list(transcripts_dir.glob("*.json"))
    print(f"\n已转写文件: {len(transcript_files)}")

    # 尝试匹配标签和转写
    print(f"\n标签中的文件数: {len(labels_df)}")
    if "file" in str(labels_df.columns).lower() or "filename" in str(labels_df.columns).lower():
        file_col = [c for c in labels_df.columns if "file" in c.lower()][0] if [c for c in labels_df.columns if "file" in c.lower()] else None
        if file_col:
            matched = len(set(labels_df[file_col].dropna()) & set([f.stem for f in transcript_files]))
            print(f"匹配的文件数: {matched}")

    print("\n" + "="*60)
    print("分析完成！")
    print("="*60)


def main():
    print("="*60)
    print("处理新增音频文件")
    print("="*60)

    # 路径
    chat_sample_dir = Path("data/chat-sample")
    transcripts_dir = Path("data/processed/transcripts")
    label_file = Path("data/label-chat-sample.xlsx")

    # 1. 读取标签
    labels_df = None
    if label_file.exists():
        labels_df = read_labels(label_file)

    # 2. 找到未转写的文件
    untranscribed = get_untranscribed_files(chat_sample_dir, transcripts_dir)
    print(f"\n找到 {len(untranscribed)} 个未转写的音频文件")

    # 3. 转写新增文件
    if untranscribed:
        print("开始转写...")
        transcribe_new_files(untranscribed[:10], transcripts_dir)  # 先转写10个测试
    else:
        print("所有文件都已转写！")

    # 4. 快速分析
    if labels_df is not None:
        quick_analysis(labels_df, transcripts_dir)


if __name__ == "__main__":
    main()
