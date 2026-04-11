"""
Patch all notes in DB with tags from tag_cache.json.

Flow:
  note.relatedVideoId → video._id → video.youtubeId
  youtubeId → slug (from json-res filenames)
  slug → tags (from tag_cache.json)
  PATCH /api/notes/:id  { tags: [...] }
"""

import json, os, re, requests, time

BASE       = 'https://tlt-m17y.onrender.com/api'
JSON_DIR   = '/Users/nishb369/Desktop/FRIDAY/tlt/json-res'
CACHE_FILE = '/Users/nishb369/Desktop/FRIDAY/tlt/processed/tag_cache.json'

# ── 1. Load tag cache ────────────────────────────────────────────────────────
with open(CACHE_FILE) as f:
    tag_cache = json.load(f)          # slug → [tags]

# ── 2. Build youtubeId → slug from json-res filenames ───────────────────────
ytid_to_slug = {}
for fname in os.listdir(JSON_DIR):
    m = re.match(r'^(.+)_([A-Za-z0-9_-]{11})\.json$', fname)
    if m:
        slug, ytid = m.group(1), m.group(2)
        ytid_to_slug[ytid] = slug

# ── 3. Fetch all videos → build _id → youtubeId map ────────────────────────
videos = requests.get(f'{BASE}/videos?limit=200').json()['data']['data']
dbid_to_ytid = {v['_id']: v['youtubeId'] for v in videos}

# ── 4. Fetch all notes ───────────────────────────────────────────────────────
notes = requests.get(f'{BASE}/notes?limit=200').json()['data']['data']
print(f"Found {len(notes)} notes, {len(videos)} videos\n")

# ── 5. Patch each note ───────────────────────────────────────────────────────
patched = 0
skipped = 0
errors  = []

for note in notes:
    note_id   = note['_id']
    vid_db_id = note.get('relatedVideoId')

    ytid = dbid_to_ytid.get(vid_db_id)
    if not ytid:
        print(f"  [SKIP] {note['title'][:50]} — no video match for relatedVideoId={vid_db_id}")
        skipped += 1
        continue

    slug = ytid_to_slug.get(ytid)
    if not slug:
        print(f"  [SKIP] {note['title'][:50]} — ytid {ytid} not in json-res")
        skipped += 1
        continue

    # Try exact slug match, then prefix match (truncated filenames)
    tags = tag_cache.get(slug)
    if not tags:
        # slug may be truncated in notes dir (os truncation) — try prefix
        for cache_slug, cache_tags in tag_cache.items():
            if cache_slug.startswith(slug[:50]):
                tags = cache_tags
                break

    if not tags:
        print(f"  [SKIP] {note['title'][:50]} — slug '{slug}' not in tag_cache")
        skipped += 1
        continue

    resp = requests.patch(f'{BASE}/notes/{note_id}', json={'tags': tags})
    if resp.status_code in (200, 204):
        print(f"  [OK]   {note['title'][:55]}")
        print(f"         tags: {tags}")
        patched += 1
    else:
        print(f"  [ERR]  {note['title'][:50]} — {resp.status_code} {resp.text[:100]}")
        errors.append(note['title'])

    time.sleep(0.05)   # gentle on Render free tier

print(f"\n{'='*60}")
print(f"Done — {patched} patched, {skipped} skipped, {len(errors)} errors")
if errors:
    print("Errors:")
    for e in errors:
        print(f"  - {e}")
