import json, os

filepath = '/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/the_real_crusoe_back_exercise_roots_and_wings_class_6th_lite_c-mBMR5i0Dw.json'

with open(filepath) as f:
    d = json.load(f)

meta = {k: v for k, v in d.items() if k != 'transcript'}
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/crusoe_meta_out.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)

transcript_text = d.get('transcript', {}).get('full_text', '')
available = d.get('transcript', {}).get('available', False)

with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/scripts/crusoe_transcript_out.txt', 'w') as f:
    f.write(transcript_text)

print('video_id:', d.get('video_id'))
print('title:', d.get('title'))
print('published_at:', d.get('published_at'))
print('duration_seconds:', d.get('duration_seconds'))
print('language:', d.get('language'))
print('channel:', d.get('channel'))
print('tags:', d.get('tags'))
print('description:', d.get('description', ''))
print('transcript available:', available)
print('transcript length chars:', len(transcript_text))
