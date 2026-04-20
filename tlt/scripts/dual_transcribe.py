"""
dual_transcribe.py
------------------
Combine two STT providers to get both clean text and word-level timestamps:
  1. Sarvam (saaras:v3, mode=transcribe) — clean code-switched Hindi text
  2. Groq Whisper (whisper-large-v3) — word-level start/end timestamps

Then align Sarvam's tokens onto the Groq timeline using proportional mapping
(each Sarvam word i in [0..N) gets the timestamp of Groq word at index round(i*M/N)
where M is Groq's word count). Output: karaoke-ready word list with Sarvam text.

Usage:
  python dual_transcribe.py --slug sultanas_dream \\
      --src "tlt/audios/Sultana's Dream ... in Hindi.mp3" \\
      --start 0 --duration 29
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from groq import Groq

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


def call_sarvam(audio: Path) -> dict:
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        sys.exit("SARVAM_API_KEY not set")
    log("sarvam: model=saaras:v3 mode=transcribe")
    with open(audio, "rb") as f:
        r = requests.post(
            SARVAM_URL,
            headers={"api-subscription-key": key},
            files={"file": (audio.name, f, "audio/mpeg")},
            data={"model": "saaras:v3", "mode": "transcribe", "language_code": "hi-IN"},
            timeout=120,
        )
    if r.status_code != 200:
        sys.exit(f"sarvam HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def call_groq(audio: Path) -> dict:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY not set")
    client = Groq(api_key=key)
    log("groq: model=whisper-large-v3")
    with open(audio, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=(audio.name, f.read()),
            model="whisper-large-v3",
            language="hi",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )
    return resp.model_dump() if hasattr(resp, "model_dump") else json.loads(resp.model_dump_json())


def align(sarvam_text: str, groq_words: list[dict], groq_segments: list[dict], clip_duration: float) -> list[dict]:
    """Segment-anchored alignment using char-ratio token distribution.

    Each Groq segment is a time anchor. Sarvam tokens are sliced consecutively
    into chunks proportional to each segment's character share, then evenly
    distributed within that segment's [start, end] window. Works even when
    Groq returned English (translation mode) — segment timing is what matters.
    """
    tokens = [t for t in re.split(r"\s+", sarvam_text.strip()) if t]
    if not tokens:
        return []

    if not groq_segments:
        per = clip_duration / len(tokens)
        return [{"word": t, "start": round(i * per, 3), "end": round((i + 1) * per, 3)} for i, t in enumerate(tokens)]

    n = len(tokens)
    seg_chars = [max(len((s.get("text") or "").strip()), 1) for s in groq_segments]
    total = sum(seg_chars)
    counts = [int(round(c * n / total)) for c in seg_chars]
    drift = n - sum(counts)
    i = 0
    while drift != 0:
        idx = i % len(counts)
        if drift > 0:
            counts[idx] += 1; drift -= 1
        elif counts[idx] > 0:
            counts[idx] -= 1; drift += 1
        i += 1

    out, cursor = [], 0
    for seg, take in zip(groq_segments, counts):
        if take <= 0:
            continue
        slice_toks = tokens[cursor : cursor + take]
        cursor += take
        s_start = float(seg.get("start") or 0.0)
        s_end = float(seg.get("end") or s_start)
        span = max(s_end - s_start, 0.05)
        per_word = span / len(slice_toks)
        for j, tok in enumerate(slice_toks):
            out.append({
                "word": tok,
                "start": round(s_start + j * per_word, 3),
                "end": round(s_start + (j + 1) * per_word, 3),
            })

    if cursor < n:
        last_end = out[-1]["end"] if out else 0.0
        leftover = tokens[cursor:]
        per = max((clip_duration - last_end) / len(leftover), 0.1)
        for j, tok in enumerate(leftover):
            out.append({
                "word": tok,
                "start": round(last_end + j * per, 3),
                "end": round(last_end + (j + 1) * per, 3),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--duration", type=int, default=29)
    args = ap.parse_args()

    clip = trim_audio(Path(args.src).expanduser(), args.start, args.duration, args.slug)

    sarvam = call_sarvam(clip)
    groq = call_groq(clip)

    sarvam_text = (sarvam.get("transcript") or "").strip()
    groq_words = groq.get("words") or []
    groq_segments = groq.get("segments") or []
    duration = float(groq.get("duration") or args.duration)

    aligned = align(sarvam_text, groq_words, groq_segments, duration)

    out_data = {
        "transcript": sarvam_text,
        "duration": duration,
        "words": aligned,
        "_sarvam_raw": sarvam,
        "_groq_raw": groq,
        "_audio_clip": str(clip),
    }

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = TRANSCRIPT_DIR / f"{clip.stem}_dual.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    log(f"saved → {out}")
    log(f"sarvam tokens: {len(aligned)}  |  groq words: {len(groq_words)}  |  duration: {duration:.2f}s")
    print("\n--- ALIGNED (first 10) ---")
    for w in aligned[:10]:
        print(f"  {w['start']:>5.2f}-{w['end']:<5.2f}  {w['word']}")


if __name__ == "__main__":
    main()
