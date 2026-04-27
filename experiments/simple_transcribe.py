"""
Simple Indonesian speech transcription test
Avoid encoding issues
"""
import sys
import json
from pathlib import Path

print("=" * 60)
print("Indonesian Speech Transcription Test")
print("=" * 60)

# Check audio files
data_dir = Path("data/chat-sample")
audio_files = sorted(list(data_dir.glob("*.mp3")))

print("\nFound", len(audio_files), "audio files:")
for f in audio_files:
    size_mb = f.stat().st_size / 1024 / 1024
    print(f"  {f.name}: {size_mb:.2f} MB")

if not audio_files:
    print("No audio files found!")
    sys.exit(1)

# Import faster-whisper
print("\n" + "=" * 60)
print("Loading model...")
print("=" * 60)

from faster_whisper import WhisperModel

# Try small model first
model_size = "small"
print("Loading model:", model_size, "(this will download on first run)...")
model = WhisperModel(model_size, device="cpu", compute_type="int8")
print("Model loaded successfully")

# Transcribe first file
audio_file = audio_files[0]
print("\nTranscribing:", audio_file.name)

segments, info = model.transcribe(
    str(audio_file),
    language="id",
    beam_size=5,
    word_timestamps=True
)

print("Detected language:", info.language, "(prob:", info.language_probability, ")")

# Print results
print("\n" + "=" * 60)
print("Transcription Result:")
print("=" * 60)

# Need to re-iterate
segments, _ = model.transcribe(
    str(audio_file),
    language="id",
    beam_size=5,
    word_timestamps=True
)

full_text = []
segments_list = []

for segment in segments:
    print(f"\n[{segment.start:.2f}s -> {segment.end:.2f}s]")
    print(" ", segment.text)
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
print("Full Text:")
print("=" * 60)
print(" ".join(full_text))

# Save result
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

print("\nResult saved to:", output_file)

# Transcribe all files
print("\n" + "=" * 60)
print("Transcribing all files...")
print("=" * 60)

for audio_file in audio_files:
    print(f"\nProcessing: {audio_file.name}...")

    segments, info = model.transcribe(
        str(audio_file),
        language="id",
        beam_size=5,
        word_timestamps=True
    )

    # Re-iterate
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

    print("  Saved to:", output_file)

print("\n" + "=" * 60)
print("All done!")
print("=" * 60)
