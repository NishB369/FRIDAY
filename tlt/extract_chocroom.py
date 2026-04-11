import json, os

INFILE = "/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/the_chocolate_room_roots_and_wings_class_7th_english_literat_W2a2I-TZM-o.json"
BASE = "the_chocolate_room_roots_and_wings_class_7th_english_literat_W2a2I-TZM-o"
OUTDIR = "/Users/aanchalbhatia/Desktop/Aanchal/tlt"

with open(INFILE) as f:
    data = json.load(f)

meta = {k: v for k, v in data.items() if k != 'transcript'}
ft = data.get('transcript', {}).get('full_text', '')
total = len(ft)

# Write meta
with open(f"{OUTDIR}/tmp_choc_meta.json", 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# Write transcript in chunks of 8000
chunk_size = 8000
for i, start in enumerate(range(0, total, chunk_size)):
    chunk = ft[start:start+chunk_size]
    with open(f"{OUTDIR}/tmp_choc_transcript_{i:02d}.txt", 'w') as f:
        f.write(chunk)

with open(f"{OUTDIR}/tmp_choc_info.txt", 'w') as f:
    f.write(f"total_chars={total}\n")
    f.write(f"num_chunks={len(range(0, total, chunk_size))}\n")
    f.write(f"video_id={data.get('video_id')}\n")
    f.write(f"title={data.get('title')}\n")
    f.write(f"channel={data.get('channel')}\n")
    f.write(f"published_at={data.get('published_at')}\n")
    f.write(f"duration_seconds={data.get('duration_seconds')}\n")
    f.write(f"language={data.get('language')}\n")
    f.write(f"tags={data.get('tags')}\n")
    f.write(f"description={data.get('description', '')[:800]}\n")

# Also save raw split files
os.makedirs(f'{OUTDIR}/raw/metadata', exist_ok=True)
os.makedirs(f'{OUTDIR}/raw/transcripts', exist_ok=True)

with open(f'{OUTDIR}/raw/metadata/{BASE}.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

transcript_data = {
    'video_id': data.get('video_id'),
    'title': data.get('title'),
    'language': data.get('language'),
    'transcript': data.get('transcript')
}
with open(f'{OUTDIR}/raw/transcripts/{BASE}.json', 'w') as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

print(f"Done. Transcript length: {total} chars, {len(range(0, total, chunk_size))} chunks.")
