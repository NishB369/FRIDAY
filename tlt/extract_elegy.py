import json, os

with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/elegy_written_in_a_country_charchyard_poem_summary_in_hindi_tBn3XXCvfQY.json', 'r') as f:
    data = json.load(f)

print("video_id:", data.get('video_id'))
print("title:", data.get('title'))
print("channel:", data.get('channel'))
print("published_at:", data.get('published_at'))
print("duration_seconds:", data.get('duration_seconds'))
print("language:", data.get('language'))
print("tags:", data.get('tags'))
print("description:", data.get('description', '')[:1000])
print("transcript_available:", data.get('transcript', {}).get('available'))
print("full_text_length:", len(data.get('transcript', {}).get('full_text', '')))
print("---FULL_TEXT_START---")
print(data.get('transcript', {}).get('full_text', ''))
print("---FULL_TEXT_END---")
