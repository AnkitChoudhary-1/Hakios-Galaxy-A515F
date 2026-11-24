import json

lines = open(r"C:\Users\Ankit\.gemini\antigravity\brain\8f62b2de-af14-429e-b60e-1a5d09e1319a\.system_generated\logs\transcript.jsonl", "r", encoding="utf-8").readlines()
for i in range(5605, min(5631, len(lines))):
    d = json.loads(lines[i])
    print(f"[{i}] {d.get('source')}/{d.get('type')}: {str(d.get('content',''))[:250]}")
