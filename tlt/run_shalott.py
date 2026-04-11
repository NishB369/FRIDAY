import json, os

filepath = "json-res/the_lady_of_shalott_by_alfred_tennyson_line_by_line_explanat_cGddpj24q70.json"
base = "the_lady_of_shalott_by_alfred_tennyson_line_by_line_explanat_cGddpj24q70"

with open(filepath) as f:
    data = json.load(f)

# Save metadata
os.makedirs('raw/metadata', exist_ok=True)
os.makedirs('raw/transcripts', exist_ok=True)

meta = {k: v for k, v in data.items() if k != 'transcript'}
with open(f'raw/metadata/{base}.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# Save transcript
transcript_data = {
    'video_id': data.get('video_id'),
    'title': data.get('title'),
    'language': data.get('language'),
    'transcript': data.get('transcript')
}
with open(f'raw/transcripts/{base}.json', 'w') as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

print("Split done.")

# Print meta for inspection
print("=== META ===")
print(json.dumps(meta, indent=2, ensure_ascii=False))

# Print transcript in chunks
ft = data.get('transcript', {}).get('full_text', '')
print(f"\n=== TRANSCRIPT LENGTH: {len(ft)} chars ===")
chunk = 6000
for i in range(0, len(ft), chunk):
    print(f"\n=== TRANSCRIPT {i}-{i+chunk} ===")
    print(ft[i:i+chunk])
print("\nDone.")
