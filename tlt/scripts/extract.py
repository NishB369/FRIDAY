#!/usr/bin/env python3
"""
extract.py — Standalone YouTube video extractor.
Replaces the yt-data-extractor Next.js server for pipeline use.

Usage:
    python3 tlt/scripts/extract.py <youtube_url> <output_path.json>

Loads YOUTUBE_API_KEY from (in order):
    1. Environment variable YOUTUBE_API_KEY
    2. yt-data-extractor/.env.local
    3. .env at repo root
"""

import json, os, re, sys
from pathlib import Path


# ── Key loading ────────────────────────────────────────────────────────────

def load_api_key() -> str:
    # 1. Already in environment
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if key:
        return key

    # 2. yt-data-extractor/.env.local
    # 3. repo root .env
    base = Path(__file__).resolve().parents[2]  # FRIDAY root
    candidates = [
        base / "yt-data-extractor" / ".env.local",
        base / ".env",
    ]
    for path in candidates:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("YOUTUBE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    return ""


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def parse_duration(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "PT0S")
    if not m:
        return 0
    h, mi, s = m.group(1), m.group(2), m.group(3)
    return int(h or 0) * 3600 + int(mi or 0) * 60 + int(s or 0)


# ── Fetchers ───────────────────────────────────────────────────────────────

def fetch_metadata(video_id: str, api_key: str) -> dict:
    import urllib.request
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet,statistics,contentDetails&id={video_id}&key={api_key}"
    )
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    if not data.get("items"):
        raise ValueError(f"Video not found or private: {video_id}")

    item = data["items"][0]
    s  = item["snippet"]
    st = item.get("statistics", {})
    cd = item.get("contentDetails", {})

    thumbnails = s.get("thumbnails", {})
    thumb = (thumbnails.get("maxres") or thumbnails.get("high") or {}).get("url", "")

    return {
        "video_id":        video_id,
        "url":             f"https://www.youtube.com/watch?v={video_id}",
        "title":           s.get("title", ""),
        "channel":         s.get("channelTitle", ""),
        "channel_id":      s.get("channelId", ""),
        "description":     s.get("description", ""),
        "published_at":    s.get("publishedAt", ""),
        "upload_date":     (s.get("publishedAt", "")[:10] or "").replace("-", ""),
        "duration_seconds": parse_duration(cd.get("duration", "PT0S")),
        "thumbnail":       thumb,
        "tags":            s.get("tags", []),
        "category_id":     s.get("categoryId", ""),
        "view_count":      int(st.get("viewCount", 0)),
        "like_count":      int(st.get("likeCount", 0)),
        "comment_count":   int(st.get("commentCount", 0)),
        "language":        s.get("defaultAudioLanguage") or s.get("defaultLanguage"),
    }


def fetch_comments(video_id: str, api_key: str, max_results: int = 50) -> list:
    import urllib.request
    url = (
        f"https://www.googleapis.com/youtube/v3/commentThreads"
        f"?part=snippet&videoId={video_id}&maxResults={max_results}"
        f"&order=relevance&key={api_key}"
    )
    try:
        with urllib.request.urlopen(url) as r:
            data = json.loads(r.read())
    except Exception:
        return []

    comments = []
    for item in data.get("items", []):
        c = item["snippet"]["topLevelComment"]["snippet"]
        comments.append({
            "author":       c.get("authorDisplayName", ""),
            "text":         c.get("textDisplay", ""),
            "likes":        c.get("likeCount", 0),
            "published_at": c.get("publishedAt", ""),
            "reply_count":  item["snippet"].get("totalReplyCount", 0),
        })
    return comments


def fetch_transcript(video_id: str) -> dict:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        chunks = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join(c["text"] for c in chunks)
        return {
            "available":  True,
            "word_count": len(full_text.split()),
            "full_text":  full_text,
            "chunks": [
                {
                    "text":     c["text"],
                    "offset":   round(c["start"]),
                    "duration": round(c.get("duration", 0)),
                }
                for c in chunks
            ],
        }
    except Exception as e:
        print(f"  [transcript] unavailable: {e}", file=sys.stderr)
        return {"available": False, "word_count": 0, "full_text": None, "chunks": []}


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: extract.py <youtube_url> <output.json>", file=sys.stderr)
        sys.exit(1)

    yt_url  = sys.argv[1]
    outpath = sys.argv[2]

    # Key check
    api_key = load_api_key()
    if not api_key:
        print(
            "ERROR: YOUTUBE_API_KEY not found.\n"
            "Set it in yt-data-extractor/.env.local, .env, or as an environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Video ID
    video_id = extract_video_id(yt_url)
    if not video_id:
        print(f"ERROR: Could not extract video ID from: {yt_url}", file=sys.stderr)
        sys.exit(1)

    # Fetch
    metadata   = fetch_metadata(video_id, api_key)
    comments   = fetch_comments(video_id, api_key)
    transcript = fetch_transcript(video_id)

    # Assemble + write
    result = {**metadata, "comments": comments, "transcript": transcript}
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Saved: {outpath}", file=sys.stderr)


if __name__ == "__main__":
    main()
