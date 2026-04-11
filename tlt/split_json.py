import json

base = "the_glass_menagerie_by_tennessee_williams_summary_and_explan_bDvtMvXAa0E"
src = f"json-res/{base}.json"

with open(src) as f:
    d = json.load(f)

# metadata (no transcript, no comments)
meta = {k: v for k, v in d.items() if k not in ("transcript", "comments")}
with open(f"raw/metadata/{base}.json", "w") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

# transcript
trans = {k: d[k] for k in ("video_id", "title", "language", "transcript")}
with open(f"raw/transcripts/{base}.json", "w") as f:
    json.dump(trans, f, ensure_ascii=False, indent=2)

print("Done")
