"""
audio_to_karaoke.py
-------------------
End-to-end: raw audio file → Hinglish karaoke Remotion props.

Steps (each logged):
  1. Trim source audio to N seconds (ffmpeg)
  2. Transcribe with Groq Whisper (word-level timestamps, Hindi)
  3. Transliterate Devanagari words → Hinglish (Claude Haiku, batched)
  4. Build Remotion props JSON
  5. Print render + mux commands

Usage:
  python tlt/scripts/audio_to_karaoke.py \\
      --src "/path/to/source.mp3" \\
      --slug sultanas_dream_30s \\
      --seconds 30
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
AUDIO_DIR = ROOT / "tlt" / "audios"
TRANSCRIPT_DIR = ROOT / "tlt" / "transcripts"
PROPS_DIR = ROOT / "remotion" / "props"
OUT_DIR = ROOT / "remotion" / "outputs"


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def step(n: int, title: str):
    print(f"\n{'='*60}\n[STEP {n}] {title}\n{'='*60}", flush=True)


def trim_audio(src: Path, seconds: int, slug: str) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIO_DIR / f"{slug}.mp3"
    log(f"src:  {src}")
    log(f"out:  {out}  ({seconds}s)")
    cmd = ["ffmpeg", "-y", "-i", str(src), "-t", str(seconds), "-c", "copy", str(out)]
    log("cmd:  " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log("stream-copy failed, re-encoding...")
        cmd = ["ffmpeg", "-y", "-i", str(src), "-t", str(seconds), "-c:a", "libmp3lame", "-b:a", "128k", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("ffmpeg failed:\n" + r.stderr[-500:])
    log(f"trimmed → {out.stat().st_size / 1024:.1f} KB")
    return out


def transcribe_groq(audio: Path, language: str = "hi", slug: str | None = None, context_prompt: str = "हिंदी और अंग्रेजी मिक्स") -> list[dict]:
    try:
        from groq import Groq
    except ImportError:
        sys.exit("groq not installed (.venv/bin/pip install groq)")
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY not set")
    client = Groq(api_key=key)
    log(f"uploading {audio.name} to Groq Whisper (whisper-large-v3)...")
    log(f"prompt: {context_prompt[:120]}{'...' if len(context_prompt) > 120 else ''}")
    with open(audio, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=(audio.name, f.read()),
            model="whisper-large-v3",
            language=language,
            prompt=context_prompt,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )
    data = resp.model_dump() if hasattr(resp, "model_dump") else json.loads(resp.model_dump_json())
    words = data.get("words") or []
    log(f"got {len(words)} words; language={data.get('language')}; dur={data.get('duration')}")
    if slug:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = TRANSCRIPT_DIR / f"{slug}_groq.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log(f"raw Groq JSON → {raw_path}")
    for w in words[:8]:
        log(f"  [{w['start']:.2f}-{w['end']:.2f}] {w['word']}")
    return words


def transliterate_hinglish(words: list[dict], proper_nouns: str = "") -> list[dict]:
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic not installed")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=key)

    payload = "\n".join(f"{i}|{w['word']}" for i, w in enumerate(words))
    log(f"transliterating {len(words)} words via Claude Haiku...")
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=(
            "You transliterate Devanagari Hindi tokens to Hinglish (romanized Hindi, "
            "WhatsApp-style). Rules:\n"
            "1. Preserve exact spoken sound.\n"
            "2. English words already spoken in English stay as English (hello, youtube, poem, discuss).\n"
            "3. One output line per input line, same index.\n"
            "4. Format strictly: INDEX|hinglish\n"
            "5. No explanations, no extra lines.\n"
            + (f"6. If a token looks like a mangled version of a known proper noun, use the correct spelling. Known proper nouns: {proper_nouns}\n" if proper_nouns else "")
        ),
        messages=[{"role": "user", "content": f"Convert:\n{payload}"}],
    )
    out = {}
    for line in msg.content[0].text.strip().splitlines():
        if "|" in line:
            i, t = line.split("|", 1)
            try:
                out[int(i.strip())] = t.strip()
            except ValueError:
                pass
    log(f"transliterated {len(out)}/{len(words)}")
    return [
        {"word": out.get(i, w["word"]), "startSec": round(float(w["start"]), 3), "endSec": round(float(w["end"]), 3)}
        for i, w in enumerate(words)
    ]


def shift_to_zero(words: list[dict]) -> list[dict]:
    if not words:
        return words
    off = words[0]["startSec"]
    if off <= 0:
        return words
    return [
        {"word": w["word"], "startSec": round(w["startSec"] - off, 3), "endSec": round(w["endSec"] - off, 3)}
        for w in words
    ]


def build_props(words: list[dict]) -> dict:
    return {
        "words": words,
        "totalDurationSec": round(words[-1]["endSec"], 3) if words else 0,
        "fps": 30,
        "wordsPerScreen": 18,
        "bgColor": "#F5F4F0",
        "textActive": "#1A1A1A",
        "textPast": "#AAAAAA",
        "textFuture": "#CCCCCC",
        "fontSize": 52,
        "fontFamily": "Georgia, 'Times New Roman', serif",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Source audio path")
    ap.add_argument("--slug", required=True, help="Output slug (no extension)")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--language", default="hi")
    ap.add_argument("--prompt", default="हिंदी और अंग्रेजी मिक्स", help="Groq Whisper context prompt")
    ap.add_argument("--proper-nouns", default="", help="Comma-separated proper nouns passed to Claude for spelling fixes")
    ap.add_argument("--no-hinglish", action="store_true", help="Keep Devanagari words")
    args = ap.parse_args()

    step(1, "Trim audio")
    clip = trim_audio(Path(args.src).expanduser(), args.seconds, args.slug)

    step(2, "Transcribe via Groq Whisper")
    words = transcribe_groq(clip, language=args.language, slug=args.slug, context_prompt=args.prompt)
    if not words:
        sys.exit("No words returned from Groq")

    step(3, "Transliterate → Hinglish")
    if args.no_hinglish:
        log("skipped")
        words_out = [{"word": w["word"], "startSec": float(w["start"]), "endSec": float(w["end"])} for w in words]
    else:
        words_out = transliterate_hinglish(words, proper_nouns=args.proper_nouns)

    words_out = shift_to_zero(words_out)

    step(4, "Build Remotion props")
    props = build_props(words_out)
    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    props_path = PROPS_DIR / f"{args.slug}.json"
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)
    log(f"props → {props_path}")
    log(f"words: {len(words_out)}  duration: {props['totalDurationSec']}s")

    step(5, "Render + mux commands")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = int(props["totalDurationSec"] * props["fps"])
    silent = OUT_DIR / f"{args.slug}_silent.mp4"
    final = OUT_DIR / f"{args.slug}.mp4"
    print(f"""
# Render karaoke (silent):
cd {ROOT}/remotion && npx remotion render TranscriptKaraoke {silent.relative_to(ROOT/'remotion')} \\
  --props=props/{args.slug}.json --frames=0-{frames - 1}

# Mux audio:
ffmpeg -y -i {silent} -i {clip} -c:v copy -c:a aac -shortest {final}
""")


if __name__ == "__main__":
    main()
