"""
det_optimize.py
---------------
Deterministic metadata fixes for all TLT videos. Zero API cost.

Fixes applied:
1. Add brand tag "the literature talks" if missing
2. Remove generic junk tags
3. Fix ALL CAPS titles → Title Case
4. Strip emoji from titles
5. Append standard CTA block to descriptions missing it

Output: tlt/processed/optimized_metadata/<slug>.json
Each file stores: video_id, slug, title, description, tags (optimized)
Nothing is pushed to YouTube — review first, then run the updater.

Usage:
  python3 tlt/scripts/det_optimize.py
"""

import json, re, unicodedata
from pathlib import Path

JSON_DIR  = Path('tlt/json-res')
OUT_DIR   = Path('tlt/processed/optimized_metadata')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────

BRAND_TAG = 'the literature talks'

JUNK_TAGS = {
    'education', 'enjoy', 'knowledge', 'trending video', 'trending',
    'english', 'english for everyone', 'english fro everyone',
    'english trending videos', 'arts', 'schoolwork', 'homework',
    'tarea', 'audiobook', 'college', 'high school', 'genre', 'translation',
    'world literature', 'literary', 'english-language',
    'feel your wings', 'booktube',
}

CTA_BLOCK = "https://theliteraturetalks.com"

# Links/text to strip from descriptions
STRIP_PATTERNS = [
    # Social CTAs
    r'JOIN US ON TELEGRAM\s*[-–:]?\s*',
    r'Join us on Telegram\s*[-–:]?\s*',
    r'FOLLOW ME ON INSTAGRAM\s*[-–:]?\s*',
    r'Follow me on Instagram.*?(?=\n|$)',
    r'Follow me on Linkedin.*?(?=\n|$)',
    r'Follow me on Twitter.*?(?=\n|$)',
    r'Linkedin\s*[-–].*?(?=\n|$)',
    r'Twitter\s*[-–].*?(?=\n|$)',
    # Subscribe prompts
    r'Subscribe to our Yout.*?(?=\n|$)',
    r'subscribe to our channel.*?(?=\n|$)',
    r"(?:👍\s*)?Don'?t Forget to Like.*?(?=\n|$)",
    r'Like 👍 and Subscribe.*?(?=\n|$)',
    r'Join us in this exploration.*?(?=\n|$)',
    r'If you find this video helpful.*?(?=\n|$)',
    # Notes shop / sales
    r'SALE!\s*SALE!\s*SALE!\s*',
    r'\*?PURCHASE ANY NOTES.*?(?=\n|$)',
    r'NEW NOTES FOR THE.*?(?=\n|$)',
    r'Whole semester notes.*?(?=\n|$)',
    r'Important Questions.*?(?=\n|$)',
    # Notes list items — with or without URL (URL already stripped by link patterns)
    r'.+\(BA ENG HONS SEM \d+\).*?(?=\n|$)',
    r'.+\(BA ENG HONS SEM \d+ YR\).*?(?=\n|$)',
    # Orphaned punctuation lines left after URL strip
    r'^\s*[-:]\s*$',
    r'^\s*:\s*$',
    # Bio
    r"Hi,\s*I'?m Aanchal Bhatia[\s\S]*?(?=\n\n|\Z)",
    # Old checklist lines
    r'CHECK OUT THE LINK BELOW.*?(?=\n|$)',
    r'TO READ SOME AMAZING REVIEWS.*?(?=\n|$)',
    r'BUY ENGLISH HONS HANDWRITTEN NOTES.*?(?=\n|$)',
    r'FOR EXAMS\s*[-–]?\s*(?=\n|$)',
    # Links
    r'https?://t\.me/\S+',
    r'https?://(?:www\.)?instagram\.com/\S+',
    r'https?://twitter\.com/\S+',
    r'https?://(?:www\.)?linkedin\.com/\S+',
    r'https?://(?:www\.)?youtube\.com/\S*',
    r'https?://(?:www\.)?ratingshating\.com\S*',
    r'https?://shop\.handwrittennotes\.in\S*',
    r'https?://drive\.google\.com/\S+',
    # Weak opener lines
    r'^(?:this is|this video|in this video|this chapter|this story|this poem|here is|free notes)[^\n]*\n?',
    # Numbered vocabulary / difficult words lists
    r'(?:Difficult Words|Vocabulary|Word Meanings?|Hard Words)[^\n]*\n',
    r'(?:^|\n)\d{1,2}\.\s+[^\n]+(?:\n(?!\d{1,2}\.\s)[^\n]*)*',  # numbered items incl. wrapped lines
    # Separator lines
    r'_{10,}',
]

EMOJI_RE = re.compile(
    "[\U00010000-\U0010ffff"   # surrogates / emoji
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F9FF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]+",
    flags=re.UNICODE
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_emoji(text: str) -> str:
    return EMOJI_RE.sub('', text).strip()

def fix_caps(title: str) -> str:
    """Convert ALL CAPS title to Title Case, preserve known acronyms."""
    if title == title.upper() and len(title) > 10:
        return title.title()
    return title

def fix_title(title: str) -> str:
    title = strip_emoji(title)
    title = fix_caps(title)
    title = title.strip(' "\'')
    return title

def fix_tags(tags: list) -> list:
    cleaned = [t for t in tags if t.lower() not in JUNK_TAGS]
    tag_lower = [t.lower() for t in cleaned]
    if BRAND_TAG not in tag_lower:
        cleaned.append(BRAND_TAG)
    return cleaned

def clean_description(desc: str) -> str:
    """Strip all old social links, CTAs, and separator lines."""
    for pattern in STRIP_PATTERNS:
        desc = re.sub(pattern, '', desc, flags=re.IGNORECASE | re.MULTILINE)
    # Collapse 3+ blank lines into 2
    desc = re.sub(r'\n{3,}', '\n\n', desc)
    return desc.strip()

def fix_description(desc: str) -> str:
    cleaned = clean_description(desc)
    # Remove any trailing blank lines left after stripping
    cleaned = re.sub(r'\n{2,}$', '', cleaned).strip()
    return cleaned + '\n______________________________________________________________________\n' + CTA_BLOCK

def slug_from_filename(path: Path) -> str:
    # filename: slug_YTID.json → strip last _YTID part
    stem = path.stem
    m = re.match(r'^(.+)_([A-Za-z0-9_-]{11})$', stem)
    return m.group(1) if m else stem

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    files = sorted(JSON_DIR.glob('*.json'))
    print(f"Processing {len(files)} videos...\n")

    stats = {'title_fixed': 0, 'tags_fixed': 0, 'desc_fixed': 0, 'total': 0}

    for f in files:
        d = json.loads(f.read_text())
        slug = slug_from_filename(f)
        video_id = d.get('video_id', '')

        orig_title = d.get('title', '')
        orig_tags  = d.get('tags', [])
        orig_desc  = d.get('description', '')

        new_title = fix_title(orig_title)
        new_tags  = fix_tags(orig_tags)
        new_desc  = fix_description(orig_desc)

        title_changed = new_title != orig_title
        tags_changed  = sorted(new_tags) != sorted(orig_tags)
        desc_changed  = new_desc.strip() != orig_desc.strip()

        if title_changed: stats['title_fixed'] += 1
        if tags_changed:  stats['tags_fixed']  += 1
        if desc_changed:  stats['desc_fixed']  += 1
        stats['total'] += 1

        out = {
            'video_id':    video_id,
            'slug':        slug,
            'title':       new_title,
            'description': new_desc,
            'tags':        new_tags,
            'changes': {
                'title':       title_changed,
                'tags':        tags_changed,
                'description': desc_changed,
            }
        }

        # Match json-res naming: {slug}_{video_id}.json
        (OUT_DIR / f'{slug}_{video_id}.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))

        flags = []
        if title_changed: flags.append('TITLE')
        if tags_changed:  flags.append('TAGS')
        if desc_changed:  flags.append('DESC')
        status = ', '.join(flags) if flags else 'no change'
        print(f"[{'FIX' if flags else ' OK'}] {orig_title[:60]:60s}  → {status}")

    print(f"\n{'='*60}")
    print(f"Done — {stats['total']} videos processed")
    print(f"  Titles fixed  : {stats['title_fixed']}")
    print(f"  Tags fixed    : {stats['tags_fixed']}")
    print(f"  Descs fixed   : {stats['desc_fixed']}")
    print(f"\nOutput: {OUT_DIR}/")

if __name__ == '__main__':
    main()
