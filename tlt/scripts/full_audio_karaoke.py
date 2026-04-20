"""
full_audio_karaoke.py
---------------------
End-to-end karaoke for any-length audio:
  1. Probe duration
  2. Chunk to ≤29s pieces, run dual_transcribe per chunk
  3. Merge aligned words across chunks (offset corrected)
  4. Optionally transliterate Devanagari → Hinglish via Claude
  5. Build Remotion props
  6. Render + mux against the full source audio

Usage:
  python tlt/scripts/full_audio_karaoke.py \\
      --src "tlt/audios/New Recording.m4a" \\
      --slug new_recording --hinglish --delay-ms 200
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AUDIO_DIR = ROOT / "tlt" / "audios"
TRANSCRIPT_DIR = ROOT / "tlt" / "transcripts"
PROPS_DIR = ROOT / "remotion" / "props"
OUT_DIR = ROOT / "remotion" / "outputs"
SCRIPTS = ROOT / "tlt" / "scripts"
PYTHON = str(ROOT / ".venv" / "bin" / "python")
CHUNK_SECONDS = 29


def run(cmd, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        sys.exit(f"command failed: {cmd}")
    return r


def probe_duration(src: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(src)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def to_full_mp3(src: Path, slug: str) -> Path:
    out = AUDIO_DIR / f"{slug}_full.mp3"
    run(["ffmpeg", "-y", "-i", str(src), "-c:a", "libmp3lame", "-b:a", "128k", str(out)],
        capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--delay-ms", type=int, default=200)
    ap.add_argument("--hinglish", action="store_true")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    if not src.exists():
        sys.exit(f"missing source: {src}")

    duration = probe_duration(src)
    n_chunks = int((duration + CHUNK_SECONDS - 1) // CHUNK_SECONDS)
    print(f"duration={duration:.1f}s  chunks={n_chunks} (×{CHUNK_SECONDS}s)")

    full_audio = to_full_mp3(src, args.slug)

    all_words = []
    for i in range(n_chunks):
        start = i * CHUNK_SECONDS
        dur = min(CHUNK_SECONDS, int(duration - start))
        if dur < 2:
            print(f"skip chunk {i}: only {dur}s remaining")
            break
        print(f"\n=== chunk {i + 1}/{n_chunks}  start={start}s dur={dur}s ===")
        run([PYTHON, str(SCRIPTS / "dual_transcribe.py"),
             "--slug", args.slug, "--src", str(src),
             "--start", str(start), "--duration", str(dur)])

        chunk_json = TRANSCRIPT_DIR / f"{args.slug}_{start}-{start + dur}s_dual.json"
        data = json.loads(chunk_json.read_text(encoding="utf-8"))
        for w in data.get("words", []):
            all_words.append({
                "word": w["word"],
                "start": round(w["start"] + start, 3),
                "end": round(w["end"] + start, 3),
            })

    print(f"\nmerged {len(all_words)} words across {n_chunks} chunks")

    # Save merged transcript
    merged_path = TRANSCRIPT_DIR / f"{args.slug}_merged.json"
    merged_path.write_text(
        json.dumps({"words": all_words, "duration": duration}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"merged transcript → {merged_path}")

    # Optional Hinglish pass — reuse the function from dual_to_karaoke.py
    if args.hinglish:
        sys.path.insert(0, str(SCRIPTS))
        from dual_to_karaoke import transliterate_hinglish
        all_words = transliterate_hinglish(all_words)

    # Apply delay offset (highlight lands after spoken word)
    delay = args.delay_ms / 1000.0
    words_out = [
        {"word": w["word"],
         "startSec": round(w["start"] + delay, 3),
         "endSec": round(w["end"] + delay, 3)}
        for w in all_words
    ]

    fps = 30
    total = max(words_out[-1]["endSec"], duration)
    props = {
        "words": words_out,
        "totalDurationSec": round(total, 3),
        "fps": fps,
        "wordsPerScreen": 18,
        "bgColor": "#F5F4F0",
        "textActive": "#1A1A1A",
        "textPast": "#AAAAAA",
        "textFuture": "#CCCCCC",
        "fontSize": 52,
        "fontFamily": "Georgia, 'Times New Roman', serif",
    }
    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    props_path = PROPS_DIR / f"{args.slug}_full.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"props → {props_path}")

    # Render
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = int(total * fps)
    silent = OUT_DIR / f"{args.slug}_full_silent.mp4"
    final = OUT_DIR / f"{args.slug}_full.mp4"
    print(f"\nrendering {frames} frames...")
    run(["npx", "remotion", "render", "TranscriptKaraoke",
         str(silent.relative_to(ROOT / "remotion")),
         f"--props=props/{args.slug}_full.json",
         f"--frames=0-{frames - 1}"],
        cwd=str(ROOT / "remotion"))

    print("\nmuxing audio...")
    run(["ffmpeg", "-y", "-i", str(silent), "-i", str(full_audio),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)],
        capture_output=True)
    print(f"\n✓ done → {final}")


if __name__ == "__main__":
    main()
