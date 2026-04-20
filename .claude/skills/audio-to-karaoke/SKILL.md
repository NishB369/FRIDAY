---
name: audio-to-karaoke
description: Convert any TLT audio file (mp3/m4a/wav, any length) into a Hinglish karaoke video with synced word highlighting. Use when the user wants to turn a lecture audio into a karaoke video, generate Remotion karaoke output, or run the audio→video node of the TLT pipeline.
---

# audio-to-karaoke

End-to-end pipeline that turns one source audio into a finished karaoke MP4 with synced Hinglish word highlighting and the original audio muxed back in.

## When to use

Trigger on any of:
- "make a karaoke video for X.mp3"
- "convert this audio to karaoke"
- "run the audio→video node"
- "generate karaoke for [TLT audio]"

## What it produces

- Final video: `remotion/outputs/<slug>_full.mp4` (with audio)
- Per-chunk transcripts: `tlt/transcripts/<slug>_<S>-<E>s_dual.json`
- Merged transcript: `tlt/transcripts/<slug>_merged.json`
- Remotion props: `remotion/props/<slug>_full.json`
- Re-encoded full audio (for mux): `tlt/audios/<slug>_full.mp3`

## How it works

Stack:
- **Sarvam** (`saaras:v3`, `mode=transcribe`) — clean Hindi+English transcription
- **Groq Whisper** (`whisper-large-v3`) — word + segment timestamps for alignment anchors
- **Segment-anchored alignment** — Sarvam tokens distributed across Groq segment time windows by character ratio
- **Claude Haiku** — Devanagari → Hinglish transliteration (English tokens pass through)
- **Remotion** (`TranscriptKaraoke` composition) — renders the karaoke frames
- **ffmpeg** — chunking, full-audio re-encoding, audio mux

Sarvam's REST endpoint caps at 30s per call, so the wrapper auto-chunks into 29s pieces and stitches the timing back together with offset correction.

## Required env vars

Loaded from `.env` at the repo root:
- `SARVAM_API_KEY`
- `GROQ_API_KEY`
- `ANTHROPIC_API_KEY`

## How to invoke

```bash
set -a && . ./.env && set +a && \
  .venv/bin/python tlt/scripts/full_audio_karaoke.py \
    --src "tlt/audios/<source-file>" \
    --slug <output_slug> \
    --hinglish \
    --delay-ms 200
```

For long audio (>2 min), run in background and use Monitor to track chunk progress + render stitching.

## Tunable knobs

- `--delay-ms N` — shift highlights N ms later (default 200, raise if highlights feel early, lower if late)
- `--hinglish` — toggle Devanagari → Hinglish transliteration via Claude (omit to keep Devanagari)

## Per-chunk-only flow (debug / single 29s clip)

If the user wants a single short clip rather than full audio:

```bash
.venv/bin/python tlt/scripts/dual_transcribe.py \
  --slug <slug> --src "<audio>" --start <S> --duration <D≤29>

.venv/bin/python tlt/scripts/dual_to_karaoke.py \
  --slug <slug>_<S>-<E>s --hinglish --delay-ms 200

cd remotion && npx remotion render TranscriptKaraoke \
  outputs/<slug>_<S>-<E>s_silent.mp4 \
  --props=props/<slug>_<S>-<E>s.json --frames=0-<N>

ffmpeg -y -i remotion/outputs/<slug>_<S>-<E>s_silent.mp4 \
       -i tlt/audios/<slug>_<S>-<E>s.mp3 \
       -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest \
       remotion/outputs/<slug>_<S>-<E>s.mp4
```

## Known limits

- Sarvam REST = 30s cap per call; wrapper handles via 29s chunking. For higher throughput, switch to Sarvam **Batch API** (up to 1 hour per file) — not yet wired.
- Alignment is **segment-anchored proportional** (text-derived), not acoustic forced alignment. Drift bounded per segment, generally <300ms; if user reports bad sync, first try `--delay-ms` adjustment, then consider WhisperX as a future upgrade.
- Audio mux must use explicit `-map 0:v:0 -map 1:a:0` and `-b:a 192k` — without these ffmpeg encodes audio at ~2 kbps (effectively silent).

## Files this skill owns

- `tlt/scripts/full_audio_karaoke.py` — top-level wrapper
- `tlt/scripts/dual_transcribe.py` — Sarvam + Groq + alignment
- `tlt/scripts/dual_to_karaoke.py` — props builder + Hinglish
- `remotion/src/compositions/TranscriptKaraoke.*` — Remotion composition
