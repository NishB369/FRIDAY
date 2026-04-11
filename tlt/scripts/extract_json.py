import json, sys

filepath = '/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/philemon_and_baucis_scene_i_roots_and_wings_class_6th_englis_UbNe291__oQ.json'

with open(filepath) as f:
    d = json.load(f)

meta = {k: v for k, v in d.items() if k != 'transcript'}
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/meta_out.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

transcript_text = d.get('transcript', {}).get('full_text', '')
available = d.get('transcript', {}).get('available', False)

with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/transcript_out.txt', 'w') as f:
    f.write(transcript_text)

print('video_id:', d.get('video_id'))
print('title:', d.get('title'))
print('published_at:', d.get('published_at'))
print('duration_seconds:', d.get('duration_seconds'))
print('language:', d.get('language'))
print('channel:', d.get('channel'))
print('transcript available:', available)
print('transcript length chars:', len(transcript_text))
