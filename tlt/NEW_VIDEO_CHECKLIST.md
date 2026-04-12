# TLT — New Video Upload Checklist

> Reference benchmark: **Sultana's Dream** (45K views) — the channel's best-performing video.
> Every new upload should meet or exceed this standard before going live.

---

## 1. TITLE

**Formula:** `[Work Title] by [Author] | [What the video covers] in Hindi`

**Rules:**
- 60–90 characters (YouTube shows ~70 chars in search)
- Max 2 pipe separators `|`
- Title Case — not ALL CAPS, no emoji
- Always include author name if applicable
- Include one of: `explanation`, `summary`, `line by line`, `analysis`
- Include `in Hindi` at the end (your audience searches in Hindi)
- If curriculum-specific: add `| BA Eng Hons` or `| Class 6 Roots and Wings` as last segment

**Good:** `Sultana's Dream by Rokeya Sakhawat Hossain | Line by Line Explanation in Hindi`
**Bad:** `SULTANA'S DREAM | EXPLANATION | DU | SOL | CBCS | NOTES IN DESCRIPTION`

---

## 2. DESCRIPTION

**Structure (in this order):**

```
[2–3 sentence content paragraph about the text/topic — real information, not keyword repetition]

[Course/curriculum context — e.g. "This video is for BA English Honours students (2nd semester) covering [syllabus]."]

[Keyword variations — 8–10 lines of natural search variants, not copy-pasted spam]

[Links section]
📚 Notes & Quizzes: https://literature-talks.vercel.app/
✉️ Telegram: https://t.me/theliteraturetalks
📸 Instagram: https://www.instagram.com/aaanchalbhatiaaa/
```

**Rules:**
- First sentence must be substantive content (not a link, not "JOIN US ON TELEGRAM")
- Keyword block: each variation on its own line, no duplicate lines
- Always include all 3 links (platform + Telegram + Instagram)
- Max 5000 characters total

---

## 3. TAGS

**Structure:** 15–20 tags total

| Type | Examples | Count |
|---|---|---|
| Exact title match | `sultanas dream by rokeya sakhawat hossain` | 1 |
| Work name variants | `sultanas dream`, `sultana dream` | 2–3 |
| Author name | `rokeya sakhawat hossain`, `begum rokeya` | 2 |
| Action tags | `sultanas dream summary in hindi`, `sultanas dream explanation` | 3–4 |
| Curriculum tags | `ba eng hons`, `ba eng hons sem 3`, `cec edusat` | 2–3 |
| Theme/genre tags | `feminist utopia`, `short story`, `english literature` | 2–3 |
| **Brand tag (mandatory)** | `the literature talks` | 1 |

**Never use:** generic tags like `education`, `enjoy`, `trending video`, `knowledge`

---

## 4. THUMBNAIL

- Text on thumbnail must match the video title (same work + author)
- Consistent template: dark background, gold/white text, author name visible
- Resolution: 1280×720 minimum
- No clickbait imagery unrelated to the content

---

## 5. CARDS & END SCREEN

- Add 2–3 cards linking to related videos on the same author or curriculum level
- End screen: subscribe button + 2 video recommendations

---

## 6. PLATFORM SYNC (after upload)

- [ ] Add video to DB via TLT backend (`POST /api/videos`)
- [ ] Generate notes + summary (`tlt/scripts/summarize.py`)
- [ ] Generate quiz (`tlt/scripts/generate_quizzes.py`)
- [ ] Tag notes with genre (`tlt/scripts/patch_note_tags.py` if new tag needed)
- [ ] Publish on platform (`isPublished: true`)

---

## Quick Pre-Publish Check

```
[ ] Title: 60–90 chars, ≤2 pipes, Title Case, includes author + "in Hindi"
[ ] Description: opens with real content paragraph
[ ] Description: has all 3 links (platform / Telegram / Instagram)
[ ] Tags: 15–20 tags, includes "the literature talks"
[ ] Thumbnail: consistent template
[ ] Platform: DB entry + notes + summary + quiz all created
```
