import json, os, sys

filepath = "/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/the_color_purple_by_alice_walker_summary_in_hindi_explanatio_DODxezG7wTw.json"
outdir = "/Users/aanchalbhatia/Desktop/Aanchal/tlt"

with open(filepath) as f:
    data = json.load(f)

meta = {k: v for k, v in data.items() if k != 'transcript'}
ft = data.get('transcript', {}).get('full_text', '')
total = len(ft)

# Write meta to file
with open(f"{outdir}/tmp_meta.json", 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# Write transcript in chunks
chunk_size = 8000
for i, start in enumerate(range(0, total, chunk_size)):
    chunk = ft[start:start+chunk_size]
    with open(f"{outdir}/tmp_transcript_{i:02d}.txt", 'w') as f:
        f.write(chunk)

# Write summary info
with open(f"{outdir}/tmp_info.txt", 'w') as f:
    f.write(f"total_chars={total}\n")
    f.write(f"num_chunks={len(range(0, total, chunk_size))}\n")
    f.write(f"video_id={data.get('video_id')}\n")
    f.write(f"title={data.get('title')}\n")

# Save raw split files
os.makedirs(f'{outdir}/raw/metadata', exist_ok=True)
os.makedirs(f'{outdir}/raw/transcripts', exist_ok=True)

base = "the_color_purple_by_alice_walker_summary_in_hindi_explanatio_DODxezG7wTw"
with open(f'{outdir}/raw/metadata/{base}.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

transcript_data = {
    'video_id': data.get('video_id'),
    'title': data.get('title'),
    'language': data.get('language'),
    'transcript': data.get('transcript')
}
with open(f'{outdir}/raw/transcripts/{base}.json', 'w') as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

print("Done")
