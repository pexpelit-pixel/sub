import json, datetime, sys, os

def srt_time(sec):
    ms = int((sec - int(sec)) * 1000)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def json_to_srt(json_file, srt_file):
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    with open(srt_file, "w", encoding="utf-8") as out:
        for i, seg in enumerate(data.get("segments", []), 1):
            text = seg.get("text", "").strip()
            if not text:
                continue
            out.write(f"{i}\n")
            out.write(f"{srt_time(seg['start'])} --> {srt_time(seg['end'])}\n")
            out.write(f"{text}\n\n")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python transcribe.py result.json output.srt")
        sys.exit(1)
    json_to_srt(sys.argv[1], sys.argv[2])
