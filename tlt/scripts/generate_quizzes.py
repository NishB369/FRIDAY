"""
Generate quizzes for all TLT videos using Claude Haiku API.
Reads overview files → generates 6-8 MCQ/T-F questions → pushes to DB.

Resume-safe: skips videos that already have a quiz in DB.
Output: tlt/processed/quiz/ (local backup of generated JSON)

Usage:
  python3 tlt/scripts/generate_quizzes.py
"""

import json, os, re, time, requests, anthropic
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY      = os.environ.get('ANTHROPIC_API_KEY', '')
BASE         = 'https://tlt-m17y.onrender.com/api'
NOVEL_ID     = '69da827a5196cf62d88a3980'
JSON_DIR     = Path('/Users/nishb369/Desktop/FRIDAY/tlt/json-res')
OVERVIEW_DIR = Path('/Users/nishb369/Desktop/FRIDAY/tlt/processed/overview')
QUIZ_DIR     = Path('/Users/nishb369/Desktop/FRIDAY/tlt/processed/quiz')
QUIZ_DIR.mkdir(parents=True, exist_ok=True)

client = anthropic.Anthropic(api_key=API_KEY)

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
    {
      "question": "...",
      "type": "mcq",
      "options": ["A", "B", "C", "D"],
      "correctAnswer": "A",
      "explanation": "...",
      "points": 1
    },
    {
      "question": "...",
      "type": "true-false",
      "options": ["True", "False"],
      "correctAnswer": "True",
      "explanation": "...",
      "points": 1
    }
  ]
}"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def build_slug_map():
    """youtubeId → slug, slug → youtubeId"""
    ytid_to_slug, slug_to_ytid = {}, {}
    for f in JSON_DIR.iterdir():
        m = re.match(r'^(.+)_([A-Za-z0-9_-]{11})\.json$', f.name)
        if m:
            slug, ytid = m.group(1), m.group(2)
            ytid_to_slug[ytid] = slug
            slug_to_ytid[slug] = ytid
    return ytid_to_slug, slug_to_ytid

def find_overview(slug):
    """Return overview content for a slug, handling truncated filenames."""
    # Exact match
    exact = OVERVIEW_DIR / f'{slug}.md'
    if exact.exists():
        return exact.read_text()
    # Prefix match (os may have truncated the filename)
    for f in OVERVIEW_DIR.iterdir():
        stem = f.stem
        if slug.startswith(stem) or stem.startswith(slug[:50]):
            return f.read_text()
    return None

def generate_quiz(title, overview_content):
    """Call Claude Haiku to generate quiz JSON."""
    user_msg = f"""Video title: {title}

Content:
{overview_content[:6000]}

Generate a quiz based on the above content."""

    resp = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_msg}]
    )
    raw = resp.content[0].text.strip()
    # Strip accidental markdown fences
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)

def push_quiz(payload):
    """POST quiz to backend."""
    r = requests.post(f'{BASE}/quizzes', json=payload)
    r.raise_for_status()
    return r.json()

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ytid_to_slug, _ = build_slug_map()

    # Fetch all videos
    videos = requests.get(f'{BASE}/videos?limit=200').json()['data']['data']
    print(f"Videos in DB: {len(videos)}")

    # Fetch existing quizzes → set of relatedVideoIds already done
    existing = requests.get(f'{BASE}/quizzes?limit=200').json()['data']['data']
    done_video_ids = {str(q.get('relatedVideoId')) for q in existing}
    print(f"Quizzes already in DB: {len(existing)}")
    print(f"To generate: {len(videos) - len(done_video_ids)}\n")

    pushed = 0
    skipped = 0
    failed = []

    limit = int(os.environ.get('LIMIT', 0))   # 0 = no limit

    for i, video in enumerate(videos, 1):
        if limit and (pushed + len(failed)) >= limit:
            print(f"\nLimit of {limit} reached — stopping.")
            break
        db_id  = video['_id']
        ytid   = video['youtubeId']
        title  = video['title']

        # Resume: skip already done
        if db_id in done_video_ids:
            print(f"[{i:02d}] SKIP (exists) {title[:55]}")
            skipped += 1
            continue

        slug = ytid_to_slug.get(ytid)
        if not slug:
            print(f"[{i:02d}] SKIP (no slug) {title[:55]}")
            skipped += 1
            continue

        # Check for local backup first (avoids re-generating on push failure)
        local_path = QUIZ_DIR / f'{slug}.json'
        if local_path.exists():
            print(f"[{i:02d}] LOCAL  {title[:55]}")
            quiz_data = json.loads(local_path.read_text())
        else:
            overview = find_overview(slug)
            if not overview:
                print(f"[{i:02d}] SKIP (no overview) {title[:55]}")
                skipped += 1
                continue

            print(f"[{i:02d}] GEN    {title[:55]}")
            try:
                quiz_data = generate_quiz(title, overview)
            except Exception as e:
                print(f"       ERR generating: {e}")
                failed.append({'title': title, 'reason': str(e)})
                time.sleep(2)
                continue

            # Save local backup
            local_path.write_text(json.dumps(quiz_data, indent=2))

        # Build DB payload
        questions = quiz_data.get('questions', [])
        payload = {
            'title': f'Quiz: {title}',
            'description': quiz_data.get('description', f'Test your understanding of {title}'),
            'novel': NOVEL_ID,
            'chapter': 'Uncategorized',
            'relatedVideoId': db_id,
            'timeLimit': 10,
            'passingScore': 70,
            'isPublished': False,
            'questions': questions,
        }

        try:
            push_quiz(payload)
            print(f"       OK  → {len(questions)} questions pushed")
            pushed += 1
        except Exception as e:
            print(f"       ERR pushing: {e}")
            failed.append({'title': title, 'reason': f'push: {e}'})

        time.sleep(0.5)   # gentle on Haiku rate limits + Render

    print(f"\n{'='*60}")
    print(f"Done — {pushed} pushed, {skipped} skipped, {len(failed)} failed")
    if failed:
        print("\nFailed:")
        for f in failed:
            print(f"  [{f['reason']}] {f['title'][:60]}")

if __name__ == '__main__':
    main()
