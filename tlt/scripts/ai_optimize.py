"""
ai_optimize.py
--------------
AI pass on TLT video metadata using Claude Haiku.
Reads from tlt/processed/optimized_metadata/ (DET pass output).
Fixes:
  1. Titles > 90 chars or > 2 pipes → rewrite to formula
  2. Descriptions with no content opening → prepend 2-3 sentence paragraph

Updates the same optimized_metadata files in-place.
Resume-safe: skips videos already marked ai_done=true.

Usage:
  python3 tlt/scripts/ai_optimize.py
  LIMIT=5 python3 tlt/scripts/ai_optimize.py
"""

import json, os, re, time
import anthropic
from pathlib import Path

# ── SEO Audit parser ──────────────────────────────────────────────────────────

AUDIT_FILE = Path('tlt/reports/video_seo_audit_2026-04-12.md')

def parse_seo_audit() -> list[dict]:
    """Parse the SEO audit markdown → list of {score, rank, issue, keyword_searched, video_fragment}."""
    if not AUDIT_FILE.exists():
        return []
    rows = []
    for line in AUDIT_FILE.read_text().splitlines():
        # Table data rows: | # | score | rank | ... | keyword | video |
        if not line.startswith('|') or line.startswith('| #') or line.startswith('|---'):
            continue
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p]  # remove empty from leading/trailing |
        if len(parts) < 11:
            continue
        try:
            score_raw = parts[1].strip('*')
            score = int(score_raw) if score_raw.isdigit() else 0
            rank  = parts[2]
            issue = parts[8]
            kw    = parts[9].strip('`')
            vid   = parts[10]
            rows.append({'score': score, 'rank': rank, 'issue': issue,
                         'keyword_searched': kw, 'video_fragment': vid})
        except (IndexError, ValueError):
            continue
    return rows

def _slug_words(slug: str) -> set[str]:
    """Return lowercase word set from a slug (strip trailing video_id)."""
    # slug may include _VIDEO_ID at end — video_id is 11 chars alphanumeric+dash+underscore
    clean = re.sub(r'_[A-Za-z0-9_-]{11}$', '', slug)
    return set(re.split(r'[_\s]+', clean.lower()))

def match_audit(slug: str, audit_rows: list[dict]) -> dict | None:
    """Find best-matching audit row for a given slug using word-overlap scoring."""
    slug_w = _slug_words(slug)
    best, best_score = None, 0.0
    for row in audit_rows:
        frag_w = set(re.split(r'[\s·\-_]+', row['video_fragment'].lower()))
        kw_w   = set(re.split(r'[\s]+', row['keyword_searched'].lower()))
        combined = frag_w | kw_w
        if not combined:
            continue
        overlap = len(slug_w & combined) / len(slug_w | combined)
        if overlap > best_score:
            best_score = overlap
            best = row
    return best if best_score > 0.25 else None

# Load .env manually
_env_file = Path(__file__).parent.parent.parent / '.env'
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

OPT_DIR      = Path('tlt/processed/optimized_metadata')
JSON_DIR     = Path('tlt/json-res')
OVERVIEW_DIR = Path('tlt/processed/overview')
API_KEY      = os.environ.get('ANTHROPIC_API_KEY', '')
client    = anthropic.Anthropic(api_key=API_KEY)

TITLE_SYSTEM = """You are a YouTube SEO specialist for an English literature education channel (@TheLiteratureTalks).
The channel explains English literature texts in Hindi for Indian university students (BA/MA English Honours, Class 6-12).

Rewrite the given YouTube video title to follow this formula:
[Work/Text Title] by [Author] | [Content Type] in Hindi

Rules:
- 60–90 characters total
- Maximum 2 pipe separators |
- Title Case (not ALL CAPS)
- Always include author name if applicable
- Include ONE of: explanation, summary, line by line explanation, analysis, back exercise
- End with "in Hindi" if the video is in Hindi
- If it's a multi-part series, keep the Part N at the end: "... in Hindi | Part 1"
- If curriculum-specific (Class 6, BA Eng Hons), add as last segment after "in Hindi"

Return ONLY the rewritten title. No explanation, no quotes."""

DESC_SYSTEM = """You are an SEO-focused YouTube description writer for @TheLiteratureTalks — an English literature education channel explaining texts in Hindi for Indian students (BA/MA English Honours, CBSE/NCERT Class 6–12).

TASK: Write ONE tight paragraph (3 sentences max, strictly 80–120 words) to open a YouTube description.

This paragraph must:
- Hook with a story, tension, or surprising fact about the text or author
- Naturally embed keywords: work name, author full name, 1–2 themes, curriculum level (BA Eng Hons / Class 6 / DU SOL etc.)
- Sound like a knowledgeable friend, not a textbook or Wikipedia article

HARD RULES — violating any of these will make your output unusable:
- EXACTLY 3 sentences or fewer
- STRICTLY under 120 words — count before you output
- Do NOT start with "This video", "In this video", "This is", "This story", "This chapter"
- Do NOT reproduce any content from the context provided — use it only to understand the text, then write fresh
- Do NOT write a biography — focus on the TEXT and why it matters to students
- Do NOT use markdown, bullets, or formatting

GOOD EXAMPLE (for Sultana's Dream by Begum Rokeya):
Written in 1905 by Begum Rokeya Sakhawat Hossain — a pioneering Bengali Muslim feminist — Sultana's Dream imagines a world where women rule and men are confined indoors, flipping the logic of purdah on its head with razor-sharp wit. Part utopia, part social satire, this short story is a landmark in feminist fiction and a key text in the BA English Honours syllabus across DU and SOL. Rokeya's Ladyland, powered by solar energy and free of crime, feels startlingly prescient over a century later.

WHAT TO AVOID:
- A biography of the author (birth dates, awards, career timeline)
- Starting with "This is", "This video explains", "This story is about"
- Copying or listing vocabulary words, difficult words, or exercise content
- More than 3 sentences or more than 120 words

Return ONLY the paragraph. No title, no label, no extra text."""


def find_overview(slug: str) -> str:
    """Return first 3000 chars of overview file for a slug, or empty string."""
    exact = OVERVIEW_DIR / f'{slug}.md'
    if exact.exists():
        return exact.read_text()[:3000]
    for f in OVERVIEW_DIR.iterdir():
        stem = f.stem
        if slug.startswith(stem) or stem.startswith(slug[:50]):
            return f.read_text()[:3000]
    return ''

WEAK_OPENERS = ('this is', 'this video', 'in this video', 'this chapter', 'this story', 'this poem', 'here is', 'free notes', 'notes link')

# Signals that the first paragraph is a bio dump, not a content opening
BIO_SIGNALS = ('was born', 'was an indian writer', '(10 october', '(born ', 'died ', 'is an indian', 'is a poet', 'is a writer', 'rasipuram', 'iyer narayanaswami')

def desc_is_weak(desc: str) -> bool:
    """True if description has no real content — just keyword lines, short/canned opener, or author bio dump."""
    first_line = next((l.strip() for l in desc.splitlines() if l.strip()), '')
    if len(first_line) < 80 or first_line.startswith('http') or first_line.startswith('_'):
        return True
    if first_line.lower().startswith(WEAK_OPENERS):
        return True
    # Bio dump: first paragraph reads like a Wikipedia author bio
    first_para = desc.split('\n\n')[0].lower()
    if any(sig in first_para for sig in BIO_SIGNALS):
        return True
    return False

def needs_title_fix(title: str) -> bool:
    return len(title) > 90 or title.count('|') > 2

def needs_desc_fix(desc: str) -> bool:
    return desc_is_weak(desc)

def rewrite_title(title: str, keyword_searched: str = '') -> str:
    user_content = f'Rewrite this title:\n{title}'
    if keyword_searched:
        user_content += f'\n\nTarget keyword (must appear naturally in the rewritten title):\n{keyword_searched}'
    resp = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=150,
        system=TITLE_SYSTEM,
        messages=[{'role': 'user', 'content': user_content}]
    )
    return resp.content[0].text.strip().strip('"\'')

def generate_desc_opening(title: str, slug: str, keyword_searched: str = '', issue: str = '') -> str:
    user_msg = f"Video title: {title}"
    if keyword_searched:
        user_msg += f'\nTarget search keyword: {keyword_searched}'
    if issue:
        user_msg += f'\nSEO issue to address: {issue}'
    user_msg += '\n\nWrite the opening paragraph now.'
    resp = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=250,
        system=DESC_SYSTEM,
        messages=[{'role': 'user', 'content': user_msg}]
    )
    return resp.content[0].text.strip()

WEAK_FIRST_LINE_RE = re.compile(
    r'^(this is|this video|in this video|this chapter|this story|this poem|here is|free notes|notes link)[^\n]*\n?',
    re.IGNORECASE
)

VOCAB_BLOCK_RE = re.compile(
    r'(?:Difficult Words|Vocabulary|Word Meanings?|Hard Words)[^\n]*\n[\s\S]*?(?=\n[A-Z"\'\u0900-\u097F]|\Z)',
    re.IGNORECASE
)

def strip_weak_content(desc: str) -> str:
    """Remove weak opening line, bio dumps, and vocabulary/difficult words blocks from desc."""
    desc = WEAK_FIRST_LINE_RE.sub('', desc)
    desc = VOCAB_BLOCK_RE.sub('', desc)
    desc = re.sub(r'(?:\d+\.\s+\S.+\n?){5,}', '', desc)
    # If desc opens with a bio dump, strip everything up to the keyword variation block
    first_para = desc.split('\n\n')[0].lower() if desc else ''
    if any(sig in first_para for sig in BIO_SIGNALS):
        # Find where keyword variation lines start (repeated title phrases)
        lines = desc.splitlines()
        keyword_start = None
        for i, line in enumerate(lines):
            # Keyword lines are short, repetitive title variations
            stripped = line.strip()
            if stripped and len(stripped) < 80 and not any(c in stripped for c in '.,;!?()'):
                # Check if next few lines are similar (keyword block pattern)
                next_lines = [l.strip() for l in lines[i+1:i+4] if l.strip()]
                if sum(1 for nl in next_lines if len(nl) < 80) >= 2:
                    keyword_start = i
                    break
        if keyword_start is not None:
            desc = '\n'.join(lines[keyword_start:])
        else:
            desc = ''  # all bio, nothing useful
    return re.sub(r'\n{3,}', '\n\n', desc).strip()

def prepend_opening(desc: str, opening: str) -> str:
    cleaned = strip_weak_content(desc)
    return opening + '\n\n' + cleaned

def main():
    files = sorted(OPT_DIR.glob('*.json'))
    limit = int(os.environ.get('LIMIT', 0))

    audit_rows = parse_seo_audit()
    print(f"Loaded {len(audit_rows)} SEO audit entries\n")

    processed = 0
    skipped   = 0
    failed    = []

    for f in files:
        d = json.loads(f.read_text())

        if d.get('ai_done'):
            skipped += 1
            continue

        title   = d['title']
        desc    = d['description']
        slug    = d.get('slug', f.stem)
        fix_t   = needs_title_fix(title)
        fix_d   = needs_desc_fix(desc) or bool(d.get('needs_ai_desc'))

        if not fix_t and not fix_d:
            d['ai_done'] = True
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            skipped += 1
            continue

        if limit and processed >= limit:
            print(f'\nLimit of {limit} reached — stopping.')
            break

        # Match to SEO audit
        audit = match_audit(slug, audit_rows)
        keyword_searched = audit['keyword_searched'] if audit else ''
        issue            = audit['issue'] if audit else ''
        seo_score        = audit['score'] if audit else '?'
        tlt_rank         = audit['rank'] if audit else '?'

        flags = []
        if fix_t: flags.append('TITLE')
        if fix_d: flags.append('DESC')
        kw_info = f' [kw: {keyword_searched[:50]}]' if keyword_searched else ''
        print(f"[AI] {title[:55]:55s}  → {', '.join(flags)}{kw_info}")

        try:
            if fix_t:
                new_title = rewrite_title(title, keyword_searched)
                print(f"     TITLE: {new_title}")
                d['title'] = new_title
                d['changes']['title'] = True

            if fix_d:
                opening = generate_desc_opening(d['title'], slug, keyword_searched, issue)
                d['description'] = prepend_opening(desc, opening)
                d['changes']['description'] = True

            # Store audit match for traceability
            if audit:
                d['seo_audit'] = {'score': seo_score, 'rank': tlt_rank,
                                  'keyword_searched': keyword_searched, 'issue': issue}

            d['ai_done'] = True
            d.pop('needs_ai_desc', None)
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            processed += 1

        except Exception as e:
            print(f"     ERR: {e}")
            failed.append({'title': title, 'reason': str(e)})

        time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"Done — {processed} updated, {skipped} skipped, {len(failed)} failed")
    if failed:
        print('\nFailed:')
        for ff in failed:
            print(f"  {ff['title'][:60]} — {ff['reason']}")

if __name__ == '__main__':
    main()
