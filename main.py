"""
YouTube Shorts Auto-Generator — GitHub Actions Edition
=======================================================
Pipeline: Gemini (script) → Pexels (video) → Edge TTS (voice)
        → FFmpeg (assemble 1080×1920) → YouTube Data API (upload)

All secrets are injected as environment variables by GitHub Actions.
No API keys are ever stored in the code.
"""

import os, sys, json, csv, time, random, subprocess, tempfile, logging, requests
from datetime import datetime
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Secrets from environment (set in GitHub → Settings → Secrets) ─────────────
GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
PEXELS_API_KEY        = os.environ["PEXELS_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

TMP = Path(tempfile.gettempdir())

# ── Niche rotation ─────────────────────────────────────────────────────────────
# Picks a different niche each day based on the day of year for variety
NICHES = [
    {"topic": "psychology facts that will blow your mind",
     "tags": ["psychology","mentalhealth","facts","mindblowing","shorts","viral"],
     "pexels_query": "human mind psychology"},
    {"topic": "money and investing tips every beginner must know",
     "tags": ["money","finance","wealth","investing","shorts","viral"],
     "pexels_query": "money finance business success"},
    {"topic": "mind-blowing science facts most people don't know",
     "tags": ["science","facts","didyouknow","mindblowing","shorts"],
     "pexels_query": "science experiment laboratory"},
    {"topic": "surprising history facts they never taught you in school",
     "tags": ["history","facts","historyfacts","shorts","viral"],
     "pexels_query": "ancient history civilization"},
    {"topic": "AI and technology facts that seem unreal",
     "tags": ["ai","technology","tech","future","shorts","viral"],
     "pexels_query": "artificial intelligence technology futuristic"},
    {"topic": "productivity hacks to completely transform your life",
     "tags": ["productivity","lifehacks","motivation","shorts","success"],
     "pexels_query": "productivity workspace office success"},
    {"topic": "health and body facts you need to know right now",
     "tags": ["health","wellness","fitness","healthy","shorts"],
     "pexels_query": "health wellness nature fitness"},
    {"topic": "space and universe facts that are truly mind blowing",
     "tags": ["space","nasa","astronomy","universe","shorts"],
     "pexels_query": "space galaxy stars cosmos"},
    {"topic": "incredible animal facts you never knew existed",
     "tags": ["animals","nature","wildlife","facts","shorts"],
     "pexels_query": "wildlife animals nature"},
    {"topic": "simple cooking hacks that save time and money",
     "tags": ["cooking","food","recipe","hacks","shorts"],
     "pexels_query": "cooking kitchen food chef"},
    {"topic": "philosophy quotes that will change how you think",
     "tags": ["philosophy","wisdom","motivation","mindset","shorts"],
     "pexels_query": "sunset mountains peaceful nature"},
    {"topic": "bizarre geography facts about our incredible planet",
     "tags": ["geography","earth","nature","travel","shorts"],
     "pexels_query": "earth landscape aerial drone nature"},
]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 ── Generate script with Gemini 2.0 Flash (free: 250 req/day)
# ══════════════════════════════════════════════════════════════════════════════
def generate_script(niche: dict) -> dict:
    log.info(f"[1/5] Generating script  →  {niche['topic']}")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = f"""You are a world-class YouTube Shorts scriptwriter. Your videos regularly hit 1M+ views.

Write a 55-second script about: {niche['topic']}

RULES (follow exactly):
1. First sentence MUST be a shocking hook — use one of: "Did you know", "Most people never know", "Scientists just discovered"
2. Include exactly 5 specific, surprising facts — no filler, no vague statements
3. Final sentence MUST be exactly: "Follow for more!"
4. Word count: 110–130 words (critical — too many words = cuts off)
5. Write ONLY the spoken words — no labels, headers, or stage directions

Return ONLY a raw JSON object with no markdown, no code blocks, no extra text:
{{"title": "Catchy title under 60 chars, no hashtags", "script": "Full 110-130 word narration", "description": "100-150 word YouTube description packed with keywords"}}"""

    for attempt in range(3):
        resp = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.85,
                    "maxOutputTokens": 1024,
                },
            },
            timeout=30,
        )
        if resp.status_code == 429:
            log.info(f"  Rate limited, waiting 30s (attempt {attempt+1}/3)...")
            time.sleep(30)
            continue
        resp.raise_for_status()
        break

    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    # Strip any accidental markdown fences
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    data = json.loads(raw)

    log.info(f"  ✓ Title: {data['title']}")
    log.info(f"  ✓ Script words: {len(data['script'].split())}")
    return data


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 ── Fetch portrait stock video from Pexels (free, no watermark)
# ══════════════════════════════════════════════════════════════════════════════
def fetch_pexels_video(query: str) -> tuple:
    log.info(f"[2/5] Fetching stock video  →  '{query}'")

    headers = {"Authorization": PEXELS_API_KEY}
    fallbacks = [query, "nature aerial landscape", "abstract motion background"]

    for q in fallbacks:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": q, "per_page": 10, "orientation": "portrait",
                    "min_duration": 15, "max_duration": 90},
            timeout=15,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if videos:
            log.info(f"  ✓ Found {len(videos)} videos for '{q}'")
            break

    if not videos:
        raise RuntimeError("No Pexels videos found")

    # Pick randomly from top 5 so we get variety across days
    video = random.choice(videos[:5])

    # Prefer HD portrait file
    video_url = None
    for quality in ["hd", "sd", ""]:
        for f in video["video_files"]:
            portrait = f.get("width", 1) < f.get("height", 1)
            right_q  = not quality or f.get("quality") == quality
            if portrait and right_q and f.get("link"):
                video_url = f["link"]
                break
        if video_url:
            break
    if not video_url:
        video_url = video["video_files"][0]["link"]

    log.info(f"  ✓ Video selected (duration: {video['duration']}s)")
    return video_url, video["duration"]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 ── Generate voiceover with Microsoft Edge TTS (free, no key needed)
# ══════════════════════════════════════════════════════════════════════════════
def generate_voiceover(script: str) -> Path:
    log.info("[3/5] Generating voiceover  →  Edge TTS (en-US-AriaNeural)")

    audio_path  = TMP / "voiceover.mp3"
    script_path = TMP / "script.txt"

    clean = script.replace('"', "'").replace("\n", " ").strip()
    script_path.write_text(clean, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "edge_tts",
         "--voice", "en-US-AriaNeural",
         "--rate", "+8%",
         "--file", str(script_path),
         "--write-media", str(audio_path)],
        capture_output=True, text=True, timeout=90,
    )

    if result.returncode != 0 or not audio_path.exists():
        log.warning(f"  ⚠ edge-tts error: {result.stderr[:300]}")
        # Fallback: pass text directly (avoids file path issues)
        subprocess.run(
            [sys.executable, "-m", "edge_tts",
             "--voice", "en-US-AriaNeural",
             "--rate", "+8%",
             "--text", clean[:500],
             "--write-media", str(audio_path)],
            capture_output=True, timeout=90,
        )

    if not audio_path.exists():
        raise RuntimeError("Edge TTS failed — no audio file produced")

    size_kb = audio_path.stat().st_size // 1024
    log.info(f"  ✓ Audio: {size_kb} KB")
    return audio_path


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 ── Download stock video + assemble Short with FFmpeg
#           Output: 1080×1920, 30fps, H.264 + AAC — perfect for YouTube Shorts
# ══════════════════════════════════════════════════════════════════════════════
def assemble_short(video_url: str, audio_path: Path, title: str) -> Path:
    log.info("[4/5] Assembling Short  →  downloading video + FFmpeg")

    raw_video = TMP / "raw_video.mp4"
    output    = TMP / "final_short.mp4"

    # Download stock video
    log.info("  Downloading stock video...")
    with requests.get(video_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(raw_video, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
    log.info(f"  ✓ Downloaded: {raw_video.stat().st_size // (1024*1024)} MB")

    # Get audio duration for trimming the video correctly
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(audio_path)],
        capture_output=True, text=True, timeout=15,
    )
    try:
        duration = min(float(probe.stdout.strip()) + 1.0, 59.0)
    except ValueError:
        duration = 57.0
    log.info(f"  Target duration: {duration:.1f}s")

    # Escape title for FFmpeg drawtext filter
    safe_title = (title[:48]
                  .replace("\\", "\\\\")
                  .replace("'",  "\\'")
                  .replace(":",  "\\:")
                  .replace(",",  "\\,")
                  .replace("[",  "\\[")
                  .replace("]",  "\\]"))

    # FFmpeg filter chain:
    #   scale → crop to 1080×1920 (portrait / Shorts format)
    #   fade in 0.4s, fade out 0.8s
    #   white title text with black shadow for first 3.5s
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"fade=t=in:st=0:d=0.4,"
        f"fade=t=out:st={duration - 0.9:.2f}:d=0.8,"
        f"drawtext=text='{safe_title}':"
        f"fontsize=44:fontcolor=white:x=(w-text_w)/2:y=90:"
        f"shadowcolor=black@0.8:shadowx=2:shadowy=2:"
        f"enable='between(t,0,3.5)'"
    )

    log.info("  Running FFmpeg...")
    result = subprocess.run(
        ["ffmpeg", "-y",
         "-stream_loop", "-1",     # loop stock video if shorter than audio
         "-i", str(raw_video),
         "-i", str(audio_path),
         "-vf", vf,
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k",
         "-t", str(duration),
         "-shortest",
         "-movflags", "+faststart",
         "-pix_fmt", "yuv420p",
         str(output)],
        capture_output=True, text=True, timeout=300,
    )

    if result.returncode != 0:
        log.error(f"FFmpeg failed:\n{result.stderr[-3000:]}")
        raise RuntimeError("FFmpeg assembly failed")

    size_mb = output.stat().st_size / (1024 * 1024)
    log.info(f"  ✓ Short assembled: {size_mb:.1f} MB, {duration:.1f}s")
    return output


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 ── Upload to YouTube via Data API v3
#           Uses offline refresh token — no browser needed in CI
# ══════════════════════════════════════════════════════════════════════════════
def _get_access_token() -> str:
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id":     YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "refresh_token": YOUTUBE_REFRESH_TOKEN,
            "grant_type":    "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"Token refresh failed: {resp.text}")
    return token


def upload_to_youtube(video_path: Path, title: str,
                      description: str, tags: list, niche: dict) -> tuple:
    log.info("[5/5] Uploading to YouTube...")

    access_token = _get_access_token()
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    full_title = f"{title} #shorts"[:100]
    full_desc  = (
        f"{description}\n\n"
        f"#shorts #viral #trending #youtubeshorts "
        f"#{niche['topic'].split()[0]} #fyp #facts #reels"
    )
    all_tags = list(dict.fromkeys(
        ["shorts", "viral", "trending", "youtube shorts"] + tags
    ))[:20]

    metadata = {
        "snippet": {
            "title": full_title,
            "description": full_desc,
            "tags": all_tags,
            "categoryId": "22",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        },
    }

    file_size = video_path.stat().st_size

    # Initiate resumable upload session
    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={
            **auth_headers,
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        },
        json=metadata,
        timeout=30,
    )
    init.raise_for_status()
    upload_url = init.headers["Location"]

    # Upload in 5 MB chunks with progress logging
    CHUNK   = 5 * 1024 * 1024
    sent    = 0
    video_id = None

    with open(video_path, "rb") as fh:
        while sent < file_size:
            chunk_data = fh.read(CHUNK)
            end        = sent + len(chunk_data) - 1

            up = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes {sent}-{end}/{file_size}",
                    "Content-Type":  "video/mp4",
                },
                data=chunk_data,
                timeout=120,
            )
            sent += len(chunk_data)
            log.info(f"  Upload: {int(sent/file_size*100)}%")

            if up.status_code in (200, 201):
                video_id = up.json()["id"]
                break
            elif up.status_code == 308:
                continue
            else:
                raise RuntimeError(f"Upload failed {up.status_code}: {up.text}")

    if not video_id:
        raise RuntimeError("Upload completed but no video ID returned")

    yt_url = f"https://youtube.com/shorts/{video_id}"
    log.info(f"  ✓ Published: {yt_url}")
    return video_id, yt_url


# ══════════════════════════════════════════════════════════════════════════════
# Logging helper — writes CSV so GitHub Actions artifact is human-readable
# ══════════════════════════════════════════════════════════════════════════════
def log_result(date, title, niche, video_id, url, status):
    exists = Path("upload_log.csv").exists()
    with open("upload_log.csv", "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["Date","Title","Niche","VideoID","URL","Status"])
        w.writerow([date, title, niche, video_id, url, status])


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log.info("=" * 60)
    log.info(f"  YouTube Shorts Bot  |  {today} UTC")
    log.info("=" * 60)

    # Rotate niche by day of year so we never repeat on back-to-back days
    day_index = datetime.utcnow().timetuple().tm_yday % len(NICHES)
    niche = NICHES[day_index]
    log.info(f"  Niche ({day_index+1}/{len(NICHES)}): {niche['topic']}\n")

    try:
        script_data          = generate_script(niche)
        video_url, _         = fetch_pexels_video(niche["pexels_query"])
        audio_path           = generate_voiceover(script_data["script"])
        final_video          = assemble_short(video_url, audio_path, script_data["title"])
        video_id, yt_url     = upload_to_youtube(
            final_video,
            script_data["title"],
            script_data["description"],
            niche["tags"],
            niche,
        )

        log_result(today, script_data["title"], niche["topic"], video_id, yt_url, "SUCCESS")

        # Cleanup /tmp
        for p in [audio_path, TMP/"raw_video.mp4", final_video, TMP/"script.txt"]:
            try: Path(p).unlink(missing_ok=True)
            except: pass

        log.info("\n" + "=" * 60)
        log.info(f"  ✅  SUCCESS  →  {yt_url}")
        log.info("=" * 60)

    except Exception as exc:
        log.error(f"\n  ❌  PIPELINE FAILED: {exc}", exc_info=True)
        log_result(today, "FAILED", niche["topic"], "", "", f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
