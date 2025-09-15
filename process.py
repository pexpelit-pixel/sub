import os, sys, json, subprocess, srt, shutil
from datetime import timedelta
from groq import Groq  # pip install groq

API_KEY = "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"
client = Groq(api_key=API_KEY)

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

# ===================== chunk split translate =====================
def chunk_text(text, max_tokens=5000):
    """
    Split text into chunks safely under max_tokens (approx)
    """
    lines = text.splitlines()
    chunks = []
    current = []
    tokens = 0
    for line in lines:
        line_tokens = len(line.split())  # rough token approx
        if tokens + line_tokens > max_tokens and current:
            chunks.append("\n".join(current))
            current = []
            tokens = 0
        current.append(line)
        tokens += line_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks

def translate_srt(in_srt, out_srt):
    text = open(in_srt, encoding="utf-8").read()
    chunks = chunk_text(text, max_tokens=5000)
    translated_chunks = []

    for i, chunk in enumerate(chunks, start=1):
        print(f"🔹 Translating chunk {i}/{len(chunks)}...")
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Translate Japanese subtitles to natural English. Keep exact SRT format (indexes, timestamps)."},
                {"role": "user", "content": chunk}
            ],
            temperature=0.7,
            max_completion_tokens=8192,
            top_p=1,
            stream=True
        )
        translated = []
        for delta in completion:
            if delta.choices[0].delta.content:
                translated.append(delta.choices[0].delta.content)
        translated_chunks.append("".join(translated))

    # gabungkan semua chunk
    result_text = "\n".join(translated_chunks)
    with open(out_srt, "w", encoding="utf-8") as f:
        f.write(result_text)

# ===================== hardcode & upload =====================
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

    download_video(url, mp4)
    extract_audio(mp4, wav, mp3)
    whisper_transcribe(mp3, jpn_json)
    json_to_srt(jpn_json, jpn_srt)
    translate_srt(jpn_srt, eng_srt)
    hardcode_sub(mp4, eng_srt, outmp4)

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
