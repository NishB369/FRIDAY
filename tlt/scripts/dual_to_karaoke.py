"""
dual_to_karaoke.py
------------------
Convert a dual_transcribe.py output JSON into Remotion karaoke props
and print the render + mux commands.

Sarvam's transcript already mixes Devanagari + English naturally (e.g.
"हेलो एवरीवन एंड वेलकम बैक टू माय YouTube चैनल"), so we keep it as-is —
no extra Hinglish transliteration step needed.

Usage:
  python tlt/scripts/dual_to_karaoke.py --slug sultanas_dream_0-29s
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TRANSCRIPT_DIR = ROOT / "tlt" / "transcripts"
AUDIO_DIR = ROOT / "tlt" / "audios"
PROPS_DIR = ROOT / "remotion" / "props"
OUT_DIR = ROOT / "remotion" / "outputs"


def transliterate_hinglish(words: list[dict]) -> list[dict]:
    """Send Devanagari words to Claude Haiku, get romanized Hinglish back.
    English tokens (already roman) pass through unchanged. Returns same list
    shape with `word` replaced by Hinglish.
    """
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic not installed (.venv/bin/pip install anthropic)")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=key)

    payload = "\n".join(f"{i}|{w['word']}" for i, w in enumerate(words))
    print(f"transliterating {len(words)} tokens via Claude Haiku...")
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=(
            "Transliterate Devanagari Hindi tokens to Hinglish (romanized Hindi, "
            "WhatsApp-style). Rules:\n"
            "1. Preserve exact spoken sound.\n"
            "2. English tokens already in Roman script stay unchanged (YouTube, hello, channel).\n"
            "3. One output line per input line, same index.\n"
            "4. Format strictly: INDEX|hinglish\n"
            "5. No explanations, no extra lines, no commentary."
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
    print(f"transliterated {len(out)}/{len(words)}")
    return [{**w, "word": out.get(i, w["word"])} for i, w in enumerate(words)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="Stem of the dual JSON, e.g. sultanas_dream_0-29s")
    ap.add_argument("--delay-ms", type=int, default=200, help="Shift all word timings later by N ms so highlight lands after the spoken word")
    ap.add_argument("--hinglish", action="store_true", help="Transliterate Devanagari → Hinglish via Claude")
    args = ap.parse_args()
    delay = args.delay_ms / 1000.0

    src = TRANSCRIPT_DIR / f"{args.slug}_dual.json"
    if not src.exists():
        sys.exit(f"missing {src}")
    audio = AUDIO_DIR / f"{args.slug}.mp3"
    if not audio.exists():
        sys.exit(f"missing audio {audio}")

    data = json.loads(src.read_text(encoding="utf-8"))
    words_in = data.get("words") or []
    if not words_in:
        sys.exit("no aligned words in dual JSON")

    # Shift to zero so karaoke starts at frame 0 even if first word starts late.
    if args.hinglish:
        words_in = transliterate_hinglish(words_in)

    off = words_in[0].get("start", 0.0) - delay
    words_out = [
        {
            "word": w["word"],
            "startSec": round(w["start"] - off, 3),
            "endSec": round(w["end"] - off, 3),
        }
        for w in words_in
    ]

    props = {
        "words": words_out,
        "totalDurationSec": round(words_out[-1]["endSec"], 3),
        "fps": 30,
        "wordsPerScreen": 18,
        "bgColor": "#F5F4F0",
        "textActive": "#1A1A1A",
        "textPast": "#AAAAAA",
        "textFuture": "#CCCCCC",
        "fontSize": 52,
        "fontFamily": "Georgia, 'Times New Roman', serif",
    }

    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    props_path = PROPS_DIR / f"{args.slug}.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"props → {props_path}")
    print(f"words: {len(words_out)}  duration: {props['totalDurationSec']}s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = int(props["totalDurationSec"] * props["fps"])
    silent = OUT_DIR / f"{args.slug}_silent.mp4"
    final = OUT_DIR / f"{args.slug}.mp4"
    print(f"""
# Render karaoke (silent):
cd {ROOT}/remotion && npx remotion render TranscriptKaraoke {silent.relative_to(ROOT/'remotion')} \\
  --props=props/{args.slug}.json --frames=0-{frames - 1}

# Mux audio:
ffmpeg -y -i {silent} -i {audio} -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest {final}
""")


if __name__ == "__main__":
    main()
