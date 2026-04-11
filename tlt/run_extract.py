import json, os

filepath = "json-res/my_mother_at_sixty_six_class_12_summary_my_mother_at_66_clas_rbOvSQmD2SA.json"
base = "my_mother_at_sixty_six_class_12_summary_my_mother_at_66_clas_rbOvSQmD2SA"

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

# Print meta for inspection
print("=== META ===")
print(json.dumps(meta, indent=2, ensure_ascii=False))

# Print transcript length and content in chunks
ft = data.get('transcript', {}).get('full_text', '')
print(f"\n=== TRANSCRIPT LENGTH: {len(ft)} chars ===")
print("\n=== TRANSCRIPT 0-4000 ===")
print(ft[:4000])
print("\n=== TRANSCRIPT 4000-8000 ===")
print(ft[4000:8000])
print("\n=== TRANSCRIPT 8000-12000 ===")
print(ft[8000:12000])
print("\n=== TRANSCRIPT 12000-16000 ===")
print(ft[12000:16000])
print("\n=== TRANSCRIPT 16000-20000 ===")
print(ft[16000:20000])
print("\n=== TRANSCRIPT 20000-24000 ===")
print(ft[20000:24000])
print("\n=== TRANSCRIPT 24000-28000 ===")
print(ft[24000:28000])
print("\n=== TRANSCRIPT 28000-32000 ===")
print(ft[28000:32000])
print("\n=== TRANSCRIPT 32000-36000 ===")
print(ft[32000:36000])
print("\n=== TRANSCRIPT 36000-40000 ===")
print(ft[36000:40000])
print("\n=== TRANSCRIPT 40000+ ===")
print(ft[40000:])
print("\nDone.")
