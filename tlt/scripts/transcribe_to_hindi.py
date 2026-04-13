import sys
import os
import time
from pathlib import Path
import anthropic
from faster_whisper import WhisperModel

AUDIO_DIR = Path(__file__).parent.parent / "audios"
TRANSCRIPT_DIR = Path(__file__).parent.parent / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def transcribe_english(audio_path: Path) -> tuple[str, list]:
    log("Loading Whisper medium model...")
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    log("Model loaded.")

    log(f"Transcribing: {audio_path.name}")
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        task="transcribe",
    )

    log(f"Detected language: {info.language} ({info.language_probability:.0%})")

    all_segments = []
    full_text = ""
    for segment in segments:
        text = segment.text.strip()
        all_segments.append((segment.start, segment.end, text))
        full_text += text + " "
        log(f"  [{segment.start:.1f}s → {segment.end:.1f}s] {text}")

    log(f"English transcription done. {len(all_segments)} segments.")
    return full_text.strip(), all_segments

def translate_to_hindi(english_text: str) -> str:
    log("Translating to Hindi via Claude...")
    client = anthropic.Anthropic()

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        messages=[
            {
                "role": "user",
                "content": (
                    "Translate the following English text to Hindi (Devanagari script). "
                    "Keep the translation natural and fluent. "
                    "Preserve paragraph breaks if any. "
                    "Output only the Hindi translation, nothing else.\n\n"
                    f"{english_text}"
                )
            }
        ]
    )

    hindi_text = message.content[0].text.strip()
    log("Translation done.")
    return hindi_text

def run(audio_path: Path):
    english_text, segments = transcribe_english(audio_path)
    hindi_text = translate_to_hindi(english_text)

    out_path = TRANSCRIPT_DIR / (audio_path.stem + "_hindi.md")
    with open(out_path, "w") as f:
        f.write(f"# Transcript (Hindi) — {audio_path.name}\n\n")
        f.write("---\n\n")
        f.write("## English Original\n\n")
        f.write(english_text + "\n\n")
        f.write("---\n\n")
        f.write("## Hindi Translation\n\n")
        f.write(hindi_text + "\n")

    log(f"Saved: {out_path}")
    print(f"\n{'='*60}")
    print("HINDI TRANSCRIPT:")
    print('='*60)
    print(hindi_text)
    return out_path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        audio_path = Path(sys.argv[1])
    else:
        files = list(AUDIO_DIR.glob("*.m4a")) + list(AUDIO_DIR.glob("*.mp3")) + list(AUDIO_DIR.glob("*.wav"))
        if not files:
            print("No audio files found in tlt/audios/")
            sys.exit(1)
        audio_path = files[0]

    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        sys.exit(1)

    run(audio_path)
