import json
fname = '/Users/nishb369/Desktop/FRIDAY/tlt/json-res/salman_rushdies_narrative_style_in_the_short_story_the_free_2A9Zo3PGOnk.json'
with open(fname) as f:
    data = json.load(f)
print("video_id:", data.get('video_id'))
print("title:", data.get('title'))
print("channel:", data.get('channel'))
print("published_at:", data.get('published_at'))
print("duration_seconds:", data.get('duration_seconds'))
print("language:", data.get('language'))
print("tags:", data.get('tags'))
print("description:", data.get('description', '')[:800])
transcript = data.get('transcript', {})
print("transcript available:", transcript.get('available'))
full_text = transcript.get('full_text', '')
print("transcript length:", len(full_text))
print("=== TRANSCRIPT PART 1 ===")
print(full_text[:5000])
