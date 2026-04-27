"""
Quick test with tiny model (fast download)
"""
import sys
import json
from pathlib import Path

print("=" * 60)
print("Indonesian Speech Transcription - TINY MODEL")
print("=" * 60)

data_dir = Path("data/chat-sample")
audio_files = sorted(list(data_dir.glob("*.mp3")))
print("\nFound", len(audio_files), "audio files")

from faster_whisper import WhisperModel

model_size = "tiny"
print("Loading TINY model (very fast download)...")
model = WhisperModel(model_size, device="cpu", compute_type="int8")
print("Model loaded")

audio_file = audio_files[0]
print("\nTranscribing:", audio_file.name)

segments, info = model.transcribe(str(audio_file), language="id", beam_size=5)
print("Detected language:", info.language)

# Re-iterate to get content
segments, _ = model.transcribe(str(audio_file), language="id", beam_size=5)

full_text = []
for segment in segments:
    print(f"\n[{segment.start:.2f}s -> {segment.end:.2f}s]")
    print(" ", segment.text)
    full_text.append(segment.text)

print("\n" + "=" * 60)
print("Full Text:")
print(" ".join(full_text))

# Save
output_dir = Path("data/processed/transcripts")
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / f"{audio_file.stem}_tiny.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump({"full_text": " ".join(full_text)}, f, ensure_ascii=False, indent=2)

print("\nSaved to:", output_file)
print("\nDone!")
