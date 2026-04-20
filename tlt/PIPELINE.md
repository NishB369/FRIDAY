# TLT Pipeline — Node Graph

Branched flow from raw audio recording (or YouTube source) to YouTube upload + TLT website publish.

```
┌──────────────────────────────────────────────────────────────────┐
│  [N0] AUDIO SOURCE                                               │
│  Aanchal's m4a/mp3 recording (tlt/audios/*) OR YT extractor      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  [N1] TRANSCRIBE + KARAOKE  (Sarvam + Groq + Claude + Remotion)  │
│  audio→video skill: chunk · dual-transcribe · align · Hinglish · │
│  render · mux                                                    │
│  → tlt/transcripts/{slug}_merged.json                            │
│  → remotion/outputs/{slug}_full.mp4                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  [N2] NORMALISE → unified canonical JSON                         │
│  source · slug · title · transcript.full_text · chunks · lang ·  │
│  duration · (optional youtube{video_id, channel, ...})           │
│  → tlt/n2/{slug}_n2.json                                         │
└──────────────────────────┬───────────────────────────────────────┘
                           │
        ┌──────────────────┼─────────────────────┐
        ▼                  ▼                     ▼
┌─────────────────────┐  ┌──────────────┐  ┌─────────────┐
│ [N3a] SUMMARY DOCS  │  │ [N3c] QUIZ   │  │ [N3d] YT    │
│ overview (full+YAML)│  │ MCQ / Q&A    │  │ METADATA    │
│ summary (narrative) │  │ → quiz/      │  │ title·desc· │
│ notes  (analysis)   │  │              │  │ tags·chaps  │
│ → processed/        │  │              │  │ (YT-only)   │
│   {overview,summary,│  │              │  │             │
│   notes}/           │  │              │  │             │
└──────┬──────────────┘  └──────┬───────┘  └──────┬──────┘
       │                        │                 │
       │    ┌───────────────────┘                 │
       │    │                                     │
       ▼    ▼                                     ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│ [N4-VIDEO] YT VIDEO      │  │ [N4-WEB] TLT WEBSITE PUBLISH         │
│ ─ karaoke .mp4 from N1   │  │ ─ MD → post (overview / summary /    │
│ ─ Thumbnail              │  │   notes views)                       │
│ ─ Chapters from N2 chunks│  │ ─ Quiz component embed               │
│                          │  │ ─ SEO: keywords from N3d / overview  │
│ → final .mp4             │  │ → live page at /posts/{slug}         │
└────────────┬─────────────┘  └────────────────┬─────────────────────┘
             │                                 │
             ▼                                 ▼
      ┌──────────────┐                 ┌──────────────────┐
      │ [N5] YT      │◀───── links ───▶│ [N5] Website     │
      │ UPLOAD       │                 │ LIVE             │
      │ title/desc/  │                 │ indexed, shared  │
      │ tags = N3d   │                 │                  │
      └──────┬───────┘                 └──────────────────┘
             │
             ▼
      ┌──────────────────────────────┐
      │ [N6] TRACKER sync            │
      │ tlt/TRACKER.md row flip to ✅│
      └──────────────────────────────┘
```

## Note on N3b
Originally planned as a separate "notes" generator. Dropped — `summarize_n2.py`
already emits the analysis-half view (`processed/notes/`) by splitting the
overview, so a dedicated N3b is redundant.

## Branch points

- **After N2** the pipeline fans out into parallel content artifacts (N3a, N3c, N3d). None depend on each other.
- **N4 splits into two consumers**: the **video track** (uses N1's mp4 + N2 chunks + N3d metadata) and the **web track** (uses N3a markdown views + N3c quiz + N3d SEO).
- **N3d is YT-only** — skipped when `n2.source == "audio"`.
- **N5 cross-links**: YT description points to website post; website post embeds/links the YT video.

## Status

| Node | Artifact | Script / tool | Status |
|------|----------|---------------|--------|
| N0   | `tlt/audios/*` | manual upload | ✓ |
| N1   | `remotion/outputs/{slug}_full.mp4`, `tlt/transcripts/{slug}_merged.json` | skill: `audio-to-karaoke` (`full_audio_karaoke.py`) | ✓ |
| N2   | `tlt/n2/{slug}_n2.json` | `normalize_to_n2.py` | ✓ |
| N3a  | `tlt/processed/{overview,summary,notes}/` | `summarize_n2.py` (overview + auto-split) | ✓ |
| N3c  | `tlt/processed/quiz/` | `generate_quizzes.py` on N2 | ✓ |
| N3d  | `tlt/processed/optimized_metadata/` | metadata optimizer on N2 (gated on `source=youtube`) | ✓ |
| N4-VIDEO | final `.mp4` (+ thumbnail, chapters) | `remotion/` karaoke ✓; `generate_chapters_n2.py` ✓; thumbnail TBD | partial |
| N4-WEB   | website post | TLT website repo (TBD) | pending |
| N5   | YT upload + live page | manual / API | pending |
| N6   | `tlt/TRACKER.md` sync | manual / sync script | pending |
| —    | HTML previewer for all nodes | `build_preview.py` → `tlt/preview/` | ✓ |
