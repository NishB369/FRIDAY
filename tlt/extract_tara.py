import json, os

filepath = "/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/tara_by_mahesh_dattani_summary_in_hindi_-dz1jvj5qIE.json"
outdir = "/Users/aanchalbhatia/Desktop/Aanchal/tlt"

with open(filepath) as f:
    data = json.load(f)

meta = {k: v for k, v in data.items() if k != 'transcript'}
ft = data.get('transcript', {}).get('full_text', '')
total = len(ft)

# Write meta to file
with open(f"{outdir}/tmp_tara_meta.json", 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# Write transcript in chunks
chunk_size = 8000
for i, start in enumerate(range(0, total, chunk_size)):
    chunk = ft[start:start+chunk_size]
    with open(f"{outdir}/tmp_tara_transcript_{i:02d}.txt", 'w') as f:
        f.write(chunk)

# Write summary info
with open(f"{outdir}/tmp_tara_info.txt", 'w') as f:
    f.write(f"total_chars={total}\n")
    f.write(f"num_chunks={len(range(0, total, chunk_size))}\n")
    f.write(f"video_id={data.get('video_id')}\n")
    f.write(f"title={data.get('title')}\n")

print("Done. Chunks:", len(range(0, total, chunk_size)))
