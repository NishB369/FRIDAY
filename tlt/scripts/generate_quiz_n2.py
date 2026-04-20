"""
generate_quiz_n2.py
-------------------
N3c — generate a quiz JSON from a unified N2 canonical JSON. Reads the
overview markdown produced by summarize_n2.py (richer than raw N2) and
calls Claude Haiku for 6 questions (4 MCQ + 2 T/F). Optional --push for
YT-sourced items (audio items skip DB push).

Usage:
  python tlt/scripts/generate_quiz_n2.py --src tlt/n2/<slug>_n2.json
  python tlt/scripts/generate_quiz_n2.py --src tlt/n2/<slug>_n2.json --push
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
TLT = ROOT / "tlt"
OVERVIEW_DIR = TLT / "processed" / "overview"
QUIZ_DIR = TLT / "processed" / "quiz"

load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DB_BASE = "https://tlt-m17y.onrender.com/api"
NOVEL_ID = "69da827a5196cf62d88a3980"

SYSTEM_PROMPT = """You are an expert English literature teacher creating quiz questions for students.
Given the content of a literature explanation video, generate quiz questions that test comprehension and understanding.

Rules:
- Generate exactly 6 questions: 4 MCQ + 2 True/False
- MCQ: 4 answer options, exactly one correct
- True/False: question must have a clear True or False answer
- correctAnswer for MCQ = the exact option text (string), not a number
- correctAnswer for True/False = "True" or "False"
- Keep questions clear, factual, based strictly on the content provided
- Explanations should be 1-2 sentences explaining why the answer is correct
- Points = 1 for every question

Return ONLY valid JSON — no markdown, no code fences, no extra text:
{
  "description": "one line description of what this quiz tests",
  "questions": [
    {"question": "...", "type": "mcq", "options": ["A","B","C","D"], "correctAnswer": "A", "explanation": "...", "points": 1},
    {"question": "...", "type": "true-false", "options": ["True","False"], "correctAnswer": "True", "explanation": "...", "points": 1}
  ]
}"""


def find_overview(slug: str) -> Path | None:
    matches = list(OVERVIEW_DIR.glob(f"{slug}_*_summary.md"))
    return matches[0] if matches else None


def generate(title: str, content: str) -> dict:
    client = anthropic.Anthropic(api_key=API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content":
            f"Video title: {title}\n\nContent:\n{content[:6000]}\n\nGenerate a quiz based on the above content."}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def push(payload: dict):
    r = requests.post(f"{DB_BASE}/quizzes", json=payload)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--push", action="store_true",
                    help="push to remote DB (only valid for source=youtube)")
    args = ap.parse_args()

    if not API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set")

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        sys.exit(f"missing: {src}")

    n2 = json.loads(src.read_text(encoding="utf-8"))
    slug = n2["slug"]
    title = n2.get("title", slug)
    yt = n2.get("youtube") or {}
    vid = yt.get("video_id") or "audio"

    overview = find_overview(slug)
    if not overview:
        sys.exit(f"no overview for {slug} — run summarize_n2.py first")

    print(f"→ generating quiz from {overview.relative_to(ROOT)}", flush=True)
    quiz = generate(title, overview.read_text(encoding="utf-8"))

    QUIZ_DIR.mkdir(parents=True, exist_ok=True)
    out = QUIZ_DIR / f"{slug}_{vid}_quiz.json"
    out.write_text(json.dumps(quiz, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {out.relative_to(ROOT)}  ({len(quiz.get('questions', []))} questions)")

    if args.push:
        if n2.get("source") != "youtube":
            print("skip push: source is not youtube")
            return
        if not yt.get("video_id"):
            sys.exit("cannot push: missing youtube.video_id")
        # Resolve DB id from youtubeId
        videos = requests.get(f"{DB_BASE}/videos?limit=300").json()["data"]["data"]
        match = next((v for v in videos if v.get("youtubeId") == yt["video_id"]), None)
        if not match:
            sys.exit(f"no DB video row for youtubeId={yt['video_id']}")
        payload = {
            "title": f"Quiz: {title}",
            "description": quiz.get("description", f"Test your understanding of {title}"),
            "novel": NOVEL_ID,
            "chapter": "Uncategorized",
            "relatedVideoId": match["_id"],
            "timeLimit": 10,
            "passingScore": 70,
            "isPublished": False,
            "questions": quiz.get("questions", []),
        }
        push(payload)
        print(f"✓ pushed to DB → relatedVideoId={match['_id']}")


if __name__ == "__main__":
    main()
