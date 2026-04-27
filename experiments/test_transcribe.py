"""
快速测试语音转写
"""
import sys
import json
from pathlib import Path

print("=" * 60)
print("印尼语语音转写测试")
print("=" * 60)

# 1. 检查音频文件
data_dir = Path("data/chat-sample")
audio_files = sorted(list(data_dir.glob("*.mp3")))

print(f"\n找到 {len(audio_files)} 个音频文件:")
for f in audio_files:
    size_mb = f.stat().st_size / 1024 / 1024
    print(f"  {f.name}: {size_mb:.2f} MB")

if not audio_files:
    print("没有找到音频文件!")
    sys.exit(1)

# 2. 尝试导入faster-whisper
print("\n" + "=" * 60)
print("检查依赖...")
print("=" * 60)

try:
    from faster_whisper import WhisperModel
    print("✓ faster-whisper 已安装")
except ImportError:
    print("✗ faster-whisper 未安装，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "faster-whisper"])
    from faster_whisper import WhisperModel
    print("✓ faster-whisper 安装成功")

# 3. 转写第一个文件
print("\n" + "=" * 60)
print("开始转写...")
print("=" * 60)

# 先用small模型快速测试，如果效果好再用medium/large
model_size = "small"
print(f"\n加载模型: {model_size} (这会在第一次运行时下载模型)...")

try:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
except Exception as e:
    print(f"模型加载失败: {e}")
    print("\n尝试使用tiny模型...")
    model_size = "tiny"
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

print(f"✓ 模型 {model_size} 加载成功")

# 转写第一个文件
audio_file = audio_files[0]
print(f"\n转写文件: {audio_file.name}")

segments, info = model.transcribe(
    str(audio_file),
    language="id",  # 指定印尼语
    beam_size=5,
    word_timestamps=True
)

print(f"\n检测语言: {info.language} (概率: {info.language_probability:.2f})")

# 打印结果
print("\n" + "=" * 60)
print("转写结果:")
print("=" * 60)

full_text = []
segments_list = []

# 需要重新迭代获取内容
segments, _ = model.transcribe(
    str(audio_file),
    language="id",
    beam_size=5,
    word_timestamps=True
)

for segment in segments:
    print(f"\n[{segment.start:.2f}s -> {segment.end:.2f}s]")
    print(f"  {segment.text}")
    full_text.append(segment.text)

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
    segments_list.append(seg_data)

print("\n" + "=" * 60)
print("完整文本:")
print("=" * 60)
print(" ".join(full_text))

# 保存结果
output_dir = Path("data/processed/transcripts")
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / f"{audio_file.stem}.json"

result = {
    "file_name": audio_file.name,
    "detected_language": info.language,
    "language_probability": float(info.language_probability),
    "segments": segments_list,
    "full_text": " ".join(full_text)
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到: {output_file}")

# 询问是否批量转写
print("\n" + "=" * 60)
response = input("是否批量转写所有文件? (y/n): ").strip().lower()

if response == 'y':
    print("\n开始批量转写...")

    for audio_file in audio_files:
        print(f"\n处理: {audio_file.name}...")

        segments, info = model.transcribe(
            str(audio_file),
            language="id",
            beam_size=5,
            word_timestamps=True
        )

        # 重新获取
        segments, _ = model.transcribe(
            str(audio_file),
            language="id",
            beam_size=5,
            word_timestamps=True
        )

        segments_list = []
        full_text = []
        for segment in segments:
            segments_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": []
            })
            full_text.append(segment.text)

        output_file = output_dir / f"{audio_file.stem}.json"
        result = {
            "file_name": audio_file.name,
            "detected_language": info.language,
            "language_probability": float(info.language_probability),
            "segments": segments_list,
            "full_text": " ".join(full_text)
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 保存到: {output_file}")

    print("\n全部完成!")
else:
    print("跳过批量转写")

print("\nDone!")
