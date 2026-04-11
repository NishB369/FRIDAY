#!/bin/bash
# pipeline.sh — Automates: Excel → yt-data-extractor → Claude summary
# TRACKER.md is the source of truth — processed video IDs are read from it
# and it is updated automatically after each successful run.
#
# Usage:
#   ./pipeline.sh                  # Process all 77 videos (skips tracker-listed ones)
#   ./pipeline.sh --limit=5        # Process first 5 only
#   ./pipeline.sh --index=3        # Process only row 3 from the sheet
#   ./pipeline.sh --no-skip        # Re-process even if already in tracker

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
BASE="$(cd "$(dirname "$0")" && pwd)"
TLT="$BASE/tlt"
EXTRACTOR="$BASE/yt-data-extractor"
XLSX="$BASE/sheets-data/The_Literature_Talks_Videos.xlsx"
JSON_DIR="$TLT/json-res"
SUMMARIES_DIR="$TLT/processed/summaries"
TRACKER="$TLT/TRACKER.md"
EXTRACTOR_PORT=3000
EXTRACTOR_URL="http://localhost:$EXTRACTOR_PORT"

# ── Args ───────────────────────────────────────────────────────────────────
SKIP_EXISTING=true
LIMIT=0
VIDEO_INDEX=0

for arg in "$@"; do
  case $arg in
    --no-skip)  SKIP_EXISTING=false ;;
    --limit=*)  LIMIT="${arg#--limit=}" ;;
    --index=*)  VIDEO_INDEX="${arg#--index=}" ;;
  esac
done

# ── Colors ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

# ── 1. Check dependencies ──────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  The Literature Talks — Video Processing Pipeline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

for cmd in python3 curl claude npm; do
  if ! command -v "$cmd" &>/dev/null; then
    err "Required command not found: $cmd"; exit 1
  fi
done
ok "All dependencies found"

# ── 2. Read TRACKER.md — build done-set and next row number ───────────────
TRACKER_STATE=$(TRACKER_PATH="$TRACKER" python3 - <<'PYEOF'
import re, json, os

tracker = open(os.environ["TRACKER_PATH"]).read()

# Extract video IDs already in the File Reference table
# Rows look like: | N | `video_id` | ...
done_ids = re.findall(r'^\|\s*\d+\s*\|\s*`([A-Za-z0-9_-]{11})`', tracker, re.MULTILINE)

# Find max tracker row number across both tables
all_row_nums = re.findall(r'^\|\s*(\d+)\s*\|', tracker, re.MULTILINE)
max_row = max((int(n) for n in all_row_nums), default=0)

print(json.dumps({"done_ids": done_ids, "next_row": max_row + 1}))
PYEOF
)

DONE_IDS=$(echo "$TRACKER_STATE" | python3 -c "import json,sys; print('\n'.join(json.load(sys.stdin)['done_ids']))")
NEXT_ROW=$(echo "$TRACKER_STATE" | python3 -c "import json,sys; print(json.load(sys.stdin)['next_row'])")
DONE_COUNT=$(echo "$DONE_IDS" | grep -c . || true)

ok "Tracker loaded — $DONE_COUNT videos already done, next tracker row: $NEXT_ROW"

is_done() {
  echo "$DONE_IDS" | grep -qx "$1"
}

# ── 3. Start yt-data-extractor if not running ──────────────────────────────
SERVER_STARTED=false
SERVER_PID=""

check_server() {
  curl -sf --max-time 3 "$EXTRACTOR_URL" &>/dev/null
}

if check_server; then
  ok "yt-data-extractor already running on port $EXTRACTOR_PORT"
else
  echo "Starting yt-data-extractor server..."
  cd "$EXTRACTOR"
  npm run dev > /tmp/yt-extractor.log 2>&1 &
  SERVER_PID=$!
  SERVER_STARTED=true
  cd "$BASE"

  echo -n "Waiting for server to be ready"
  for i in $(seq 1 30); do
    sleep 2
    if check_server; then
      echo ""; ok "Server ready"; break
    fi
    echo -n "."
    if [ "$i" -eq 30 ]; then
      echo ""; err "Server failed to start after 60s — check /tmp/yt-extractor.log"; exit 1
    fi
  done
fi

cleanup() {
  if [ "$SERVER_STARTED" = true ] && [ -n "$SERVER_PID" ]; then
    echo ""; echo "Stopping yt-data-extractor (PID $SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# ── 4. Read URLs from Excel ────────────────────────────────────────────────
echo ""
echo "Reading video list from Excel..."

VIDEOS_JSON=$(XLSX_PATH="$XLSX" python3 - <<'PYEOF'
import json, re, os, sys
try:
    import openpyxl
except ImportError:
    sys.exit("ERROR: openpyxl not installed — run: pip3 install openpyxl")

wb = openpyxl.load_workbook(os.environ["XLSX_PATH"])
ws = wb.active
rows = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if len(row) < 3 or not row[2]: continue
    num, title, url = row[0], row[1], row[2]
    m = re.search(r'(?:v=|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})', str(url))
    video_id = m.group(1) if m else None
    slug = re.sub(r'[^a-z0-9\s]', '', str(title).lower())
    slug = re.sub(r'\s+', '_', slug.strip())[:60].rstrip('_')
    rows.append({"num": num, "title": str(title), "url": str(url), "video_id": video_id, "slug": slug})
print(json.dumps(rows))
PYEOF
)

TOTAL=$(echo "$VIDEOS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
ok "Found $TOTAL videos in sheet"

# ── 5. Tracker update helper ───────────────────────────────────────────────
update_tracker() {
  local tracker_row="$1" title="$2" video_id="$3" json_filename="$4" summary_filename="$5"

  TRACKER_PATH="$TRACKER" \
  TRACKER_ROW="$tracker_row" \
  V_TITLE="$title" \
  V_ID="$video_id" \
  JSON_FILE="$json_filename" \
  SUMMARY_FILE="$summary_filename" \
  python3 - <<'PYEOF'
import os, re
from datetime import date

path      = os.environ["TRACKER_PATH"]
row_num   = os.environ["TRACKER_ROW"]
title     = os.environ["V_TITLE"]
video_id  = os.environ["V_ID"]
json_f    = os.environ["JSON_FILE"]
summary_f = os.environ["SUMMARY_FILE"]
today     = date.today().strftime("%Y-%m-%d")

content = open(path).read()

# 1. Update Last Updated line
content = re.sub(
    r'\*\*Last Updated:\*\*[^\n]*',
    f'**Last Updated:** {today} (automated pipeline)',
    content
)

# 2. Append row to Video Tracker table
# Find the last | row in the Video Tracker section (between ## Video Tracker and next ---)
def insert_after_last_table_row(text, section_heading, new_row):
    lines = text.split('\n')
    in_section = False
    last_row_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == section_heading:
            in_section = True
        if in_section and line.startswith('| ') and not line.startswith('| #') and not line.startswith('|--') and not line.startswith('| -'):
            # Check it's a data row (not header or separator)
            if re.match(r'^\|\s*\d+\s*\|', line):
                last_row_idx = i
        # Stop at next --- after we've found the section
        if in_section and last_row_idx >= 0 and line.strip() == '---':
            break
    if last_row_idx >= 0:
        lines.insert(last_row_idx + 1, new_row)
    return '\n'.join(lines)

vt_row = f'| {row_num} | {title} | {json_f} | ✅ | ✅ | ✅ | ✅ | ❌ |'
content = insert_after_last_table_row(content, '## Video Tracker', vt_row)

fr_row = f'| {row_num} | `{video_id}` | `json-res/{json_f}` | *(in json-res file)* | `processed/summaries/{summary_f}` | — |'
content = insert_after_last_table_row(content, '## File Reference', fr_row)

open(path, 'w').write(content)
print(f"Tracker updated — row {row_num} added")
PYEOF
}

# ── 6. Process each video ──────────────────────────────────────────────────
echo ""
PROCESSED=0; SKIPPED=0; FAILED=0

process_video() {
  local num="$1" title="$2" url="$3" video_id="$4" slug="$5"
  local json_filename="${slug}_${video_id}.json"
  local summary_filename="${slug}_${video_id}_summary.md"
  local json_file="$JSON_DIR/$json_filename"
  local summary_file="$SUMMARIES_DIR/$summary_filename"

  echo ""
  echo "────────────────────────────────────────────────────"
  echo "[$num] $title"

  # Skip if already in tracker
  if [ "$SKIP_EXISTING" = true ] && is_done "$video_id"; then
    warn "Already in tracker — skipping (--no-skip to force)"
    SKIPPED=$((SKIPPED + 1)); return
  fi

  # Step A: Fetch JSON (reuse if exists)
  if [ -f "$json_file" ] && [ "$SKIP_EXISTING" = true ]; then
    ok "JSON already exists"
  else
    echo "  Fetching metadata + transcript..."
    HTTP_CODE=$(curl -s -o "$json_file" -w "%{http_code}" \
      "$EXTRACTOR_URL/api/extract" \
      -X POST -H "Content-Type: application/json" \
      -d "{\"url\":\"$url\"}")

    if [ "$HTTP_CODE" != "200" ]; then
      err "Extract API returned HTTP $HTTP_CODE"
      rm -f "$json_file"
      FAILED=$((FAILED + 1)); return
    fi

    if ! python3 -c "import json; d=json.load(open('$json_file')); assert 'video_id' in d" 2>/dev/null; then
      err "Invalid/unexpected JSON response"
      FAILED=$((FAILED + 1)); return
    fi
    ok "JSON saved: $json_filename"
  fi

  # Step B: Generate summary with Claude CLI
  echo "  Generating summary with Claude..."
  local json_rel="json-res/$json_filename"
  local summary_rel="processed/summaries/$summary_filename"

  if (cd "$TLT" && claude -p \
    "Read the file $json_rel and generate a comprehensive educational summary following the instructions in CLAUDE.md. Write the output to $summary_rel." \
    --allowedTools "Read,Write" \
    --no-session-persistence \
    --output-format text < /dev/null 2>/tmp/claude_error.log); then
    ok "Summary saved: $summary_filename"

    # Step C: Update TRACKER.md
    update_tracker "$NEXT_ROW" "$title" "$video_id" "$json_filename" "$summary_filename"
    NEXT_ROW=$((NEXT_ROW + 1))
    # Add to done set so --index runs don't double-count
    DONE_IDS="$DONE_IDS"$'\n'"$video_id"

    PROCESSED=$((PROCESSED + 1))
  else
    err "Claude failed — see /tmp/claude_error.log"
    cat /tmp/claude_error.log 2>/dev/null || true
    FAILED=$((FAILED + 1))
  fi
}

# Iterate over videos
COUNT=0
while IFS= read -r VIDEO; do
  NUM=$(echo "$VIDEO"   | python3 -c "import json,sys; print(json.load(sys.stdin)['num'])")
  TITLE=$(echo "$VIDEO" | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])")
  URL=$(echo "$VIDEO"   | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")
  VID=$(echo "$VIDEO"   | python3 -c "import json,sys; print(json.load(sys.stdin)['video_id'] or '')")
  SLUG=$(echo "$VIDEO"  | python3 -c "import json,sys; print(json.load(sys.stdin)['slug'])")

  if [ "$VIDEO_INDEX" -gt 0 ] && [ "$NUM" != "$VIDEO_INDEX" ]; then continue; fi

  if [ -z "$VID" ]; then
    warn "[$NUM] Could not extract video ID — skipping"
    FAILED=$((FAILED + 1)); continue
  fi

  process_video "$NUM" "$TITLE" "$URL" "$VID" "$SLUG"
  COUNT=$((COUNT + 1))

  if [ "$LIMIT" -gt 0 ] && [ "$COUNT" -ge "$LIMIT" ]; then
    warn "Reached --limit=$LIMIT"; break
  fi

done < <(echo "$VIDEOS_JSON" | python3 -c "
import json, sys
for v in json.load(sys.stdin):
    print(json.dumps(v))
")

# ── 7. Final report ────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  Processed : %d\n" "$PROCESSED"
printf "  Skipped   : %d (already in tracker)\n" "$SKIPPED"
printf "  Failed    : %d\n" "$FAILED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
