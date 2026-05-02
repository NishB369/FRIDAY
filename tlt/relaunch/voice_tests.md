# Voicebox Voice Cloning — Test Log

**Profiles:**
- ~~`T1`~~ — deleted
- ~~`Aanchal-v2`~~ — deleted
- ~~`Aanchal-sultana`~~ — deleted
- **`Aanchal-sultana-12`** — `12c7ecc1-d754-43c5-a57e-b1fca4ad8d58` — 12 samples (all sultanas_dream, 29s × 12 = ~6 min reference)

**Test text (kept constant across all tests for fair comparison):**
```
मार्लो ... जिस ज़माने में जीता था , 16वीं सेंचुरी इंग्लैंड। ......

वो एक , मैसिव ट्रांसफॉर्मेशन का टाइम था। ......

सोचो ... क्या क्या हो रहा था उस वक्त ...
```

---

## Scorecard (use for every test)

Each axis rated **1–5**. Total out of **30**.

| Axis | What to listen for |
|---|---|
| **Speed/pacing** | Rushed (1) ↔ natural (3) ↔ dragging (5) — sweet spot is 3-4 |
| **Naturalness** | Robotic/AI (1) ↔ real human (5) |
| **Voice match** | Generic voice (1) ↔ unmistakably Aanchal (5) |
| **Pause adherence** | Steamrolls punctuation (1) ↔ pauses exactly where `...` and `......` are (5) |
| **Pronunciation** | Hinglish words wrong (1) ↔ all words correct (5) |
| **Emotion/warmth** | Flat monotone (1) ↔ engaged teacher (5) |

**Scale anchors:**
- **5** = Perfect, indistinguishable from a real recording
- **4** = Very good, minor flaw, would ship
- **3** = Acceptable, noticeable issues but usable
- **2** = Bad, needs fixing
- **1** = Unusable

---

## Parameter cheat sheet

| Param | Type | Notes |
|---|---|---|
| `language` | `en` / `hi` / etc. | Prosody routing — `en` worked better for Hinglish |
| `engine` | `chatterbox` / `qwen` / `chatterbox_turbo` / `kokoro` / ... | TTS backbone (we use chatterbox) |
| `effects_chain.atempo.tempo` | float, e.g. `0.75` | Playback speed; <1 = slower |
| `instruct` | string ≤500 | Engine guidance, e.g. "speak slowly and warmly" |
| `personality` | bool | If true, profile's personality prompt rewrites text in-character before TTS |
| `seed` | int / null | Determinism — same seed = repeatable output |
| `max_chunk_chars` | int (default 800) | Long-text chunking |
| `crossfade_ms` | int (default 50) | Crossfade between chunks |
| `normalize` | bool (default true) | Auto-normalize output volume |

---

## Test 1

**Hypothesis:** Baseline — does adding 10 varied reference samples alone produce natural output without any other tweaks?

**Settings:**
- `language`: `en`
- `engine`: `chatterbox`
- `effects_chain`: none
- `instruct`: none
- `personality`: false
- `seed`: null
- other: profile defaults

**Generation ID:** `dc160be6-afb1-4a7c-ad6e-6dadcd9d6a0c` (previous attempts `e5e4c463`, `e241e4a6` were orphaned by server stalls; resolved by killing stuck `voicebox-server` processes and relaunching)

**Score:**

| Axis | Score (1-5) | Note |
|---|---|---|
| Speed/pacing | 3 | natural without atempo |
| Naturalness | 2.5 | weakest axis |
| Voice match | 2.5 | weakest axis — varied samples may be averaging out Aanchal's distinctive timbre |
| Pause adherence | 4 | punctuation-as-pauses approach is working |
| Pronunciation | 4 |  |
| Emotion/warmth | 3.5 |  |
| **Total** | **19.5/30** |  |

**Verdict:** iterate — naturalness + voice match need lift, pacing is fine

---

## Test 2

**Hypothesis:** Adding an `instruct` field with warmth/teacher guidance lifts naturalness and emotion without disturbing pacing or pauses (the strong axes from Test 1).

**Settings:**
- `language`: `en`
- `engine`: `chatterbox`
- `effects_chain`: none
- `instruct`: `"Speak warmly and naturally, like a literature teacher explaining to her students. Use conversational rhythm with natural emphasis on key words."`
- `personality`: false
- `seed`: null
- other: profile defaults

**Generation ID:** `dcf596bb-e68d-42bc-b18b-9c2cefdef2a1`

**Score:**

| Axis | Score (1-5) | Note |
|---|---|---|
| Speed/pacing | — | (not scored) |
| Naturalness | — |  |
| Voice match | — |  |
| Pause adherence | — |  |
| Pronunciation | — |  |
| Emotion/warmth | — |  |
| **Total** | **—/30** | poorer than Test 1 |

**Verdict:** discard — `instruct` field made naturalness worse, not better

---

## Test 3

**Hypothesis:** Setting a personality prompt on the profile + `personality: true` will rewrite the input text in-character (more natural fillers, varied sentence length, warmth) before TTS — should lift naturalness and emotion. Personality prompt copied from T1.

**Settings:**
- `language`: `en`
- `engine`: `chatterbox`
- `effects_chain`: none
- `instruct`: none
- `personality`: **true** (profile prompt: "You are Aanchal, warm Hinglish literature teacher...")
- `seed`: null
- other: profile defaults

**Generation ID:** `c535b617-70a0-4fc6-ad7b-ad0c3d30d2e5`

**⚠️ Side effect:** `personality: true` rewrites the input text before TTS — output may have added fillers (`तो`, `हाँ`, `मतलब`) and reordered pause markers. The "spoken text" will differ from the input.

**Score:**

| Axis | Score (1-5) | Note |
|---|---|---|
| Speed/pacing | _ |  |
| Naturalness | _ |  |
| Voice match | _ |  |
| Pause adherence | _ |  |
| Pronunciation | _ |  |
| Emotion/warmth | _ |  |
| **Total** | **_/30** |  |

**Verdict:** _________

---

---

## Test 4

**Hypothesis:** personality (helping per Test 3) + `atempo: 0.85` to slow slightly — compound effect on naturalness/voice match.

**Settings:**
- `language`: `en`
- `engine`: `chatterbox`
- `effects_chain`: `[{type: "atempo", params: {tempo: 0.85}}]`
- `instruct`: none
- `personality`: **true**
- other: profile defaults

**Generation ID:** `b5247e90-f278-4799-a5a3-90d870ede944`

**Score:**

| Axis | Score (1-5) | Note |
|---|---|---|
| Speed/pacing | _ |  |
| Naturalness | _ |  |
| Voice match | _ |  |
| Pause adherence | _ |  |
| Pronunciation | _ |  |
| Emotion/warmth | _ |  |
| **Total** | **_/30** |  |

**Verdict:** _________

---

---

## Test 5

**Hypothesis:** A single-context profile (5 sultanas_dream clips only) may produce a more cohesive voice than the mixed-context Aanchal-v2 (10 clips across 5 different recordings) — narrower distribution may preserve Aanchal's distinctive timbre better.

**Profile:** `Aanchal-sultana` (`698fd5bc-9f71-4b1f-bdcb-ff4fad6cb17f`) — 5 samples, all from sultanas_dream

**Settings:**
- `language`: `en`
- `engine`: `chatterbox`
- `effects_chain`: none
- `instruct`: none
- `personality`: false
- other: profile defaults

**Generation ID:** `5b803cf6-13ba-47b7-b617-5c9cfec7b28e`

**Score:**

| Axis | Score (1-5) | Note |
|---|---|---|
| Speed/pacing | _ |  |
| Naturalness | _ |  |
| Voice match | _ |  |
| Pause adherence | _ |  |
| Pronunciation | _ |  |
| Emotion/warmth | _ |  |
| **Total** | **_/30** |  |

**Verdict:** _________

---

## Summary

| # | Profile | Settings (short) | Gen ID | Speed | Natural | Voice | Pause | Pron | Emo | Total | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Aanchal-v2 | defaults, 10 mixed samples | `dc160be6` | 3 | 2.5 | 2.5 | 4 | 4 | 3.5 | 19.5 | iterate |
| 2 | Aanchal-v2 | + instruct (warmth) | `dcf596bb` | — | — | — | — | — | — | — | discard (poorer) |
| 3 | Aanchal-v2 | + personality | `c535b617` | — | — | — | — | — | — | — | "bit better", discarded |
| 4 | Aanchal-v2 | + personality + atempo 0.85 | `b5247e90` | — | — | — | — | — | — | — | discarded |
| 5 | Aanchal-sultana | defaults, 5 single-context | `5b803cf6` |  |  |  |  |  |  |  | "pretty good, synced — but pitch too high" |
| 6 | Aanchal-sultana | + `pitch_shift` -2 semitones | `c6e4c7a7` |  |  |  |  |  |  |  | feels robotic — too much pitch artifact |
| 7 | Aanchal-sultana | pitch_shift -1 + compressor + model_size 3B | `d81d6d82` | — | — | — | — | — | — | — | discarded — even more robotic than Test 6 |
| 8 | Aanchal-sultana | + personality (text rewrite), no effects | `545ffd19` |  |  |  |  |  |  |  | "remove personality" — discarded |
| 9 | Aanchal-sultana-12 | defaults, intro text (real-world A/B) | `48a22368` |  |  |  |  |  |  |  | (prev `8bcbb154`, `71122b5b` orphaned) |

**Profile state reset:** `personality` cleared back to `null`. Aanchal-v2 now matches Test 1 base config.
| 3 |  |  |  |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |  |  |  |
