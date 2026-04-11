import json, os

src = '/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/elegy_written_in_a_country_charchyard_poem_summary_in_hindi_tBn3XXCvfQY.json'

with open(src, 'r') as f:
    data = json.load(f)

# Print metadata
print("video_id:", data.get('video_id'))
print("title:", data.get('title'))
print("channel:", data.get('channel'))
print("published_at:", data.get('published_at'))
print("duration_seconds:", data.get('duration_seconds'))
print("language:", data.get('language'))
print("tags:", data.get('tags'))
print("description:", data.get('description', '')[:800])
print("transcript_available:", data.get('transcript', {}).get('available'))
print("full_text_length:", len(data.get('transcript', {}).get('full_text', '')))

# Save metadata file (everything except transcript)
meta = {k: v for k, v in data.items() if k != 'transcript'}
os.makedirs('/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/metadata', exist_ok=True)
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/metadata/elegy_written_in_a_country_charchyard_poem_summary_in_hindi_tBn3XXCvfQY.json', 'w') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)
print("Metadata saved.")

# Save transcript file
transcript_data = {
    'video_id': data.get('video_id'),
    'title': data.get('title'),
    'language': data.get('language'),
    'transcript': data.get('transcript', {})
}
os.makedirs('/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/transcripts', exist_ok=True)
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/raw/transcripts/elegy_written_in_a_country_charchyard_poem_summary_in_hindi_tBn3XXCvfQY.json', 'w') as f:
    json.dump(transcript_data, f, indent=2, ensure_ascii=False)
print("Transcript saved.")

# Print full transcript
print("---TRANSCRIPT---")
print(data.get('transcript', {}).get('full_text', ''))
