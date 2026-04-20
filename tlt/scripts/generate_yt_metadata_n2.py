"""
generate_yt_metadata_n2.py
--------------------------
N3d (audio-source variant) — generate YT-ready title, description, tags from
scratch for a unified N2 canonical JSON. Reads the overview markdown for rich
context. Output shape is compatible with the existing optimized_metadata/
folder so a future uploader script can consume both flows.

Usage:
  python tlt/scripts/generate_yt_metadata_n2.py --src tlt/n2/<slug>_n2.json
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
OVERVIEW_DIR = TLT / "processed" / "overview"
META_DIR = TLT / "processed" / "optimized_metadata"

load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

CTA_FOOTER = (
    "\n\n______________________________________________________________________\n"
    "Want notes, summaries & quizzes for this video? "
    "Everything's free at theliteraturetalks.com"
)

SYSTEM_PROMPT = """You are a YouTube SEO expert for an educational channel called The Literature Talks.
The channel explains literary texts (poems, stories, novels, theory) in Hindi for BA/MA English Honours
and CBSE/ICSE students preparing for university and board exams.

Generate publish-ready YouTube metadata. Return ONLY valid JSON — no markdown, no fences, no commentary.

Rules:
- title: ≤ 90 characters, max 2 pipes, keyword-front-loaded. Include the text/author + key exam terms
  (e.g. "BA English Hons", "Class 12", "DU SOL"). Mention "in Hindi" if it's a Hindi explanation.
- description: 3-5 sentence opening paragraph (what the video covers, who it's for) followed by 4-6
  bulleted highlights. Use plain text, no markdown. Do NOT add the website CTA — it will be appended.
- tags: 12-18 tags. Lowercase, comma-free strings. Include: text name (multiple variants), author name,
  themes, "english literature", curriculum tags, exam terms. Always include "the literature talks".

Schema:
{
  "title": "string ≤90 chars",
  "description": "string",
  "tags": ["tag1", "tag2", ...]
}"""


def find_overview(slug: str) -> Path | None:
    matches = list(OVERVIEW_DIR.glob(f"{slug}_*_summary.md"))
    return matches[0] if matches else None


def generate(title_hint: str, language: str, content: str) -> dict:
    client = anthropic.Anthropic(api_key=API_KEY)
    user = (
        f"Working title: {title_hint}\n"
        f"Language: {language}\n\n"
        f"Source overview content:\n{content[:6000]}\n\n"
        f"Generate YT metadata."
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    args = ap.parse_args()

    if not API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set")

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        sys.exit(f"missing: {src}")

    n2 = json.loads(src.read_text(encoding="utf-8"))
    slug = n2["slug"]
    yt = n2.get("youtube") or {}
    vid = yt.get("video_id") or "audio"

    overview = find_overview(slug)
    if not overview:
        sys.exit(f"no overview for {slug} — run summarize_n2.py first")

    print(f"→ generating YT metadata from {overview.relative_to(ROOT)}", flush=True)
    meta = generate(n2.get("title", slug), n2.get("language", "mixed"),
                    overview.read_text(encoding="utf-8"))

    # Enforce title length cap
    if len(meta.get("title", "")) > 90:
        meta["title"] = meta["title"][:87].rstrip() + "..."

    # Append standard CTA footer
    meta["description"] = (meta.get("description", "").rstrip()) + CTA_FOOTER

    # Ensure brand tag present
    tags = [t.lower().strip() for t in meta.get("tags", [])]
    if "the literature talks" not in tags:
        tags.append("the literature talks")
    meta["tags"] = tags

    out_payload = {
        "video_id": vid,
        "slug": slug,
        "source": n2.get("source", "audio"),
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"],
        "ai_done": True,
        "generated_from": "n2+overview",
    }

    META_DIR.mkdir(parents=True, exist_ok=True)
    out = META_DIR / f"{slug}_{vid}.json"
    out.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {out.relative_to(ROOT)}")
    print(f"  title  ({len(meta['title'])} chars): {meta['title']}")
    print(f"  tags   ({len(meta['tags'])}): {', '.join(meta['tags'][:5])}...")


if __name__ == "__main__":
    main()
