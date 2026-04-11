import json
with open('/Users/aanchalbhatia/Desktop/Aanchal/tlt/json-res/tara_by_mahesh_dattani_summary_in_hindi_-dz1jvj5qIE.json') as f:
    data = json.load(f)

d2 = {k:v for k,v in data.items() if k != 'transcript'}
print(json.dumps(d2, indent=2, ensure_ascii=False))
print('---TRANSCRIPT KEYS---')
print(list(data.get('transcript',{}).keys()))
full_text = data.get('transcript',{}).get('full_text','')
print('FULL_TEXT LENGTH:', len(full_text))
print('---FULL TEXT---')
print(full_text)
