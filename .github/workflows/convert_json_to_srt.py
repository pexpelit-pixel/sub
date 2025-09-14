import json, srt, sys
from datetime import timedelta

base = sys.argv[1]
data = json.load(open(f"{base}.json"))
segments = []
for i, seg in enumerate(data.get("segments", []), start=1):
    start = timedelta(seconds=seg["start"])
    end = timedelta(seconds=seg["end"])
    text = seg["text"].strip()
    segments.append(srt.Subtitle(index=i, start=start, end=end, content=text))

with open(f"{base}.srt", "w", encoding="utf-8") as f:
    f.write(srt.compose(segments))
