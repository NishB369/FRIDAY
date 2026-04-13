import sys
import os
import time
from pathlib import Path
from faster_whisper import WhisperModel

AUDIO_DIR = Path(__file__).parent.parent / "audios"
TRANSCRIPT_DIR = Path(__file__).parent.parent / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def transcribe(audio_path: Path):
    log(f"Loading medium model...")
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    log(f"Model loaded.")

    log(f"Starting transcription: {audio_path.name}")
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        task="transcribe",
    )

    log(f"Detected language: {info.language} (confidence: {info.language_probability:.0%})")
    log(f"Processing segments...")

    all_segments = []
    full_text = ""
    segment_count = 0

    for segment in segments:
        segment_count += 1
        text = segment.text.strip()
        all_segments.append((segment.start, segment.end, text))
        full_text += text + " "
        log(f"  [{segment.start:.1f}s -> {segment.end:.1f}s] {text}")

    log(f"Done. {segment_count} segments transcribed.")

    # Save transcript
    out_path = TRANSCRIPT_DIR / (audio_path.stem + ".md")
    with open(out_path, "w") as f:
        f.write(f"# Transcript — {audio_path.name}\n\n")
        f.write(f"**Language:** {info.language} ({info.language_probability:.0%} confidence)  \n")
        f.write(f"**Model:** faster-whisper medium  \n\n")
        f.write("---\n\n")
        f.write("## Timestamped Segments\n\n")
        f.write("| Time | Text |\n|------|------|\n")
        for start, end, text in all_segments:
            f.write(f"| {start:.1f}s → {end:.1f}s | {text} |\n")
        f.write("\n---\n\n")
        f.write("## Full Text\n\n")
        f.write(full_text.strip() + "\n")

    log(f"Transcript saved: {out_path}")
    return out_path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
    else:
        # default: first audio in audios dir
        files = list(AUDIO_DIR.glob("*.m4a")) + list(AUDIO_DIR.glob("*.mp3")) + list(AUDIO_DIR.glob("*.wav"))
        if not files:
            print("No audio files found in tlt/audios/")
            sys.exit(1)
        audio_path = files[0]

    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        sys.exit(1)

    transcribe(audio_path)
