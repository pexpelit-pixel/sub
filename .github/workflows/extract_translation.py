import json, sys
base = sys.argv[1]
out = json.load(open(f"{base}_en.json"))
text = out["choices"][0]["message"]["content"]
with open(f"{base}_en.srt", "w", encoding="utf-8") as f:
    f.write(text)
