import json, sys

filepath = sys.argv[1]
part = sys.argv[2] if len(sys.argv) > 2 else "meta"

with open(filepath) as f:
    data = json.load(f)

if part == "meta":
    meta = {k: v for k, v in data.items() if k != 'transcript'}
    print(json.dumps(meta, indent=2))
elif part == "transcript_start":
    t = data.get('transcript', {})
    ft = t.get('full_text', '')
    print(f"LENGTH: {len(ft)}")
    print(ft[:4000])
elif part == "transcript_mid":
    t = data.get('transcript', {})
    ft = t.get('full_text', '')
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
    end = start + 4000
    print(ft[start:end])
elif part == "split":
    base = sys.argv[3]
    import os
    os.makedirs('raw/metadata', exist_ok=True)
    os.makedirs('raw/transcripts', exist_ok=True)
    meta = {k: v for k, v in data.items() if k != 'transcript'}
    with open(f'raw/metadata/{base}.json', 'w') as f:
        json.dump(meta, f, indent=2)
    transcript_data = {
        'video_id': data.get('video_id'),
        'title': data.get('title'),
        'language': data.get('language'),
        'transcript': data.get('transcript')
    }
    with open(f'raw/transcripts/{base}.json', 'w') as f:
        json.dump(transcript_data, f, indent=2)
    print("Split done.")
