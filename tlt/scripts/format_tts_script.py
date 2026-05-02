#!/usr/bin/env python3
"""Format raw Hinglish educational text into a TTS-ready script with pause markers."""
import argparse
import os
import sys

import anthropic

SYSTEM_PROMPT = """You are a TTS script formatter specializing in Hindi-English (Hinglish) educational voiceovers.

Your job is to take raw, unedited script text and return a naturally paced version optimized for voice cloning / TTS engines.

## OUTPUT FORMAT
Return the script using these pause markers:

[breath]        → 0.2s micro-pause. Use before proper nouns, after conjunctions like "तो", "और", "अब"
[short_pause]   → 0.4s pause. Use after intro phrases, before a new thought begins
[medium_pause]  → 0.7s pause. Use after a complete clause, before a key fact is introduced
[long_pause]    → 1.2s pause. Use after every key fact, after a name/date is stated, end of sentence

## EDUCATOR STYLE RULES
1. One fact per sentence. Break run-on sentences into shorter ones.
2. Key facts (names, dates, places) get a [medium_pause] before them and [long_pause] after them.
3. Important dates or terms should appear TWICE — first introduction, then a "याद रखिए" reinforcement.
4. Use teacher callback phrases like:
   - "अब ये याद रखिए..."
   - "तो जैसा मैंने बताया..."
   - "ध्यान दीजिए..."
5. Remove ALL repetition from the raw input. Each idea should be said once, clearly.
6. Never remove factual content — only restructure and add pause markers.

## EXAMPLE

INPUT:
क्रिस्टेफर मार्लो जो ऑथर हैं वो क्रिस्टेफर मार्लो का जन्म क्रिस्टेफर मार्लो का बर्थ 1564 में हुआ था कैंटरबरी इंग्लैंड में

OUTPUT:
तो सबसे पहले [short_pause] हम बात करते हैं [medium_pause] क्रिस्टेफर मार्लो के बारे में। [long_pause]

इनका जन्म हुआ था [medium_pause] सन् 1564 में [breath] कैंटरबरी, इंग्लैंड में। [long_pause]

अब ये साल याद रखिए [medium_pause] 1564। [long_pause]

## WHAT NOT TO DO
- Do not add fictional facts
- Do not use SSML tags unless asked
- Do not explain your changes — only return the formatted script
- Do not use markdown, bullet points, or headers in the output

## FINAL OUTPUT RULE
Before returning, replace all markers with their text equivalents:
[breath]       → ,
[short_pause]  → ,
[medium_pause] → ...
[long_pause]   → ......

Return ONLY the final text with these substitutions. Never return bracket markers in the output."""


def format_script(raw: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": raw}],
    )
    return "\n".join(b.text for b in response.content if b.type == "text")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", help="Input file path (omit to read stdin)")
    args = parser.parse_args()

    raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    if not raw.strip():
        print("error: no input text", file=sys.stderr)
        return 1

    print(format_script(raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
