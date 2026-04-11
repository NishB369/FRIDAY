import json, os

filepath = "/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/things_fall_apart_important_question_notes_link_in_descripti_-pS8OYvoFLY.json"
outdir = "/Users/aanchalbhatia/Desktop/Aanchal/tlt"
base = "things_fall_apart_important_question_notes_link_in_descripti_-pS8OYvoFLY"

with open(filepath) as f:
    data = json.load(f)

meta = {k: v for k, v in data.items() if k != 'transcript'}
ft = data.get('transcript', {}).get('full_text', '')
total = len(ft)

with open(outdir + "/tmp_meta.json", 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

chunk_size = 8000
for i, start in enumerate(range(0, total, chunk_size)):
    chunk = ft[start:start+chunk_size]
    with open(outdir + "/tmp_transcript_" + str(i).zfill(2) + ".txt", 'w') as f:
        f.write(chunk)

with open(outdir + "/tmp_info.txt", 'w') as f:
    f.write("total_chars=" + str(total) + "\n")
    f.write("num_chunks=" + str(len(range(0, total, chunk_size))) + "\n")
    f.write("video_id=" + str(data.get('video_id')) + "\n")
    f.write("title=" + str(data.get('title')) + "\n")

os.makedirs(outdir + '/raw/metadata', exist_ok=True)
os.makedirs(outdir + '/raw/transcripts', exist_ok=True)

with open(outdir + '/raw/metadata/' + base + '.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

transcript_data = {
    'video_id': data.get('video_id'),
    'title': data.get('title'),
    'language': data.get('language'),
    'transcript': data.get('transcript')
}
with open(outdir + '/raw/transcripts/' + base + '.json', 'w') as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)

print("Done")
print("total_chars=" + str(total))
print("video_id=" + str(data.get('video_id')))
print("title=" + str(data.get('title')))
