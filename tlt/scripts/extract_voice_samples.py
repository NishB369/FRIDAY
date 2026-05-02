#!/usr/bin/env python3
"""Download YouTube audio and extract a random 30s window per URL for voice cloning samples.

Usage:
    python extract_voice_samples.py <url> [<url> ...]
    cat urls.txt | python extract_voice_samples.py
"""
import argparse
import json
import random
import re
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "audios" / "voice_samples"
CLIP_SECONDS = 30
EDGE_BUFFER = 10  # skip first/last N seconds (intros/outros)


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[-\s]+", "_", s).strip("_")[:60]


def get_video_info(url: str) -> dict:
    out = subprocess.check_output(
        ["yt-dlp", "--no-warnings", "-J", "--skip-download", url],
        stderr=subprocess.DEVNULL,
    )
    return json.loads(out)


def download_audio(url: str, out_path: Path) -> None:
    subprocess.check_call(
        [
            "yt-dlp",
            "--no-warnings",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", str(out_path),
            url,
        ],
        stderr=subprocess.DEVNULL,
    )


def extract_clip(src: Path, dst: Path, start: float, duration: int) -> None:
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", str(start),
            "-i", str(src),
            "-t", str(duration),
            "-c:a", "libmp3lame", "-q:a", "2",
            str(dst),
        ]
    )


def process(url: str) -> Path | None:
    info = get_video_info(url)
    title = info.get("title", info.get("id", "video"))
    duration = info.get("duration") or 0
    slug = slugify(title)

    if duration < CLIP_SECONDS + 2 * EDGE_BUFFER:
        print(f"  SKIP: too short ({duration}s)", file=sys.stderr)
        return None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    full_path = OUT_DIR / f"{slug}_full.mp3"
    clip_path = OUT_DIR / f"{slug}_30s.mp3"

    if not full_path.exists():
        # yt-dlp adds extension — write to a template and rename
        tmpl = str(full_path.with_suffix(""))  # base path without ext
        download_audio(url, Path(tmpl + ".%(ext)s"))

    start = random.uniform(EDGE_BUFFER, duration - CLIP_SECONDS - EDGE_BUFFER)
    extract_clip(full_path, clip_path, start, CLIP_SECONDS)

    # Cleanup full audio to save disk
    full_path.unlink(missing_ok=True)

    print(f"  -> {clip_path} (start={start:.1f}s, total={duration}s)", file=sys.stderr)
    return clip_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="YouTube URLs (omit to read stdin)")
    args = parser.parse_args()

    urls = args.urls if args.urls else [u.strip() for u in sys.stdin if u.strip()]
    if not urls:
        print("error: no URLs provided", file=sys.stderr)
        return 1

    paths = []
    for url in urls:
        print(f"[{url}]", file=sys.stderr)
        try:
            p = process(url)
            if p:
                paths.append(p)
        except subprocess.CalledProcessError as e:
            print(f"  FAIL: {e}", file=sys.stderr)

    # stdout: one clip path per line — feed into next step
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
