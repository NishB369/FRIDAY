"""
generate_thumbnail.py
---------------------
N4-VIDEO (thumbnail) — render a 1280x720 YouTube thumbnail from a unified N2
canonical JSON. Intent-first, text-dominant, paper-tone aesthetic that matches
the karaoke video itself. Uses Claude to extract clean work title, author, and
curriculum chip from the N2 title/description.

Usage:
  python tlt/scripts/generate_thumbnail.py --src tlt/n2/<slug>_n2.json
  python tlt/scripts/generate_thumbnail.py --src ... --no-llm \
      --work "Doctor Faustus" --author "Christopher Marlowe" \
      --chip "BA ENGLISH HONS · DU SOL"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "remotion" / "outputs"

load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Paper-tone editorial palette.
BG_COLOR       = (245, 244, 240)
TEXT_PRIMARY   = (26, 26, 26)
TEXT_MUTED     = (110, 108, 102)
ACCENT         = (196, 138, 56)
RULE_COLOR     = (26, 26, 26)

FONT_SERIF        = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONT_SERIF_REG    = "/System/Library/Fonts/Supplemental/Georgia.ttf"
FONT_SERIF_ITAL   = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"

W, H = 1280, 720
MARGIN = 80

EXTRACT_PROMPT = """Extract clean YouTube thumbnail fields from a literature lesson video.

Rules:
- Return ONLY valid JSON — no markdown, no commentary.
- work_title: the primary text/topic (e.g. "Doctor Faustus", "Sonnet 18", "The Color Purple").
  ≤ 28 characters. Title Case. No author name, no "summary in Hindi", no platform names.
- author: full name of the author/poet/theorist if there is one, else "" (empty string).
  ≤ 28 characters.
- chip: tiny top-left label — the curriculum context. ≤ 32 characters, UPPERCASE, separators " · ".
  Mix 2–3 of: exam level (BA ENG HONS, CLASS 12, CLASS 6), institution (DU SOL, IGNOU, CBSE),
  topic kind (POETRY, DRAMA, FICTION, THEORY). Prefer the most specific markers in the source.
- tagline: one short italic line ≤ 48 characters describing the video's angle
  (e.g. "Line-by-line summary in Hindi", "Themes & key questions").

Schema:
{"work_title": "...", "author": "...", "chip": "...", "tagline": "..."}"""


def extract_fields(n2_title: str, n2_desc: str) -> dict:
    client = anthropic.Anthropic(api_key=API_KEY)
    user = (
        f"Working title: {n2_title}\n\n"
        f"Description excerpt:\n{n2_desc[:2500]}\n\n"
        "Return the JSON."
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=EXTRACT_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def fit_font(text: str, path: str, max_width: int, start_px: int, min_px: int = 28) -> ImageFont.FreeTypeFont:
    size = start_px
    while size > min_px:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_width:
            return f
        size -= 2
    return ImageFont.truetype(path, min_px)


def draw_thumbnail(work: str, author: str, chip: str, tagline: str, out_path: Path) -> None:
    canvas = Image.new("RGB", (W, H), BG_COLOR)
    d = ImageDraw.Draw(canvas)

    # Top-left chip — small uppercase curriculum label in accent.
    chip_font = ImageFont.truetype(FONT_SERIF, 24)
    d.text((MARGIN, MARGIN), chip.upper(), font=chip_font, fill=ACCENT)

    # Thin accent rule under the chip.
    chip_w = chip_font.getlength(chip.upper())
    rule_y = MARGIN + 38
    d.line([(MARGIN, rule_y), (MARGIN + chip_w, rule_y)], fill=ACCENT, width=2)

    # Work title — big Georgia Bold, left-aligned, may wrap to 2 lines.
    content_w = W - 2 * MARGIN
    title_font = fit_font(work, FONT_SERIF, content_w, start_px=180, min_px=96)
    title_y = 180
    d.text((MARGIN, title_y), work, font=title_font, fill=TEXT_PRIMARY)

    # Author — Georgia Italic, muted.
    _, _, _, title_bottom = title_font.getbbox(work)
    after_title_y = title_y + title_bottom + 12
    if author:
        author_font = ImageFont.truetype(FONT_SERIF_ITAL, 42)
        d.text((MARGIN, after_title_y), author, font=author_font, fill=TEXT_MUTED)
        after_title_y += 58

    # Tagline — italic serif, accent-tinted, one line.
    if tagline:
        tag_font = fit_font(tagline, FONT_SERIF_ITAL, content_w, start_px=36, min_px=24)
        d.text((MARGIN, H - MARGIN - 80), tagline, font=tag_font, fill=ACCENT)

    # Bottom rule + brand.
    brand_font = ImageFont.truetype(FONT_SERIF, 22)
    brand = "THE LITERATURE TALKS"
    brand_w = brand_font.getlength(brand)
    rule_y2 = H - MARGIN - 20
    d.line([(MARGIN, rule_y2), (W - MARGIN, rule_y2)], fill=RULE_COLOR, width=1)
    d.text((W - MARGIN - brand_w, rule_y2 + 10), brand, font=brand_font, fill=TEXT_PRIMARY)

    canvas.save(out_path, "PNG", optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="path to tlt/n2/<slug>_n2.json")
    ap.add_argument("--no-llm", action="store_true",
                    help="skip Claude extraction; require --work/--author/--chip")
    ap.add_argument("--work", help="explicit work title (with --no-llm)")
    ap.add_argument("--author", default="", help="explicit author (with --no-llm)")
    ap.add_argument("--chip", help="explicit curriculum chip (with --no-llm)")
    ap.add_argument("--tagline", default="", help="explicit tagline (with --no-llm)")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        sys.exit(f"missing: {src}")

    n2 = json.loads(src.read_text(encoding="utf-8"))
    slug = n2["slug"]
    n2_title = n2.get("title", slug)
    n2_desc = n2.get("description") or (n2.get("transcript") or {}).get("full_text", "")[:2500]

    if args.no_llm:
        if not (args.work and args.chip):
            sys.exit("--no-llm requires --work and --chip")
        fields = {"work_title": args.work, "author": args.author,
                  "chip": args.chip, "tagline": args.tagline}
    else:
        if not API_KEY:
            sys.exit("ANTHROPIC_API_KEY not set (use --no-llm with explicit fields)")
        print(f"→ extracting thumbnail fields for {slug}", flush=True)
        fields = extract_fields(n2_title, n2_desc)

    work    = (args.work    or fields["work_title"]).strip()
    author  = (args.author  or fields.get("author", "")).strip()
    chip    = (args.chip    or fields["chip"]).strip()
    tagline = (args.tagline or fields.get("tagline", "")).strip()

    print(f"  chip:    {chip}")
    print(f"  work:    {work}")
    print(f"  author:  {author}")
    print(f"  tagline: {tagline}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{slug}_thumbnail.png"
    draw_thumbnail(work, author, chip, tagline, out)
    print(f"✓ {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
