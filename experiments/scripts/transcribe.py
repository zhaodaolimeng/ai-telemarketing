"""
语音转写脚本
使用 Whisper 进行语音转写 + 说话人分离
"""
import os
import json
from pathlib import Path
from typing import List, Dict

# 可以使用 faster-whisper 或 openai-whisper
try:
    import faster_whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


def transcribe_audio(audio_path: str, model_size: str = "small", language: str = "id") -> List[Dict]:
    """
    转写单个音频文件

    Args:
        audio_path: 音频文件路径
        model_size: Whisper模型大小
        language: 语言 (id, en)

    Returns:
        转写结果列表，每个元素含 start, end, text
    """
    if not WHISPER_AVAILABLE:
        raise ImportError("Please install faster-whisper or openai-whisper")

    from faster_whisper import WhisperModel

    # 加载模型
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # 转写音频
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        word_timestamps=True
    )

    # 重新迭代获取内容（faster-whisper的generator特性）
    segments, _ = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        word_timestamps=True
    )

    # 返回带时间戳的结果
    result = []
    for segment in segments:
        seg_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "words": []
        }
        if segment.words:
            for word in segment.words:
                seg_data["words"].append({
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                    "probability": float(word.probability)
                })
        result.append(seg_data)

    return result


def diarize_speakers(audio_path: str, num_speakers: int = 2) -> List[Dict]:
    """
    说话人分离

    Args:
        audio_path: 音频文件路径
        num_speakers: 说话人数量（通常是2: agent和customer）

    Returns:
        带说话人标注的segment列表
    """
    # 简化版本：尝试使用 whisperx（如果可用），否则使用简单启发式
    try:
        import whisperx
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # 1. 加载 whisperx 模型进行 ASR
        model = whisperx.load_model("small", device, compute_type="int8")
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=4, language="id")

        # 2. 对齐
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

        # 3. 说话人分离
        diarize_model = whisperx.DiarizationPipeline(use_auth_token="", device=device)
        diarize_segments = diarize_model(audio, num_speakers=num_speakers)

        # 4. 分配说话人
        result = whisperx.assign_word_speakers(diarize_segments, result)

        # 格式化输出
        segments = []
        for seg in result["segments"]:
            speaker = seg.get("speaker", "SPEAKER_00")
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "speaker": speaker
            })
        return segments

    except Exception:
        # 如果 whisperx 不可用或出错，使用简化的启发式
        # 先获取转写结果，用一些启发式分配说话人
        transcript = transcribe_audio(audio_path)
        segments = []

        # 启发式1：基于内容启发式
        agent_keywords = ["halo", "bu", "pak", "nama", "kartu", "kredit", "tagihan", "bayar", "ekstra", "aplikasi"]
        customer_keywords = ["ya", "tidak", "ngga", "tidak tahu", "saya", "kapan", "sudah", "besok", "nanti"]

        for i, seg in enumerate(transcript):
            text = seg["text"].lower()

            # 简单启发式：检查内容匹配
            agent_score = sum(1 for kw in agent_keywords if kw in text)
            customer_score = sum(1 for kw in customer_keywords if kw in text)

            if agent_score > customer_score:
                speaker = "AGENT"
            elif customer_score > agent_score:
                speaker = "CUSTOMER"
            else:
                # 交替
                speaker = "AGENT" if i % 2 == 0 else "CUSTOMER"

            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "speaker": speaker
            })

        return segments


def merge_transcript_and_diarization(transcript: List[Dict], diarization: List[Dict]) -> List[Dict]:
    """
    合并转写结果和说话人分离结果

    Returns:
        [{"start": 0.0, "end": 2.0, "speaker": "agent", "text": "..."}]
    """
    merged = []

    # 如果两个列表长度一样，直接合并
    if len(transcript) == len(diarization):
        for t, d in zip(transcript, diarization):
            merged.append({
                "start": t["start"],
                "end": t["end"],
                "speaker": d.get("speaker", "UNKNOWN"),
                "text": t.get("text", ""),
                "words": t.get("words", [])
            })
    else:
        # 使用时间重叠匹配
        for t in transcript:
            t_start = t["start"]
            t_end = t["end"]

            # 找重叠最大的说话人段
            best_speaker = "UNKNOWN"
            max_overlap = 0

            for d in diarization:
                d_start = d["start"]
                d_end = d["end"]

                # 计算重叠
                overlap_start = max(t_start, d_start)
                overlap_end = min(t_end, d_end)
                overlap = max(0, overlap_end - overlap_start)

                if overlap > max_overlap:
                    max_overlap = overlap
                    best_speaker = d.get("speaker", "UNKNOWN")

            merged.append({
                "start": t_start,
                "end": t_end,
                "speaker": best_speaker,
                "text": t.get("text", ""),
                "words": t.get("words", [])
            })

    return merged


def process_directory(input_dir: str, output_dir: str, model_size: str = "small", use_diarization: bool = False):
    """
    批量处理目录下的所有音频文件
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    audio_files = list(input_path.glob("*.wav")) + list(input_path.glob("*.mp3"))
    audio_files = sorted(audio_files)

    print(f"Found {len(audio_files)} audio files")

    for idx, audio_file in enumerate(audio_files, 1):
        case_id = audio_file.stem
        print(f"[{idx}/{len(audio_files)}] Processing {case_id}...")

        # 转写
        transcript = transcribe_audio(str(audio_file), model_size=model_size)

        result = {
            "case_id": case_id,
            "file_name": audio_file.name,
            "transcript": transcript,
            "full_text": " ".join([seg["text"] for seg in transcript])
        }

        # 可选：说话人分离
        if use_diarization:
            print("  Running speaker diarization...")
            diarization = diarize_speakers(str(audio_file))
            merged = merge_transcript_and_diarization(transcript, diarization)
            result["transcript_with_speakers"] = merged

        # 保存
        output_file = output_path / f"{case_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  Saved to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transcribe audio files")
    parser.add_argument("--input", default="data/chat-sample", help="Input directory")
    parser.add_argument("--output", default="data/processed/transcripts", help="Output directory")
    parser.add_argument("--model", default="small", help="Whisper model size (tiny, small, medium, large-v3)")
    parser.add_argument("--with-diarization", action="store_true", help="Enable speaker diarization")
    args = parser.parse_args()

    print("=" * 60)
    print("Indonesian Speech Transcription")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Speaker diarization: {args.with_diarization}")
    print()

    process_directory(args.input, args.output, model_size=args.model, use_diarization=args.with_diarization)

    print()
    print("=" * 60)
    print("All done!")
    print("=" * 60)
