import json, sys
filepath = sys.argv[1] if len(sys.argv) > 1 else '/Users/nishb369/Desktop/FRIDAY/tlt/json-res/comment_on_the_theme_of_partition_in_the_shadow_lines_du_sol_2zMP61djEpA.json'
with open(filepath) as f:
    data = json.load(f)
# Print metadata
print("video_id:", data.get('video_id'))
print("title:", data.get('title'))
print("channel:", data.get('channel'))
print("published_at:", data.get('published_at'))
print("duration_seconds:", data.get('duration_seconds'))
print("language:", data.get('language'))
print("tags:", data.get('tags'))
print("description:", data.get('description', '')[:500])
transcript = data.get('transcript', {})
print("transcript available:", transcript.get('available'))
full_text = transcript.get('full_text', '')
print("transcript length:", len(full_text))
print("transcript (first 8000 chars):")
print(full_text[:8000])
