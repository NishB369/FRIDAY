"""
yt_push.py
----------
Pushes optimized metadata (title, description, tags) to YouTube via Data API v3.

First run: opens browser for OAuth2 consent → saves tlt/.yt_token.json
Subsequent runs: reuses saved token automatically.

Usage:
  # Test one video (by video_id):
  python3 tlt/scripts/yt_push.py --video 8eOCn5Aoy2k

  # Push all videos (skips already-pushed unless --force):
  python3 tlt/scripts/yt_push.py --all

  # Force re-push even if already pushed:
  python3 tlt/scripts/yt_push.py --all --force

Requirements:
  - tlt/client_secrets.json  (OAuth2 Desktop app credentials from Google Cloud Console)
  - tlt/processed/optimized_metadata/*.json  (output of the optimization pipeline)
"""

import json, sys, argparse
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Paths ──────────────────────────────────────────────────────────────────────
OPT_DIR        = Path('tlt/processed/optimized_metadata')
SECRETS_FILE   = Path('tlt/client_secrets.json')
TOKEN_FILE     = Path('tlt/.yt_token.json')

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# YouTube category IDs — 27 = Education
CATEGORY_ID = '27'


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_youtube_client():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRETS_FILE.exists():
                print(f'ERROR: {SECRETS_FILE} not found.')
                print('Download it from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON')
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        print(f'Token saved to {TOKEN_FILE}')

    return build('youtube', 'v3', credentials=creds)


# ── Push ───────────────────────────────────────────────────────────────────────

def sanitize_tags(tags: list) -> list:
    """Strip invalid characters; drop tags over 30 chars; enforce 500 char total."""
    clean = []
    total = 0
    for t in tags:
        t = t.strip().replace('<', '').replace('>', '').replace('&', 'and')
        if not t or len(t) > 30:
            continue
        if total + len(t) > 500:
            break
        clean.append(t)
        total += len(t)
    return clean


def push_video(youtube, d: dict) -> bool:
    """Push title, description, tags for one video. Returns True on success."""
    video_id = d['video_id']
    title    = d['title']
    desc     = d['description']
    tags     = sanitize_tags(d.get('tags', []))

    # Fetch current snippet to get required fields (categoryId, defaultLanguage etc.)
    current = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()

    if not current.get('items'):
        print(f'  SKIP — video {video_id} not found on channel (private/deleted?)')
        return False

    snippet = current['items'][0]['snippet']

    # Patch only our fields — preserve everything else
    snippet['title']       = title
    snippet['description'] = desc
    snippet['tags']        = tags
    snippet['categoryId']  = snippet.get('categoryId', CATEGORY_ID)

    youtube.videos().update(
        part='snippet',
        body={'id': video_id, 'snippet': snippet}
    ).execute()

    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--video', help='Push a single video by video_id')
    group.add_argument('--all',   action='store_true', help='Push all videos')
    parser.add_argument('--force', action='store_true', help='Re-push even if already pushed')
    args = parser.parse_args()

    youtube = get_youtube_client()
    print('Authenticated OK\n')

    if args.video:
        # Find the file for this video_id
        matches = [f for f in OPT_DIR.glob('*.json')
                   if args.video in f.stem]
        if not matches:
            # Try by reading video_id field
            matches = [f for f in OPT_DIR.glob('*.json')
                       if json.loads(f.read_text()).get('video_id') == args.video]
        if not matches:
            print(f'ERROR: No optimized_metadata file found for video_id {args.video}')
            sys.exit(1)
        files = matches[:1]
    else:
        files = sorted(OPT_DIR.glob('*.json'))

    pushed = 0
    skipped = 0
    failed = []

    for f in files:
        d = json.loads(f.read_text())
        video_id = d['video_id']
        title    = d['title'][:55]

        if not args.force and d.get('yt_pushed'):
            print(f'SKIP (already pushed) — {title}')
            skipped += 1
            continue

        print(f'PUSH {video_id} — {title}...')
        try:
            ok = push_video(youtube, d)
            if ok:
                d['yt_pushed'] = True
                f.write_text(json.dumps(d, ensure_ascii=False, indent=2))
                print(f'  OK')
                pushed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f'  ERR: {e}')
            failed.append({'video_id': video_id, 'title': title, 'reason': str(e)})

    print(f'\n{"="*50}')
    print(f'Done — {pushed} pushed, {skipped} skipped, {len(failed)} failed')
    if failed:
        print('\nFailed:')
        for ff in failed:
            print(f"  [{ff['video_id']}] {ff['title']} — {ff['reason']}")


if __name__ == '__main__':
    main()
