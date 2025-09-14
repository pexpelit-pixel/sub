import os, sys, json, subprocess, requests, srt, shutil
from datetime import timedelta

API_KEY = "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"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def get_ffmpeg_path():
    # Cari ffmpeg di PATH
    path = shutil.which("ffmpeg")
    if path:
        return path
    # fallback ke lokasi manual
    if os.path.exists("/usr/local/bin/ffmpeg"):
        return "/usr/local/bin/ffmpeg"
    raise FileNotFoundError("❌ ffmpeg tidak ditemukan di PATH atau /usr/local/bin")

FFMPEG = get_ffmpeg_path()

def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)

def download_video(url, out):
    run(["curl", "-L", url, "-o", out])

def extract_audio(video, out_wav, out_mp3):
    run([FFMPEG, "-y", "-i", video, "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", out_wav])
    run([FFMPEG, "-y", "-i", out_wav, "-b:a", "64k", out_mp3])

def whisper_transcribe(audio, out_json):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    with open(audio, "rb") as f:
        r = requests.post(url, headers=HEADERS, files={
            "file": (os.path.basename(audio), f, "audio/mpeg")
        }, data={"model":"whisper-large-v3-turbo","response_format":"verbose_json"})
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

def translate_srt(in_srt, out_srt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    text = open(in_srt, encoding="utf-8").read()
    payload = {
        "model": "gpt-oss-20b",
        "messages": [
            {"role": "system", "content": "Translate Japanese subtitles to natural English, keeping exact SRT format (indexes, timestamps)."},
            {"role": "user", "content": text}
        ]
    }
    r = requests.post(url, headers={**HEADERS, "Content-Type":"application/json"}, json=payload)
    r.raise_for_status()
    result = r.json()
    translated = result["choices"][0]["message"]["content"]
    with open(out_srt, "w", encoding="utf-8") as f:
        f.write(translated)

def hardcode_sub(video, srtfile, outmp4):
    run([
        FFMPEG,"-y","-i",video,
        "-vf",f"subtitles={srtfile}:force_style='Alignment=2,Fontsize=20'",
        "-c:a","copy", outmp4
    ])

def upload_catbox(file):
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

    download_video(url, mp4)
    extract_audio(mp4, wav, mp3)
    whisper_transcribe(mp3, jpn_json)
    json_to_srt(jpn_json, jpn_srt)
    translate_srt(jpn_srt, eng_srt)
    hardcode_sub(mp4, eng_srt, outmp4)

    # Upload hasil ke Catbox
    link = upload_catbox(outmp4)
    print(f"✅ Uploaded: {link}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process.py video.txt")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        for url in f:
            url = url.strip()
            if url:
                process_video(url)
