import json

with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/philemon_and_baucis_scene_i_roots_and_wings_class_6th_englis_UbNe291__oQ.json') as f:
    d = json.load(f)

# Save metadata (no transcript)
meta = {k: v for k, v in d.items() if k != 'transcript'}
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/tmp_meta.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

# Save transcript text only
transcript_text = d.get('transcript', {}).get('full_text', '')
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/tmp_transcript.txt', 'w') as f:
    f.write(transcript_text)

print('Done. Transcript length (chars):', len(transcript_text))
print('Transcript available:', d.get('transcript', {}).get('available'))
