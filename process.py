import os, sys, json, subprocess, srt, shutil, time, requests
from datetime import timedelta
from groq import Groq  # pip install groq

# ===================== API =====================
API_KEY = "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"
client = Groq(api_key=API_KEY)

# ===================== FFMPEG =====================
def get_ffmpeg_path():
    path = shutil.which("ffmpeg")
    if path:
        return path
    if os.path.exists("/usr/local/bin/ffmpeg"):
        return "/usr/local/bin/ffmpeg"
    raise FileNotFoundError("❌ ffmpeg tidak ditemukan")

FFMPEG = get_ffmpeg_path()

def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)

# ===================== Download & Extract =====================
def download_video(url, out):
    run(["curl", "-L", url, "-o", out])

def extract_audio(video, out_wav, out_mp3):
    run([FFMPEG, "-y", "-i", video, "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", out_wav])
    run([FFMPEG, "-y", "-i", out_wav, "-b:a", "64k", out_mp3])

# ===================== Whisper (Groq) =====================
def whisper_transcribe(audio, out_json):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    with open(audio, "rb") as f:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"file": (os.path.basename(audio), f, "audio/mpeg")},
            data={"model": "whisper-large-v3-turbo", "response_format": "verbose_json"}
        )
    r.raise_for_status()
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(r.text)

# ===================== JSON → SRT =====================
def json_to_srt(json_file, out_srt):
    data = json.load(open(json_file))
    subs = []
    for i, seg in enumerate(data.get("segments", []), start=1):
        subs.append(srt.Subtitle(
            index=i,
            start=timedelta(seconds=seg["start"]),
            end=timedelta(seconds=seg["end"]),
            content=seg["text"].strip()
        ))
    with open(out_srt, "w", encoding="utf-8") as f:
        f.write(srt.compose(subs))

# ===================== Google Translate =====================
def google_translate(text, source="ja", target="en"):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": text,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        return "".join([t[0] for t in result[0]])
    except Exception as e:
        print(f"❌ Translate error: {e}")
        return text

def translate_srt(in_srt, out_srt, delay=1.0):
    subs = list(srt.parse(open(in_srt, encoding="utf-8").read()))
    translated_subs = []

    for i, sub in enumerate(subs, start=1):
        try:
            sub.content = google_translate(sub.content, "ja", "en")
        except Exception as e:
            print(f"⚠️ Error at line {i}: {e}")
        translated_subs.append(sub)

        if i % 10 == 0:
            print(f"🔹 Translated {i}/{len(subs)} subtitles...")

        time.sleep(delay)  # biar ga ke-limit

    with open(out_srt, "w", encoding="utf-8") as f:
        f.write(srt.compose(translated_subs))

# ===================== Hardcode Subtitle =====================
def hardcode_sub(video, srtfile, outmp4):
    srt_path = os.path.abspath(srtfile).replace(":", "\\:")
    run([
        FFMPEG,"-y","-i",video,
        "-vf",f"subtitles={srt_path}:force_style='Alignment=2,Fontsize=20'",
        "-c:a","copy", outmp4
    ])

# ===================== Upload Catbox =====================
def upload_catbox(file):
    url = "https://catbox.moe/user/api.php"
    with open(file, "rb") as f:
        r = requests.post(url, data={"reqtype":"fileupload"}, files={"fileToUpload":f})
    r.raise_for_status()
    return r.text.strip()

# ===================== Main Flow =====================
def process_video(url, delay=1.0):
    base = os.path.splitext(os.path.basename(url))[0]
    print(f"\n🎬 Processing {base}")
    mp4 = f"{base}.mp4"
    wav = f"{base}.wav"
    mp3 = f"{base}_c.mp3"
    jpn_json = f"{base}.json"
    jpn_srt = f"{base}.srt"
    eng_srt = f"{base}_en.srt"
    outmp4 = f"{base}_sub.mp4"

    download_video(url, mp4)
    extract_audio(mp4, wav, mp3)
    whisper_transcribe(mp3, jpn_json)
    json_to_srt(jpn_json, jpn_srt)
    translate_srt(jpn_srt, eng_srt, delay=delay)
    hardcode_sub(mp4, eng_srt, outmp4)

    link = upload_catbox(outmp4)
    print(f"✅ Uploaded: {link}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process.py video.txt [delay]")
        sys.exit(1)

    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    with open(sys.argv[1]) as f:
        for url in f:
            url = url.strip()
            if url:
                process_video(url, delay=delay)
