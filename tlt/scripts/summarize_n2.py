"""
summarize_n2.py
---------------
N3a — generate the master "overview" doc from a unified N2 canonical JSON,
then split it into derived "summary" (narrative half) and "notes" (analysis
half) views. Three artifacts per video, identical filename across dirs:

  tlt/processed/overview/<slug>_<vid>_summary.md   — full doc + YAML frontmatter
  tlt/processed/summary/<slug>_<vid>_summary.md    — About + Background + Walkthrough + Quotes
  tlt/processed/notes/<slug>_<vid>_summary.md      — About + Themes + Devices + Quotes + Takeaways

Usage:
  python tlt/scripts/summarize_n2.py --src tlt/n2/<slug>_n2.json
  python tlt/scripts/summarize_n2.py --src tlt/n2/<slug>_n2.json --skip-overview  # only re-split
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TLT = ROOT / "tlt"
PROCESSED = TLT / "processed"
OVERVIEW_DIR = PROCESSED / "overview"
SUMMARY_DIR = PROCESSED / "summary"
NOTES_DIR = PROCESSED / "notes"

SUMMARY_KEEP = {"about", "background", "walkthrough", "plot", "stanza",
                "chapter", "text overview", "key ideas", "quotes"}
NOTES_KEEP = {"about", "themes", "literary devices", "key terminology",
              "key concepts", "quotes", "takeaways"}


def generate_overview(n2_path: Path, out_rel: str) -> int:
    src_rel = n2_path.relative_to(TLT)
    prompt = (
        f"Read the N2 canonical JSON at {src_rel} and generate a comprehensive "
        f"educational summary following the structure in CLAUDE.md. The N2 shape "
        f"has top-level title, language, duration_seconds, transcript.full_text, "
        f"transcript.chunks, and an optional youtube block (video_id, channel, "
        f"published_at, description, tags). For audio sources, the youtube block "
        f"is absent — derive curriculum/keywords from title + transcript content. "
        f"Always include the YAML frontmatter block. "
        f"Write the output to {out_rel}."
    )
    print(f"→ overview: {out_rel}\n... claude generating", flush=True)
    r = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "Read,Write",
         "--no-session-persistence", "--output-format", "text"],
        cwd=str(TLT), stdin=subprocess.DEVNULL,
    )
    return r.returncode


def split_overview(overview_path: Path, summary_path: Path, notes_path: Path):
    """Strip frontmatter, split sections by H2 heading into summary/notes views."""
    text = overview_path.read_text(encoding="utf-8")

    # Drop YAML frontmatter
    body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)

    # Split on H2 boundaries, keep the heading attached to its block
    parts = re.split(r"(?m)^(?=## )", body)
    header = parts[0]  # title + bold metadata block before first H2
    sections = parts[1:]

    def pick(keep_terms):
        out = [header]
        for sec in sections:
            first_line = sec.splitlines()[0].lower()
            if any(term in first_line for term in keep_terms):
                out.append(sec)
        return "".join(out).rstrip() + "\n"

    summary_path.write_text(pick(SUMMARY_KEEP), encoding="utf-8")
    notes_path.write_text(pick(NOTES_KEEP), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--skip-overview", action="store_true",
                    help="reuse existing overview, only re-derive summary+notes")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        sys.exit(f"missing: {src}")

    n2 = json.loads(src.read_text(encoding="utf-8"))
    if not n2.get("transcript", {}).get("available"):
        sys.exit("transcript not available in this N2")

    slug = n2["slug"]
    vid = (n2.get("youtube") or {}).get("video_id") or "audio"
    fname = f"{slug}_{vid}_summary.md"

    for d in (OVERVIEW_DIR, SUMMARY_DIR, NOTES_DIR):
        d.mkdir(parents=True, exist_ok=True)

    overview_path = OVERVIEW_DIR / fname
    summary_path = SUMMARY_DIR / fname
    notes_path = NOTES_DIR / fname

    if not args.skip_overview:
        rc = generate_overview(src, f"processed/overview/{fname}")
        if rc != 0 or not overview_path.exists():
            sys.exit(f"overview generation failed (exit {rc})")
        print(f"✓ overview  {overview_path.stat().st_size / 1024:.1f} KB")

    if not overview_path.exists():
        sys.exit(f"missing overview: {overview_path}")

    split_overview(overview_path, summary_path, notes_path)
    print(f"✓ summary   {summary_path.stat().st_size / 1024:.1f} KB  → {summary_path.relative_to(ROOT)}")
    print(f"✓ notes     {notes_path.stat().st_size / 1024:.1f} KB  → {notes_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
