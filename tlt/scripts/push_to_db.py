#!/usr/bin/env python3
"""
push_to_db.py — On-demand push of TLT pipeline outputs to MongoDB.

Usage:
    python3 tlt/scripts/push_to_db.py <slug>           # push one video
    python3 tlt/scripts/push_to_db.py --all            # push all available slugs
    python3 tlt/scripts/push_to_db.py --list           # list pushable slugs
    python3 tlt/scripts/push_to_db.py <slug> --dry-run # preview without writing

What it pushes (all upserted — safe to re-run):
    Novel     ← from overview.md frontmatter (title + author)
    Video     ← from n2.json (youtubeId, title, duration, tags, etc.)
    Summary   ← from processed/summary/{slug}.md
    Note      ← from processed/notes/{slug}.md
    Quiz      ← from processed/quiz/{slug}.json

Reads MONGO_URI from (in priority order):
    1. MONGO_URI env var
    2. Desktop/tlt/Backend/.env
    3. Desktop/tlt/Backend/.auth-token-cache
    4. Desktop/JARVIS/.env  (TLT_MONGO_URI key)
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
TLT_DIR = SCRIPT_DIR.parent
BACKEND_ENV = Path(__file__).parents[4] / "Desktop" / "tlt" / "Backend" / ".env"
AUTH_CACHE = Path(__file__).parents[4] / "Desktop" / "tlt" / "Backend" / ".auth-token-cache"
JARVIS_ENV = Path(__file__).parents[4] / "Desktop" / "JARVIS" / ".env"

N2_DIR = TLT_DIR / "n2"
OVERVIEW_DIR = TLT_DIR / "processed" / "overview"
SUMMARY_DIR = TLT_DIR / "processed" / "summary"
NOTES_DIR = TLT_DIR / "processed" / "notes"
QUIZ_DIR = TLT_DIR / "processed" / "quiz"


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML-ish frontmatter between --- delimiters. Returns (meta, body)."""
    meta = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if m:
        fm_text, body = m.group(1), m.group(2)
        for line in fm_text.splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, body


def extract_author_from_md(md_text: str) -> str:
    m = re.search(r"\*\*Author[^:]*:\*\*\s*(.+)", md_text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\*\*Poet[^:]*:\*\*\s*(.+)", md_text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\*\*Theorist[^:]*:\*\*\s*(.+)", md_text)
    if m:
        return m.group(1).strip()
    return "Unknown"


def infer_chapter(title: str, curriculum: str) -> str:
    """Best-effort chapter string from title / curriculum."""
    for src in [title, curriculum]:
        m = re.search(r"(Chapter\s*\d+|Ch\.?\s*\d+|Part\s*\d+|Scene\s*\d+|Stanza\s*\d+)", src, re.I)
        if m:
            return m.group(0)
    return "General"


def difficulty_from_curriculum(curriculum: str) -> str:
    low = curriculum.lower()
    if any(x in low for x in ["class 6", "class 7", "class 8", "class 9", "class 10"]):
        return "beginner"
    if any(x in low for x in ["class 11", "class 12", "ba", "b.a"]):
        return "intermediate"
    if any(x in low for x in ["ma ", "m.a", "phd", "research"]):
        return "advanced"
    return "beginner"


def slugs_with_n2() -> list[str]:
    return sorted(
        p.stem.replace("_n2", "")
        for p in N2_DIR.glob("*_n2.json")
    )


# ── Core push logic ────────────────────────────────────────────────────────────

def push_slug(slug: str, db, dry_run: bool = False) -> dict:
    result = {"slug": slug, "pushed": [], "skipped": [], "errors": []}

    # ── 1. Load N2 ──────────────────────────────────────────────────────────────
    n2_path = N2_DIR / f"{slug}_n2.json"
    if not n2_path.exists():
        result["errors"].append(f"N2 not found: {n2_path}")
        return result

    n2 = json.loads(n2_path.read_text())
    yt = n2.get("youtube", {}) or {}
    video_id = yt.get("video_id", "")
    title = n2.get("title", slug)
    duration_sec = n2.get("duration_seconds", 0) or 0
    tags = yt.get("tags", []) or []
    description = yt.get("description", "") or ""
    thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else ""

    # ── 2. Load overview frontmatter ────────────────────────────────────────────
    overview_path = OVERVIEW_DIR / f"{slug}.md"
    overview_meta = {}
    overview_body = ""
    if overview_path.exists():
        overview_meta, overview_body = parse_frontmatter(overview_path.read_text())

    curriculum = overview_meta.get("curriculum", "General")
    author = extract_author_from_md(overview_body) if overview_body else "Unknown"
    chapter = infer_chapter(title, curriculum)
    difficulty = difficulty_from_curriculum(curriculum)

    # ── 3. Upsert Novel ─────────────────────────────────────────────────────────
    novel_title = title  # one Novel per video in the TLT model
    novel_doc = {
        "title": novel_title,
        "author": author,
        "description": curriculum,
        "totalChapters": 1,
        "tags": tags[:10],
        "difficulty": difficulty,
        "isPublished": False,
    }
    novel_id = None
    if not dry_run:
        now = datetime.now(timezone.utc)
        res = db.novels.find_one_and_update(
            {"title": novel_title},
            {"$setOnInsert": {"createdAt": now},
             "$set": {**novel_doc, "updatedAt": now}},
            upsert=True,
            return_document=True,
        )
        novel_id = res["_id"]
        result["pushed"].append(f"Novel: {novel_title}")
    else:
        result["pushed"].append(f"[DRY] Novel: {novel_title}")

    # ── 4. Upsert Video ─────────────────────────────────────────────────────────
    if video_id:
        video_doc = {
            "youtubeId": video_id,
            "title": title,
            "description": description[:2000],
            "thumbnail": thumbnail,
            "duration": round(duration_sec / 60),
            "novel": novel_id,
            "chapter": chapter,
            "order": 0,
            "tags": tags[:20],
            "isPublished": False,
        }
        if not dry_run:
            now = datetime.now(timezone.utc)
            db.videos.find_one_and_update(
                {"youtubeId": video_id},
                {"$setOnInsert": {"createdAt": now},
                 "$set": {**video_doc, "updatedAt": now}},
                upsert=True,
            )
            result["pushed"].append(f"Video: {video_id}")
        else:
            result["pushed"].append(f"[DRY] Video: {video_id}")
    else:
        result["skipped"].append("Video: no youtubeId in N2 (audio-source)")

    # helper to get video ObjectId for linking
    def get_video_oid():
        if dry_run or not video_id:
            return None
        v = db.videos.find_one({"youtubeId": video_id}, {"_id": 1})
        return v["_id"] if v else None

    # ── 5. Upsert Summary ───────────────────────────────────────────────────────
    summary_path = SUMMARY_DIR / f"{slug}.md"
    if summary_path.exists():
        content = summary_path.read_text()
        summary_title = f"{title} — Summary"
        summary_doc = {
            "title": summary_title,
            "content": content,
            "novel": novel_id,
            "chapter": chapter,
            "relatedVideoId": get_video_oid(),
            "importantQuotes": [],
            "isPublished": False,
        }
        if not dry_run:
            now = datetime.now(timezone.utc)
            db.summaries.find_one_and_update(
                {"novel": novel_id, "chapter": chapter, "title": summary_title},
                {"$setOnInsert": {"createdAt": now},
                 "$set": {**summary_doc, "updatedAt": now}},
                upsert=True,
            )
            result["pushed"].append("Summary")
        else:
            result["pushed"].append("[DRY] Summary")
    else:
        result["skipped"].append("Summary: file not found")

    # ── 6. Upsert Note ──────────────────────────────────────────────────────────
    note_path = NOTES_DIR / f"{slug}.md"
    if note_path.exists():
        content = note_path.read_text()
        note_title = f"{title} — Notes"
        note_doc = {
            "title": note_title,
            "content": content,
            "novel": novel_id,
            "chapter": chapter,
            "relatedVideoId": get_video_oid(),
            "tags": tags[:10],
            "isPublished": False,
        }
        if not dry_run:
            now = datetime.now(timezone.utc)
            db.notes.find_one_and_update(
                {"novel": novel_id, "chapter": chapter, "title": note_title},
                {"$setOnInsert": {"createdAt": now},
                 "$set": {**note_doc, "updatedAt": now}},
                upsert=True,
            )
            result["pushed"].append("Note")
        else:
            result["pushed"].append("[DRY] Note")
    else:
        result["skipped"].append("Note: file not found")

    # ── 7. Upsert Quiz ──────────────────────────────────────────────────────────
    quiz_path = QUIZ_DIR / f"{slug}.json"
    if quiz_path.exists():
        quiz_data = json.loads(quiz_path.read_text())
        questions = quiz_data.get("questions", [])
        total_points = sum(q.get("points", 1) for q in questions)
        quiz_title = f"{title} — Quiz"
        quiz_doc = {
            "title": quiz_title,
            "description": quiz_data.get("description", ""),
            "novel": novel_id,
            "chapter": chapter,
            "relatedVideoId": get_video_oid(),
            "questions": questions,
            "totalPoints": total_points,
            "passingScore": max(1, round(total_points * 0.6)),
            "isPublished": False,
        }
        if not dry_run:
            now = datetime.now(timezone.utc)
            db.quizzes.find_one_and_update(
                {"novel": novel_id, "chapter": chapter, "title": quiz_title},
                {"$setOnInsert": {"createdAt": now},
                 "$set": {**quiz_doc, "updatedAt": now}},
                upsert=True,
            )
            result["pushed"].append(f"Quiz ({len(questions)} questions)")
        else:
            result["pushed"].append(f"[DRY] Quiz ({len(questions)} questions)")
    else:
        result["skipped"].append("Quiz: file not found")

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Push TLT pipeline outputs to MongoDB")
    parser.add_argument("slug", nargs="?", help="Slug to push (omit with --all or --list)")
    parser.add_argument("--all", action="store_true", help="Push all available slugs")
    parser.add_argument("--list", action="store_true", help="List available slugs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()

    available = slugs_with_n2()

    if args.list:
        print(f"\nAvailable slugs ({len(available)}):\n")
        for s in available:
            parts = []
            if (SUMMARY_DIR / f"{s}.md").exists():
                parts.append("summary")
            if (NOTES_DIR / f"{s}.md").exists():
                parts.append("notes")
            if (QUIZ_DIR / f"{s}.json").exists():
                parts.append("quiz")
            print(f"  {s}  [{', '.join(parts) or 'n2 only'}]")
        return

    if not args.slug and not args.all:
        parser.print_help()
        sys.exit(1)

    # ── Connect ─────────────────────────────────────────────────────────────────
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        mongo_uri = load_env(BACKEND_ENV).get("MONGO_URI")
    if not mongo_uri and AUTH_CACHE.exists():
        try:
            mongo_uri = json.loads(AUTH_CACHE.read_text()).get("mongo", {}).get("uri")
        except Exception:
            pass
    if not mongo_uri:
        mongo_uri = load_env(JARVIS_ENV).get("TLT_MONGO_URI")
    if not mongo_uri:
        print("ERROR: MONGO_URI not found in env, Backend/.env, .auth-token-cache, or JARVIS/.env")
        sys.exit(1)

    if not args.dry_run:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri)
        db = client.get_default_database()
        print(f"Connected to MongoDB: {db.name}\n")
    else:
        db = None
        print("[DRY RUN] No writes will happen.\n")

    # ── Run ─────────────────────────────────────────────────────────────────────
    targets = available if args.all else [args.slug]

    for slug in targets:
        print(f"── {slug}")
        result = push_slug(slug, db, dry_run=args.dry_run)
        for item in result["pushed"]:
            print(f"   ✓ {item}")
        for item in result["skipped"]:
            print(f"   – {item}")
        for item in result["errors"]:
            print(f"   ✗ {item}")
        print()

    if not args.dry_run and db is not None:
        client.close()


if __name__ == "__main__":
    main()
