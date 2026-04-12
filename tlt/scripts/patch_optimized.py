"""
patch_optimized.py
------------------
Post-processes all tlt/processed/optimized_metadata files in-place.

Fixes:
1. Strip remaining junk — Telegram CTA, GET PDF OF ANSWER, assignment blocks,
   SOL/DU headers, B.A.(Hons.) academic headers, Code: lines,
   Assignment-based evaluation lines, PAID NOTES blocks, assignment questions
2. Junk hashtag lines (#WORD_WORD, #ALLCAPS single tokens) → remove line
3. Keyword lines starting with # → strip the # character, keep line
4. Normalize newlines: 3+ → 2, trailing whitespace per line
5. Replace bare URL CTA with styled CTA block
6. Add CTA to files missing it
7. Flag files with thin body content (< 200 chars after clean) → needs_ai_desc = True

Usage:
  python3 tlt/scripts/patch_optimized.py
"""

import json, re
from pathlib import Path

OPT_DIR = Path('tlt/processed/optimized_metadata')

CTA = (
    '______________________________________________________________________\n'
    'Want notes, summaries & quizzes for this video? '
    'Everything\'s free at theliteraturetalks.com'
)

# Threshold: body content chars after stripping CTA + AI opening
SHORT_THRESH = 200

# ── Junk strip patterns (applied in order) ───────────────────────────────────
# Each is (pattern, flags). Applied with re.sub(pat, '', desc, flags=flags).

JUNK_PATTERNS = [
    # ── Assignment block: starts with "Connect with us on telegram" or
    #    "GET PDF OF ANSWER" and runs to separator or end ──
    (r'(?:Connect with us on telegram\s*[-–—]+|GET PDF OF ANSWER)'
     r'[^\n]*(?:\n(?!_{5,}|\Z)[^\n]*)*',
     re.IGNORECASE),

    # ── PAID NOTES block (header + any following lines until separator) ──
    (r'(?i)PAID NOTES[^\n]*(?:\n(?!_{5,})[^\n]*)*',
     0),

    # ── B.A. (Hons.) academic header block ──
    (r'B\.A\.\s*\(Hons\.\)[^\n]*(?:\n(?!_{5,}|\n\n)[^\n]*)*',
     re.IGNORECASE),

    # ── Standalone academic lines ──
    (r'(?m)^(?:Indian Writing in English|Code:\s*\d+|Assignment.based evaluation'
     r'|Semester\s+[IVX]+|Abe\s*\|\s*sol'
     r'|SOL\s+DU\s+BA\s+ENGLISH[^\n]*'
     r'|#SOLDU|#DUSOLASSIGNMENT|#ENGLISH\w+)[^\n]*$',
     re.IGNORECASE),

    # ── Assignment question lines (isolated interrogative lines) ──
    (r'(?m)^(?:Discuss|Comment on|How do|Write a note on|Explain|Analyse|Analyze)\s+.{15,}$',
     re.IGNORECASE),

    # ── Old separator lines (underscores 10+) — will be re-added via CTA ──
    (r'_{10,}',
     0),

    # ── Full CTA block including text (idempotent re-run) ──
    (r'Want notes, summaries & quizzes for this video\?[^\n]*',
     0),

    # ── Bare theliteraturetalks.com URL line (old CTA, will be replaced) ──
    (r'https?://theliteraturetalks\.com\S*',
     re.IGNORECASE),

    # ── Any remaining FREE NOTES / SALE lines ──
    (r'(?m)^(?:FREE NOTES|SALE!\s*SALE!\s*SALE!)[^\n]*$',
     re.IGNORECASE),

    # ── Self-promotional channel intro paragraphs ──
    (r'My channel publishes videos[\s\S]*?(?=\n\n|_{5,}|\Z)',
     re.IGNORECASE),

    # ── Full poem/text wrapped in asterisk delimiters ──
    (r'\*{5,}[\s\S]*?\*{5,}',
     0),

    # ── Cross-video notes mentions (other video's notes appearing in this desc) ──
    (r'Abhijana Shakuntalam Summary[^\n]*',
     re.IGNORECASE),
    (r'I Give You Back By Joy Harjo[^\n]*',
     re.IGNORECASE),

    # ── Inline hashtag strings (3+ hashtags on one line, with or without leading word) ──
    (r'(?m)^(?:\w+\s+)?(?:#\w+\s*){3,}.*$',
     0),

    # ── Emoji bullet / section headers (Welcome to our literary journey etc.) ──
    (r'[📚🔍📖🤔🔗✅🎬🔑💡]\s*(?:Welcome to our|In this video|Why Watch|Connect with)[^\n]*(?:\n(?![A-Z\u0900-\u097F]).+)*',
     re.IGNORECASE),
    # Strip any remaining emoji-prefixed bullet lines
    (r'(?m)^[📚🔍📖🤔🔗✅🎬🔑💡][^\n]*$',
     0),

    # ── UPSC / UGC NET / exam prep keyword blocks ──
    (r'(?m)^(?:upsc|ugc net\+jrf|pgt|nvs|kvs)[^\n]*$',
     re.IGNORECASE),
    (r'(?m)^IGNOU\s+MEG\s*\d+[^\n]*$',
     re.IGNORECASE),

    # ── YouTube description template phrases ──
    (r'(?m)^(?:Join us as we unravel|Gain a comprehensive understanding|Explore the poetic elements'
     r'|Enhance your knowledge and appreciation|Prepare effectively for exams'
     r'|Join us in this exploration)[^\n]*$',
     re.IGNORECASE),

    # ── Lone "Roots and wings class 6th" lines ──
    (r'(?m)^Roots and wings class 6th\s*$',
     re.IGNORECASE),

    # ── Orphaned single-word lines (leftover stripped hashtags) ──
    (r'(?m)^(?:Toni|Morrison|beloved|filmtheory|online_lecture)\s*$',
     re.IGNORECASE),

    # ── "Important Question" inline mentions (leftover from hashtag/note blocks) ──
    (r'(?m)^[^\n]*Important Question[^\n]*$',
     re.IGNORECASE),

    # ── Exam/curriculum number codes mid-desc ──
    (r'(?m)^\d+\s+[A-Z][^\n]{10,60}(?:Semester|MEG|paper)\s+\d+[^\n]*$',
     re.IGNORECASE),

    # ── Difficult words "Word - Definition" format (3+ consecutive lines) ──
    (r'(?:^[A-Za-z][A-Za-z\s]{1,25}\s*[-–]\s*.{4,}$\n?){3,}',
     re.MULTILINE),

    # ── Poem / verse body: 2+ stanza groups (3+ short lines each, blank-line separated)
    #    Detects actual poem text pasted into descriptions ──
    (r'(?:(?:[^\n]{1,70}\n){3,}\n){2,}',
     0),

    # ── Lone work-title / attribution lines immediately before separator or blank+separator
    # e.g. "Aunt Sue's Stories by Langston Hughes\n\n______" ──
    (r'(?m)^(?:[A-Z][A-Za-z\'\s]+(?:\sby\s[A-Z][A-Za-z\s]+)?)\s*$\n(?=\n_{5,})',
     0),
]

# ── Hashtag handling ──────────────────────────────────────────────────────────

# Junk hashtag: any line that is ONLY a #token (no spaces) — remove entirely
_JUNK_HASHTAG = re.compile(r'(?m)^#\S+\s*$')

# Keyword hashtag: starts with # followed by a letter then space (multi-word phrase) → strip #
_KW_HASHTAG = re.compile(r'(?m)^#([A-Za-z]\S[^\n]*\s\S)')

# Orphaned underscore-joined tokens (ex-hashtags with # stripped, e.g. Ma_English, Beloved_by_toni...)
_ORPHAN_UNDERSCORE = re.compile(r'(?m)^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\s*$')


def clean_hashtags(desc: str) -> str:
    """Remove junk hashtag-only lines; strip # from keyword lines; remove orphan underscore tokens."""
    desc = _JUNK_HASHTAG.sub('', desc)
    desc = _KW_HASHTAG.sub(r'\1', desc)
    desc = _ORPHAN_UNDERSCORE.sub('', desc)
    return desc


def apply_junk_patterns(desc: str) -> str:
    for pat, flags in JUNK_PATTERNS:
        desc = re.sub(pat, '', desc, flags=flags)
    return desc


def collapse_keyword_gaps(desc: str) -> str:
    """Collapse double blank lines between consecutive short keyword-style lines into single newlines."""
    # Keyword lines: < 80 chars, no sentence-ending structure
    # If two such lines are separated by a blank line, remove the blank
    return re.sub(
        r'(?m)(^.{5,79}$)\n\n(?=.{5,79}$)',
        r'\1\n',
        desc
    )

def normalize_newlines(desc: str) -> str:
    """Strip trailing whitespace per line; collapse 3+ blank lines to 2."""
    lines = [l.rstrip() for l in desc.splitlines()]
    desc = '\n'.join(lines)
    desc = re.sub(r'\n{3,}', '\n\n', desc)
    return desc.strip()


def total_content_length(desc: str) -> int:
    """Total chars of real content (excluding CTA block)."""
    content = re.split(r'_{5,}', desc)[0].strip()
    return len(content)

def body_length(desc: str) -> int:
    """Chars of body content: strip CTA block and first paragraph (AI opening or original)."""
    content = re.split(r'_{5,}', desc)[0].strip()
    paras = [p.strip() for p in content.split('\n\n') if p.strip()]
    rest = '\n\n'.join(paras[1:]) if len(paras) > 1 else ''
    return len(rest)


def patch_desc(desc: str) -> str:
    desc = apply_junk_patterns(desc)
    desc = clean_hashtags(desc)
    desc = collapse_keyword_gaps(desc)
    desc = normalize_newlines(desc)
    return desc + '\n\n' + CTA


def main():
    files = sorted(OPT_DIR.glob('*.json'))
    patched = 0
    flagged = []

    for f in files:
        d = json.loads(f.read_text())
        orig_desc = d['description']

        new_desc = patch_desc(orig_desc)

        # Preserve flag if it was already set (e.g. manually or from previous run)
        was_flagged = bool(d.get('needs_ai_desc'))

        # Also flag if desc looks like Wikipedia prose (no AI opening, generic encyclopaedic)
        first_line = new_desc.lstrip().split('\n')[0]
        wiki_like = bool(re.search(
            r'^(?:[A-Z][^\n]{0,40}(?:\sis\s(?:a|an)\s|\swas\s(?:a|an)\s|\swrote\s))',
            first_line
        ) and not d.get('changes', {}).get('description'))

        total = total_content_length(new_desc)
        if was_flagged or total < 250 or wiki_like:
            d['needs_ai_desc'] = True
            d['ai_done'] = False        # force AI re-run
            new_desc = CTA              # clean slate — AI will prepend opening
            flagged.append((total, f.name[:65]))
        else:
            d.pop('needs_ai_desc', None)

        had_stale_flag = 'needs_ai_desc' in json.loads(f.read_text())
        if new_desc != orig_desc or d.get('needs_ai_desc') or had_stale_flag:
            d['description'] = new_desc
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            patched += 1

    print(f'Patched {patched}/{len(files)} files')
    print(f'\nFlagged {len(flagged)} for AI desc re-run (body < {SHORT_THRESH} chars):')
    for blen, name in sorted(flagged):
        print(f'  [{blen:3d}c] {name}')


if __name__ == '__main__':
    main()
