"""
build_sarvam_dashboard.py
-------------------------
Render dual-source transcripts (Sarvam text + Groq word timestamps, aligned)
at tlt/reports/sarvam_review.html.

Pairs <slug>_<start>-<end>s.mp3 with <slug>_<start>-<end>s_dual.json.
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AUDIO_DIR = ROOT / "tlt" / "audios"
TRANSCRIPT_DIR = ROOT / "tlt" / "transcripts"
OUT = ROOT / "tlt" / "reports" / "sarvam_review.html"

CLIP_RE = re.compile(r"_\d+-\d+s$")


def find_transcript(stem: str) -> Path | None:
    cand = TRANSCRIPT_DIR / f"{stem}_dual.json"
    return cand if cand.exists() else None


def render_words(words: list[dict]) -> str:
    if not words:
        return "<em>no word-level timing</em>"
    chips = []
    for w in words:
        chips.append(
            f'<span class="chip" title="{w["start"]:.2f}s – {w["end"]:.2f}s">'
            f'{html.escape(w["word"])}'
            f'<small>{w["start"]:.1f}</small></span>'
        )
    return "".join(chips)


def render() -> str:
    audios = sorted(p for p in AUDIO_DIR.glob("*.mp3") if CLIP_RE.search(p.stem))
    rows = []
    for i, audio in enumerate(audios, 1):
        rel_audio = f"../audios/{audio.name}"
        tpath = find_transcript(audio.stem)
        if tpath:
            data = json.loads(tpath.read_text(encoding="utf-8"))
            transcript = (data.get("transcript") or "").strip()
            words = data.get("words") or []
            duration = data.get("duration", 0)
            tlabel = tpath.name
            meta = f"{len(words)} words · {duration:.1f}s · sarvam-text + groq-timing"
        else:
            transcript, words, tlabel, meta = "", [], "—", ""

        rows.append(f"""
        <tr>
          <td class="sn">{i}</td>
          <td class="audio-cell">
            <div class="fname">{html.escape(audio.name)}</div>
            <audio controls preload="none" src="{html.escape(rel_audio)}"></audio>
            <div class="tname">transcript: {html.escape(tlabel)}</div>
          </td>
          <td class="out">
            <div class="meta">{html.escape(meta)}</div>
            <div class="text">{html.escape(transcript) or '<em>no transcript yet</em>'}</div>
            <details class="words"><summary>word-level timing ({len(words)} words)</summary>
              <div class="chips">{render_words(words)}</div>
            </details>
          </td>
        </tr>
        """)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TLT — Dual Transcript Review (Sarvam + Groq)</title>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px; background: #fafafa; color: #1a1a1a; }}
    h1 {{ font-size: 20px; margin: 0 0 16px; }}
    .sub {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; }}
    th, td {{ border: 1px solid #ddd; padding: 12px; vertical-align: top; text-align: left; }}
    th {{ background: #f0f0f0; font-size: 13px; }}
    .sn {{ width: 40px; text-align: center; color: #888; }}
    .audio-cell {{ width: 320px; }}
    .fname {{ font-size: 12px; font-weight: 600; word-break: break-all; margin-bottom: 6px; }}
    .tname {{ font-size: 11px; color: #888; margin-top: 6px; word-break: break-all; }}
    audio {{ width: 100%; }}
    .out .meta {{ font-size: 11px; color: #555; margin-bottom: 8px; }}
    .out .text {{ font-size: 14px; line-height: 1.55; white-space: pre-wrap; margin-bottom: 12px; }}
    .words summary {{ cursor: pointer; font-size: 12px; color: #555; }}
    .chips {{ margin-top: 8px; line-height: 2.2; }}
    .chip {{ display: inline-block; background: #eef3ff; border: 1px solid #c5d3f0; border-radius: 4px;
             padding: 2px 6px; margin: 0 4px 4px 0; font-size: 13px; }}
    .chip small {{ color: #888; font-size: 9px; margin-left: 4px; vertical-align: top; }}
  </style>
</head>
<body>
  <h1>TLT — Dual Transcript Review</h1>
  <div class="sub">{len(audios)} clip(s) · text from Sarvam (saaras:v3) · word timing from Groq (whisper-large-v3) · aligned proportionally</div>
  <table>
    <thead><tr><th>#</th><th>Audio</th><th>Transcript + Word Timing</th></tr></thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
