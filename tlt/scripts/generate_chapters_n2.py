"""
generate_chapters_n2.py
-----------------------
N4-VIDEO (chapters) — segment a unified N2 canonical JSON into YouTube-ready
chapter markers. Uses Claude to pick semantic boundaries over the N2 transcript
chunks, then enforces YT's rules: first chapter at 0:00, at least 3 chapters,
each ≥10s long, timestamps snap to real chunk offsets (no hallucinated times).

Outputs:
  tlt/processed/chapters/{slug}_{video_id}.json
  (optional) patches optimized_metadata/{slug}_{video_id}.json description by
  inserting a "Chapters:\n..." block above the CTA footer.

Usage:
  python tlt/scripts/generate_chapters_n2.py --src tlt/n2/<slug>_n2.json
  python tlt/scripts/generate_chapters_n2.py --src ... --no-patch
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
TLT = ROOT / "tlt"
CHAPTERS_DIR = TLT / "processed" / "chapters"
META_DIR = TLT / "processed" / "optimized_metadata"

load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

MIN_GAP_SECONDS = 10
MIN_CHAPTERS = 3
MAX_CHAPTERS = 8
MAX_TITLE_CHARS = 45

SYSTEM_PROMPT = """You segment educational video transcripts into YouTube chapters.

Rules:
- Return ONLY valid JSON — no markdown, no fences, no commentary.
- Produce between 3 and 8 chapters.
- The first chapter MUST start at offset 0.
- Each chapter title ≤ 45 characters, in English (even when transcript is Hindi/mixed).
- Titles are descriptive section labels (e.g. "Introduction", "About the Author",
  "Key Themes", "Plot Summary"), not verbatim transcript lines.
- Use ONLY timestamps that appear in the provided chunk offset list — never invent a time.
- Chapters must be at least 10 seconds apart.
- Order chapters chronologically.

Schema:
{
  "chapters": [
    {"start_seconds": 0,   "title": "Introduction"},
    {"start_seconds": 42,  "title": "About Christopher Marlowe"},
    ...
  ]
}"""


def fmt_ts(sec: int) -> str:
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_chunk_digest(chunks: list[dict]) -> str:
    lines = []
    for c in chunks:
        off = int(c.get("offset", 0))
        text = (c.get("text") or "").strip().replace("\n", " ")
        lines.append(f"[{fmt_ts(off)} | {off}s] {text}")
    return "\n".join(lines)


def call_claude(title: str, language: str, digest: str, duration: int) -> dict:
    client = anthropic.Anthropic(api_key=API_KEY)
    user = (
        f"Video title: {title}\n"
        f"Language: {language}\n"
        f"Total duration: {duration}s ({fmt_ts(duration)})\n\n"
        f"Transcript chunks (timestamp | offset-seconds | text):\n"
        f"{digest}\n\n"
        "Segment into YouTube chapters. Pick natural topic boundaries — "
        "intro, biography, themes, plot, conclusion, etc. Keep titles short and exam-friendly."
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def validate_and_snap(proposed: list[dict], chunks: list[dict], duration: int) -> list[dict]:
    """Snap each proposed start to the nearest chunk offset at or before it,
    then enforce MIN_GAP/MIN/MAX rules. Truncate titles."""
    offsets = sorted({int(c.get("offset", 0)) for c in chunks})
    if not offsets or offsets[0] != 0:
        offsets = [0] + offsets

    out = []
    seen = set()
    for item in proposed:
        t = int(item.get("start_seconds", -1))
        if t < 0 or t >= duration:
            continue
        snapped = max((o for o in offsets if o <= t), default=0)
        if snapped in seen:
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        if len(title) > MAX_TITLE_CHARS:
            title = title[: MAX_TITLE_CHARS - 1].rstrip() + "…"
        out.append({"start_seconds": snapped, "title": title})
        seen.add(snapped)

    out.sort(key=lambda c: c["start_seconds"])

    if not out or out[0]["start_seconds"] != 0:
        out.insert(0, {"start_seconds": 0, "title": "Introduction"})

    filtered = [out[0]]
    for c in out[1:]:
        if c["start_seconds"] - filtered[-1]["start_seconds"] >= MIN_GAP_SECONDS:
            filtered.append(c)
        if len(filtered) >= MAX_CHAPTERS:
            break

    if len(filtered) < MIN_CHAPTERS:
        raise ValueError(
            f"only {len(filtered)} valid chapters after enforcement "
            f"(need ≥ {MIN_CHAPTERS}); LLM output may be too sparse"
        )
    return filtered


def render_block(chapters: list[dict]) -> str:
    lines = ["Chapters:"]
    for c in chapters:
        lines.append(f"{fmt_ts(c['start_seconds'])} {c['title']}")
    return "\n".join(lines)


def patch_metadata(meta_path: Path, block: str) -> None:
    if not meta_path.exists():
        print(f"  (skip patch: no metadata at {meta_path.relative_to(ROOT)})")
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    desc = meta.get("description", "")

    # Remove any previous chapter block we wrote.
    desc = re.sub(r"\n*Chapters:\n(?:\d+:\d{2}(?::\d{2})? .+\n?)+", "\n", desc).strip()

    cta_marker = "______________________________________________________________________"
    if cta_marker in desc:
        head, _, tail = desc.partition(cta_marker)
        new_desc = head.rstrip() + "\n\n" + block + "\n\n" + cta_marker + tail
    else:
        new_desc = desc.rstrip() + "\n\n" + block

    meta["description"] = new_desc
    meta["chapters_done"] = True
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ patched {meta_path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="path to tlt/n2/<slug>_n2.json")
    ap.add_argument("--no-patch", action="store_true",
                    help="don't inject chapters into optimized_metadata description")
    args = ap.parse_args()

    if not API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set")

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        sys.exit(f"missing: {src}")

    n2 = json.loads(src.read_text(encoding="utf-8"))
    slug = n2["slug"]
    vid = (n2.get("youtube") or {}).get("video_id") or "audio"
    duration = int(n2.get("duration_seconds") or 0)
    chunks = (n2.get("transcript") or {}).get("chunks") or []

    if not chunks:
        sys.exit(f"no transcript chunks in {src}")
    if duration < 30:
        sys.exit(f"duration {duration}s too short for chapters")

    print(f"→ segmenting {slug} ({fmt_ts(duration)}, {len(chunks)} chunks)", flush=True)
    digest = build_chunk_digest(chunks)
    proposed = call_claude(n2.get("title", slug), n2.get("language", "mixed"),
                           digest, duration).get("chapters", [])
    if not proposed:
        sys.exit("LLM returned no chapters")

    chapters = validate_and_snap(proposed, chunks, duration)

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    out = CHAPTERS_DIR / f"{slug}_{vid}.json"
    out.write_text(
        json.dumps(
            {"slug": slug, "video_id": vid, "duration_seconds": duration,
             "chapters": chapters},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✓ {out.relative_to(ROOT)}")
    for c in chapters:
        print(f"  {fmt_ts(c['start_seconds'])}  {c['title']}")

    if not args.no_patch:
        patch_metadata(META_DIR / f"{slug}_{vid}.json", render_block(chapters))


if __name__ == "__main__":
    main()
