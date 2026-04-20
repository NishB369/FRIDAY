"""
sarvam_transcribe.py
--------------------
Trim a clip from a source audio and transcribe it via Sarvam AI.

Sarvam's playground "Saaras + Transcribe" maps to the Saarika transcribe API
in code (Saaras's actual API translates to English). For Hindi/Indic
transcription with code-switching preserved, we use saarika:v2.

Usage:
  python sarvam_transcribe.py --slug sultanas_dream \\
      --src "tlt/audios/Sultana's Dream ... in Hindi.mp3" \\
      --start 0 --duration 30
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
AUDIO_DIR = ROOT / "tlt" / "audios"
TRANSCRIPT_DIR = ROOT / "tlt" / "transcripts"

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def trim_audio(src: Path, start: int, duration: int, slug: str) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIO_DIR / f"{slug}_{start}-{start + duration}s.mp3"
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-t", str(duration), "-i", str(src),
        "-c:a", "libmp3lame", "-b:a", "128k", str(out),
    ]
    log("trim: " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-500:])
    log(f"trimmed → {out} ({out.stat().st_size / 1024:.1f} KB)")
    return out


def call_sarvam(audio: Path, model: str, language: str, mode: str | None) -> dict:
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        sys.exit("SARVAM_API_KEY not set")
    log(f"sarvam: model={model} mode={mode} language={language}")
    data = {"model": model, "language_code": language, "with_timestamps": "true"}
    if mode and model.startswith("saaras"):
        data["mode"] = mode
    with open(audio, "rb") as f:
        r = requests.post(
            SARVAM_URL,
            headers={"api-subscription-key": key},
            files={"file": (audio.name, f, "audio/mpeg")},
            data=data,
            timeout=120,
        )
    if r.status_code != 200:
        sys.exit(f"sarvam HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--src", required=True, help="Source audio path")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--model", default="saaras:v3")
    ap.add_argument("--mode", default="transcribe", help="saaras only: transcribe|translate|verbatim|translit|codemix")
    ap.add_argument("--language", default="hi-IN")
    args = ap.parse_args()

    clip = trim_audio(Path(args.src).expanduser(), args.start, args.duration, args.slug)
    data = call_sarvam(clip, args.model, args.language, args.mode)
    data["_audio_clip"] = str(clip)
    data["_model"] = args.model
    data["_language"] = args.language

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = TRANSCRIPT_DIR / f"{clip.stem}_sarvam.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log(f"saved → {out}")
    print("\n--- TRANSCRIPT ---")
    print(data.get("transcript", ""))


if __name__ == "__main__":
    main()
