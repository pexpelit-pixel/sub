import os, sys, json, subprocess, srt, shutil
from datetime import timedelta
from groq import Groq  # pip install groq
from googletrans import Translator  # pip install googletrans==4.0.0-rc1

# ===================== API Key Groq =====================
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

def download_video(url, out):
    run(["curl", "-L", url, "-o", out])

def extract_audio(video, out_wav, out_mp3):
    run([FFMPEG, "-y", "-i", video, "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", out_wav])
    run([FFMPEG, "-y", "-i", out_wav, "-b:a", "64k", out_mp3])

# ===================== WHISPER =====================
def whisper_transcribe(audio, out_json):
    import requests
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    with open(audio, "rb") as f:
        r = requests.post(url,
                          headers={"Authorization": f"Bearer {API_KEY}"},
                          files={"file": (os.path.basename(audio), f, "audio/mpeg")},
                          data={"model": "whisper-large-v3-turbo", "response_format": "verbose_json"})
    r.raise_for_status()
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(r.text)

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

# ===================== Google Translate block-by-block =====================
def translate_srt(in_srt, out_srt):
    translator = Translator()
    subs = list(srt.parse(open(in_srt, encoding="utf-8").read()))
    translated_subs = []

    for i, sub in enumerate(subs, start=1):
        # Translate block by block
        translated_text = translator.translate(sub.content, src='ja', dest='en').text
        sub.content = translated_text.strip()
        translated_subs.append(sub)

        if i % 10 == 0:
            print(f"🔹 Translated {i}/{len(subs)} subtitles...")

    with open(out_srt, "w", encoding="utf-8") as f:
        f.write(srt.compose(translated_subs))

# ===================== Hardcode & Upload =====================
def hardcode_sub(video, srtfile, outmp4):
    srt_path = os.path.abspath(srtfile).replace(":", "\\:")
    run([
        FFMPEG,"-y","-i",video,
        "-vf",f"subtitles={srt_path}:force_style='Alignment=2,Fontsize=20'",
        "-c:a","copy", outmp4
    ])

def upload_catbox(file):
    import requests
    url = "https://catbox.moe/user/api.php"
    with open(file, "rb") as f:
        r = requests.post(url, data={"reqtype":"fileupload"}, files={"fileToUpload":f})
    r.raise_for_status()
    return r.text.strip()

def process_video(url):
    base = os.path.splitext(os.path.basename(url))[0]
    print(f"\n🎬 Processing {base}")
    mp4 = f"{base}.mp4"
    wav = f"{base}.wav"
    mp3 = f"{base}_c.mp3"
    jpn_json = f"{base}.json"
    jpn_srt = f"{base}.srt"
    eng_srt = f"{base}_en.srt"
    outmp4 = f"{base}_sub.mp4"
    txt_log = "uploaded_links.txt"

    download_video(url, mp4)
    extract_audio(mp4, wav, mp3)
    whisper_transcribe(mp3, jpn_json)
    json_to_srt(jpn_json, jpn_srt)
    translate_srt(jpn_srt, eng_srt)
    hardcode_sub(mp4, eng_srt, outmp4)

    link = upload_catbox(outmp4)
    print(f"✅ Uploaded: {link}")

    # Tulis TXT log dengan komentar nama video
    with open(txt_log, "a", encoding="utf-8") as f:
        f.write(f"Video: {base}\nLink: {link}\n\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process.py video.txt")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        for url in f:
            url = url.strip()
            if url:
                process_video(url)
