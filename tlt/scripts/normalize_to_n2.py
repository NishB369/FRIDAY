"""
normalize_to_n2.py
------------------
Convert any upstream transcript (audio-pipeline merged.json OR YT-extractor
JSON) into the unified N2 canonical shape that downstream nodes (summary,
notes, quiz, YT metadata) consume.

N2 shape:
{
  "source": "audio" | "youtube",
  "slug": str,
  "title": str,
  "language": "hi" | "en" | "mixed",
  "duration_seconds": int,
  "transcript": {
    "available": bool,
    "word_count": int,
    "full_text": str,
    "chunks": [{"text": str, "offset": int, "duration": int}, ...]
  },
  "youtube": {video_id, channel, published_at, description, tags, comments}  # optional
}

Usage:
  # audio source (from full_audio_karaoke.py output)
  python tlt/scripts/normalize_to_n2.py \\
      --src tlt/transcripts/new_recording_merged.json \\
      --slug new_recording --title "New Recording" --language hi

  # youtube source (from yt-data-extractor)
  python tlt/scripts/normalize_to_n2.py \\
      --src tlt/raw/transcripts/touch_meena_kandasamy_fhie3346vjY.json \\
      --from-youtube
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
N2_DIR = ROOT / "tlt" / "n2"
CHUNK_SECONDS = 5


def slugify(s: str, max_len: int = 60) -> str:
    out = "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out[:max_len]


def chunk_words(words: list[dict], window: int = CHUNK_SECONDS) -> list[dict]:
    """Group {word, start, end} into ~window-second chunks."""
    if not words:
        return []
    chunks, cur, cur_start = [], [], int(words[0]["start"])
    for w in words:
        if int(w["start"]) >= cur_start + window and cur:
            chunks.append({
                "text": " ".join(cur),
                "offset": cur_start,
                "duration": max(int(w["start"]) - cur_start, 1),
            })
            cur, cur_start = [], int(w["start"])
        cur.append(w["word"])
    if cur:
        last_end = int(words[-1]["end"]) + 1
        chunks.append({
            "text": " ".join(cur),
            "offset": cur_start,
            "duration": max(last_end - cur_start, 1),
        })
    return chunks


def from_audio(src: Path, slug: str, title: str, language: str) -> dict:
    data = json.loads(src.read_text(encoding="utf-8"))
    words = data.get("words", [])
    duration = float(data.get("duration") or (words[-1]["end"] if words else 0))
    full_text = " ".join(w["word"] for w in words)
    return {
        "source": "audio",
        "slug": slug,
        "title": title,
        "language": language,
        "duration_seconds": int(round(duration)),
        "transcript": {
            "available": bool(words),
            "word_count": len(words),
            "full_text": full_text,
            "chunks": chunk_words(words),
        },
    }


def from_youtube(src: Path) -> dict:
    raw = json.loads(src.read_text(encoding="utf-8"))
    t = raw.get("transcript") or {}
    return {
        "source": "youtube",
        "slug": slugify(raw.get("title", raw.get("video_id", "untitled"))),
        "title": raw.get("title", ""),
        "language": raw.get("language", "mixed"),
        "duration_seconds": int(raw.get("duration_seconds") or 0),
        "transcript": {
            "available": bool(t.get("available")),
            "word_count": int(t.get("word_count") or 0),
            "full_text": t.get("full_text", ""),
            "chunks": t.get("chunks", []),
        },
        "youtube": {
            "video_id": raw.get("video_id"),
            "channel": raw.get("channel"),
            "published_at": raw.get("published_at"),
            "description": raw.get("description"),
            "tags": raw.get("tags", []),
            "comments": raw.get("comments", []),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--from-youtube", action="store_true")
    ap.add_argument("--slug")
    ap.add_argument("--title")
    ap.add_argument("--language", default="mixed", choices=["hi", "en", "mixed"])
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    if not src.exists():
        sys.exit(f"missing: {src}")

    if args.from_youtube:
        n2 = from_youtube(src)
    else:
        if not (args.slug and args.title):
            sys.exit("--slug and --title required for audio source")
        n2 = from_audio(src, args.slug, args.title, args.language)

    N2_DIR.mkdir(parents=True, exist_ok=True)
    out = N2_DIR / f"{n2['slug']}_n2.json"
    out.write_text(json.dumps(n2, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {out}")
    print(f"  source={n2['source']}  words={n2['transcript']['word_count']}  "
          f"chunks={len(n2['transcript']['chunks'])}  duration={n2['duration_seconds']}s")


if __name__ == "__main__":
    main()
