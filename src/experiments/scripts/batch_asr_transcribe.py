#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量ASR转写脚本，处理新增的印尼语催收语音
输出格式与现有转写文件保持一致
"""
import os
import json
import torch
import whisper
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

# 配置
INPUT_DIR = Path("data/chat-sample/")
OUTPUT_DIR = Path("data/processed/transcripts/")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_SIZE = "small"  # 对于印尼语，small模型足够用，速度快
LANGUAGE = "id"  # 印尼语


class ASRTranscriber:
    def __init__(self, model_size: str = "small", language: str = "id"):
        # MPS设备不支持float64，Whisper在MPS上运行会出错，所以强制使用CPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"使用设备: {self.device} (已禁用MPS以避免float64兼容性问题)")

        # 加载Whisper模型
        self.model = whisper.load_model(model_size, device=self.device)
        self.language = language

        # 不使用说话人分离模型，采用简单的交替分配方式（催收场景通常坐席先说话）
        self.speaker_diarization = None

    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        转写单个音频文件
        返回格式与现有转写文件一致
        """
        # 使用Whisper转写
        result = self.model.transcribe(
            audio_path,
            language=self.language,
            word_timestamps=True,
            verbose=False
        )

        # 构造基础转写结果
        segments = []
        full_text = ""
        for seg in result["segments"]:
            segment = {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "words": []
            }
            for word in seg["words"]:
                segment["words"].append({
                    "word": word["word"],
                    "start": word["start"],
                    "end": word["end"],
                    "probability": word["probability"]
                })
            segments.append(segment)
            full_text += seg["text"]

        # 构造带说话人的转写结果
        # 如果有说话人分离模型，使用它；否则使用简单的交替分配（坐席先说话）
        transcript_with_speakers = []
        if self.speaker_diarization:
            # 使用pyannote进行说话人分离
            diarization = self.speaker_diarization(audio_path)
            # TODO: 实现说话人转写结果合并
            pass
        else:
            # 简单交替分配：第一个说话的是AGENT，然后交替
            current_speaker = "AGENT"
            for seg in segments:
                seg_with_speaker = seg.copy()
                seg_with_speaker["speaker"] = current_speaker
                transcript_with_speakers.append(seg_with_speaker)
                # 切换说话人
                current_speaker = "CUSTOMER" if current_speaker == "AGENT" else "AGENT"

        # 构造最终结果
        case_id = Path(audio_path).stem
        return {
            "case_id": case_id,
            "file_name": Path(audio_path).name,
            "transcript": segments,
            "transcript_with_speakers": transcript_with_speakers,
            "full_text": full_text.strip()
        }

    def batch_transcribe(self, force: bool = False) -> List[str]:
        """
        批量转写所有未处理的音频文件
        force: 是否强制覆盖已有的转写结果
        """
        # 获取所有mp3文件
        audio_files = list(INPUT_DIR.glob("*.mp3"))
        print(f"找到 {len(audio_files)} 个音频文件")

        # 过滤掉已经转写过的文件
        if not force:
            existing_transcripts = set([f.stem for f in OUTPUT_DIR.glob("*.json")])
            audio_files = [f for f in audio_files if f.stem not in existing_transcripts]
            print(f"需要转写的新文件: {len(audio_files)} 个")

        # 批量转写
        success_files = []
        for audio_path in tqdm(audio_files, desc="转写进度"):
            try:
                result = self.transcribe_audio(str(audio_path))
                output_path = OUTPUT_DIR / f"{result['case_id']}.json"
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                success_files.append(str(audio_path))
            except Exception as e:
                print(f"转写失败 {audio_path}: {e}")
                continue

        print(f"成功转写 {len(success_files)} 个文件")
        return success_files


def main():
    transcriber = ASRTranscriber(model_size=MODEL_SIZE, language=LANGUAGE)
    success_files = transcriber.batch_transcribe()
    print(f"转写完成，输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
