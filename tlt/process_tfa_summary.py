import json, os

filepath = '/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/things_fall_apart_novel_by_chinua_achebe_summary_in_hindi_ex_J5eRxGyJvR4.json'
b = 'things_fall_apart_novel_by_chinua_achebe_summary_in_hindi_ex_J5eRxGyJvR4'

with open(filepath) as f:
    d = json.load(f)

os.makedirs('/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/metadata', exist_ok=True)
os.makedirs('/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/transcripts', exist_ok=True)

m = {k: v for k, v in d.items() if k != 'transcript'}
with open(f'/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/metadata/{b}.json', 'w') as f:
    json.dump(m, f, indent=2, ensure_ascii=False)

t = {
    'video_id': d.get('video_id'),
    'title': d.get('title'),
    'language': d.get('language'),
    'transcript': d.get('transcript')
}
with open(f'/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/transcripts/{b}.json', 'w') as f:
    json.dump(t, f, indent=2, ensure_ascii=False)

print("=== METADATA ===")
print(json.dumps(m, indent=2, ensure_ascii=False))
print("\n=== TRANSCRIPT LENGTH ===")
ft = d.get('transcript', {}).get('full_text', '')
print(len(ft))
print("\n=== TRANSCRIPT (0-6000) ===")
print(ft[:6000])
print("\n=== TRANSCRIPT (6000-12000) ===")
print(ft[6000:12000])
print("\n=== TRANSCRIPT (12000-18000) ===")
print(ft[12000:18000])
print("\n=== TRANSCRIPT (18000-24000) ===")
print(ft[18000:24000])
print("\n=== TRANSCRIPT (24000+) ===")
print(ft[24000:])
print("\n=== DONE ===")
