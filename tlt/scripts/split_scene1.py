import json

filepath = '/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/philemon_and_baucis_scene_i_roots_and_wings_class_6th_englis_UbNe291__oQ.json'

with open(filepath) as f:
    d = json.load(f)

# Write metadata file (no transcript)
meta = {k: v for k, v in d.items() if k != 'transcript'}
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/scene1_meta.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# Write transcript text
transcript = d.get('transcript', {})
transcript_out = {
    'video_id': d.get('video_id'),
    'title': d.get('title'),
    'language': d.get('language'),
    'transcript': transcript
}
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/scene1_transcript.json', 'w') as f:
    json.dump(transcript_out, f, indent=2, ensure_ascii=False)

# Write a plain text summary of metadata for quick reading
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/scene1_info.txt', 'w') as f:
    f.write('video_id: ' + str(d.get('video_id')) + '\n')
    f.write('title: ' + str(d.get('title')) + '\n')
    f.write('channel: ' + str(d.get('channel')) + '\n')
    f.write('published_at: ' + str(d.get('published_at')) + '\n')
    f.write('duration_seconds: ' + str(d.get('duration_seconds')) + '\n')
    f.write('language: ' + str(d.get('language')) + '\n')
    f.write('tags: ' + str(d.get('tags')) + '\n')
    f.write('description:\n' + str(d.get('description')) + '\n')
    f.write('\ntranscript_available: ' + str(transcript.get('available')) + '\n')
    f.write('transcript_word_count: ' + str(transcript.get('word_count')) + '\n')
    f.write('transcript_length_chars: ' + str(len(transcript.get('full_text', ''))) + '\n')
    f.write('\n=== FULL TRANSCRIPT ===\n')
    f.write(transcript.get('full_text', ''))

print('Done! Files written.')
