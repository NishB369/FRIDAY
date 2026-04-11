"""
build_karaoke_props.py
----------------------
Converts a TLT video transcript (Devanagari chunks with timestamps) into
a word-level props JSON ready for the Remotion TranscriptKaraoke composition.

Pipeline:
  1. Load json-res/<slug>.json
  2. Filter out [music] / [संगीत] noise chunks
  3. Convert Devanagari → Hinglish via Claude API (batch, one call per video)
  4. Split each chunk into words, distribute duration evenly per word
  5. Shift all timings so first word starts at t=0
  6. Write props JSON to remotion/props/<slug>.json

Usage:
  python tlt/scripts/build_karaoke_props.py --slug a_feast_on_the_train_...
  python tlt/scripts/build_karaoke_props.py --slug a_feast_on_the_train_... --no-convert
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent  # /FRIDAY
JSON_DIR = ROOT / "tlt" / "json-res"
PROPS_DIR = ROOT / "remotion" / "props"

NOISE_PATTERNS = re.compile(r"^\s*[\[\(].*?[\]\)]\s*$")  # [संगीत], [Music], (applause) etc.


def load_chunks(slug: str) -> tuple[list[dict], float]:
    path = JSON_DIR / f"{slug}.json"
    if not path.exists():
        matches = list(JSON_DIR.glob(f"{slug}*.json"))
        if not matches:
            sys.exit(f"No JSON found for slug: {slug}")
        path = matches[0]
        print(f"Matched: {path.name}")

    with open(path) as f:
        data = json.load(f)

    chunks = data["transcript"]["chunks"]
    duration = data.get("duration_seconds", 0)
    return chunks, duration


def filter_noise(chunks: list[dict]) -> list[dict]:
    return [c for c in chunks if not NOISE_PATTERNS.match(c["text"])]


def convert_to_hinglish(chunks: list[dict]) -> list[dict]:
    """Batch convert all Devanagari chunks to Hinglish via Claude Haiku. One API call."""
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic not installed. Run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    input_lines = "\n".join(f"{i}|{c['text']}" for i, c in enumerate(chunks))

    print(f"Converting {len(chunks)} chunks to Hinglish via Claude Haiku...")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=(
            "You are a Hinglish transliterator. Convert Devanagari Hindi text to Hinglish "
            "(romanized Hindi as spoken — like WhatsApp Hindi). "
            "Rules:\n"
            "1. Preserve exact meaning and spoken rhythm.\n"
            "2. English words already in the text stay as English.\n"
            "3. Output ONLY lines in format: INDEX|hinglish text\n"
            "4. One line per input. No explanations. No extra text.\n"
            "5. Do not translate — only transliterate/romanize."
        ),
        messages=[{"role": "user", "content": f"Convert these lines:\n\n{input_lines}"}],
    )

    converted = {}
    for line in message.content[0].text.strip().splitlines():
        if "|" in line:
            idx_str, text = line.split("|", 1)
            try:
                converted[int(idx_str.strip())] = text.strip()
            except ValueError:
                pass

    print(f"Converted {len(converted)}/{len(chunks)} chunks")
    return [
        {**chunk, "text": converted.get(i, chunk["text"])}
        for i, chunk in enumerate(chunks)
    ]


def chunks_to_words(chunks: list[dict]) -> list[dict]:
    """Split each chunk into words, distributing duration evenly across words."""
    words = []
    for chunk in chunks:
        text = chunk["text"].strip()
        start = chunk["offset"]
        duration = chunk["duration"]
        raw_words = text.split()
        if not raw_words:
            continue
        per_word = duration / len(raw_words)
        for i, w in enumerate(raw_words):
            words.append({
                "word": w,
                "startSec": round(start + i * per_word, 3),
                "endSec": round(start + (i + 1) * per_word, 3),
            })
    return words


def shift_to_zero(words: list[dict]) -> list[dict]:
    """Shift all timings so the first word starts at t=0."""
    if not words:
        return words
    offset = words[0]["startSec"]
    if offset == 0:
        return words
    return [
        {"word": w["word"], "startSec": round(w["startSec"] - offset, 3), "endSec": round(w["endSec"] - offset, 3)}
        for w in words
    ]


def build_props(slug: str, convert: bool = True) -> tuple[dict, str]:
    chunks, duration = load_chunks(slug)
    print(f"Loaded {len(chunks)} chunks, duration={duration}s")

    chunks = filter_noise(chunks)
    print(f"After noise filter: {len(chunks)} chunks")

    if convert:
        chunks = convert_to_hinglish(chunks)

    words = chunks_to_words(chunks)
    words = shift_to_zero(words)
    net_duration = round(words[-1]["endSec"], 3) if words else duration
    print(f"Generated {len(words)} word timings, net duration={net_duration}s")

    props = {
        "words": words,
        "totalDurationSec": net_duration,
        "fps": 30,
        "wordsPerScreen": 18,
        "bgColor": "#F5F4F0",
        "textActive": "#1A1A1A",
        "textPast": "#AAAAAA",
        "textFuture": "#CCCCCC",
        "fontSize": 52,
        "fontFamily": "Georgia, 'Times New Roman', serif",
    }

    return props, slug


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="Video slug (filename without .json)")
    parser.add_argument("--no-convert", action="store_true", help="Skip Hinglish conversion, keep Devanagari")
    args = parser.parse_args()

    props, slug = build_props(args.slug, convert=not args.no_convert)

    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROPS_DIR / f"{slug}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    net_frames = int(props["totalDurationSec"] * props["fps"])
    print(f"\nProps written → {out_path}")
    print(f"Total words : {len(props['words'])}")
    print(f"Net duration: {props['totalDurationSec']}s ({net_frames} frames @ {props['fps']}fps)")
    print(f"\nRender command:")
    print(f"  cd remotion && npx remotion render TranscriptKaraoke outputs/{slug}.mp4 \\")
    print(f"    --props props/{slug}.json \\")
    print(f"    --frames 0-{net_frames - 1}")


if __name__ == "__main__":
    main()
