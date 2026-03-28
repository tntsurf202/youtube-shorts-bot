# 🎬 YouTube Shorts Auto-Bot — GitHub Actions

Fully automated YouTube Shorts pipeline. Runs free forever on GitHub Actions.
Uploads one Short per day — script, voiceover, video assembly, and upload all automated.

**Stack (100% free, no payment info needed):**
| Step | Tool | Cost |
|------|------|------|
| Script writing | Google Gemini 2.0 Flash API | Free (250 req/day) |
| Stock video | Pexels API | Free (unlimited) |
| Voiceover | Microsoft Edge TTS | Free (unlimited) |
| Video assembly | FFmpeg (in GitHub runner) | Free |
| Upload | YouTube Data API v3 | Free (10k units/day) |
| Scheduling | GitHub Actions cron | Free (unlimited on public repos) |

---

## ⚡ Setup — 6 Steps

### Step 1 — Get Your API Keys

#### A) Gemini API Key
1. Go to **https://aistudio.google.com**
2. Click **Get API Key** → **Create API key**
3. Copy the key — you'll add it to GitHub Secrets later

#### B) Pexels API Key
1. Go to **https://www.pexels.com/api/**
2. Sign up for a free account and verify your email
3. Your API key is shown on the dashboard — copy it

#### C) YouTube OAuth Credentials
1. Go to **https://console.cloud.google.com**
2. Create a new project → name it `yt-shorts-bot`
3. Go to **APIs & Services → Enable APIs** → search `YouTube Data API v3` → Enable
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Desktop app** → name it anything → click Create
6. Note your **Client ID** and **Client Secret**

---

### Step 2 — Get Your YouTube Refresh Token (run once, locally)

Install the required library on your computer:
```bash
pip install google-auth-oauthlib
```

Open `get_refresh_token.py` and paste in your Client ID and Client Secret, then run it:
```bash
python get_refresh_token.py
```

A browser window will open → log into your YouTube channel → click **Allow**.

The script prints your **refresh token** — copy it. This token never expires and you'll never need to run this again.

---

### Step 3 — Create Your GitHub Repository

1. Go to **https://github.com/new**
2. Name it `youtube-shorts-bot`
3. Set it to **Public** ← important! This makes Actions completely free and unlimited
4. Click **Create repository**

Upload all the files from this folder to your new repo:
- `main.py`
- `requirements.txt`
- `.gitignore`
- `get_refresh_token.py` *(optional — you already have your token)*
- `.github/workflows/daily_upload.yml`

The easiest way if you're a beginner:
```bash
cd yt-shorts-github
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/youtube-shorts-bot.git
git push -u origin main
```

---

### Step 4 — Add Your Secrets to GitHub

1. In your GitHub repo, go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** for each of these:

| Secret Name | Value |
|-------------|-------|
| `GEMINI_API_KEY` | Your Gemini API key from Step 1A |
| `PEXELS_API_KEY` | Your Pexels API key from Step 1B |
| `YOUTUBE_CLIENT_ID` | Your OAuth Client ID from Step 1C |
| `YOUTUBE_CLIENT_SECRET` | Your OAuth Client Secret from Step 1C |
| `YOUTUBE_REFRESH_TOKEN` | The token from Step 2 |

> Secrets are encrypted. Even you can't read them back after saving — they're only injected into the workflow at runtime.

---

### Step 5 — Do a Test Run

1. In your repo, click the **Actions** tab
2. Click **🎬 YouTube Shorts Daily Upload** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Watch the logs in real time — the whole pipeline takes about 5–8 minutes
5. Check your **YouTube Studio** to confirm the video is live

---

### Step 6 — Confirm the Daily Schedule

The workflow is already set to run at **12:00 UTC every day** (that's 5:30 PM IST).

To change the time, edit `.github/workflows/daily_upload.yml` and update this line:
```yaml
- cron: "0 12 * * *"
```
Use https://crontab.guru to pick your preferred time.

> **Note:** GitHub Actions cron may run up to 15 minutes late during busy periods — this is normal.

---

## 📊 Monitoring

**See every run:**
Go to your repo → **Actions** tab → click any run to see full logs

**Download the upload log:**
Each run uploads a `upload_log.csv` as an artifact — click the run → scroll down to Artifacts to download it

**Re-run a failed job:**
Actions tab → click the failed run → **Re-run failed jobs**

---

## 🔧 Customising

**Change upload time:**
Edit `cron: "0 12 * * *"` in the workflow file

**Add or change niches:**
Edit the `NICHES` list in `main.py` — each entry has a `topic`, `tags`, and `pexels_query`

**Change the voice:**
In `main.py`, change `en-US-AriaNeural` to any Edge TTS voice.
See all voices: `python -m edge_tts --list-voices`

**Upload more than once a day:**
Add more cron lines to the workflow:
```yaml
schedule:
  - cron: "0 6 * * *"   # 6am UTC
  - cron: "0 12 * * *"  # 12pm UTC
  - cron: "0 18 * * *"  # 6pm UTC
```

---

## ❓ Troubleshooting

**"GEMINI_API_KEY not set"**
→ Double-check you added all 5 secrets in GitHub Settings → Secrets

**"FFmpeg failed"**
→ Check the Actions log for the full error. Usually means the Pexels video URL expired — re-run the workflow

**"Token refresh failed"**
→ Your YouTube refresh token may have been revoked. Re-run `get_refresh_token.py` locally and update the GitHub secret

**"YouTube quota exceeded"**
→ The YouTube Data API resets at midnight Pacific time. The workflow will succeed tomorrow automatically

**Workflow not running at scheduled time**
→ GitHub Actions cron only triggers if the repo has had a push in the last 60 days. If your repo goes quiet, just make a small edit to any file to keep it active

---

## 💰 Free Tier Summary

| Service | Free Limit | Daily Usage | Status |
|---------|-----------|-------------|--------|
| GitHub Actions | Unlimited (public repo) | ~8 min/day | ✅ Free forever |
| Gemini API | 250 req/day | 1 req/day | ✅ Free forever |
| Pexels API | Unlimited | 1 req/day | ✅ Free forever |
| Edge TTS | Unlimited | 1 req/day | ✅ Free forever |
| YouTube Data API | 10,000 units/day | ~1,600 units/day | ✅ Free forever |

No credit card. No payment info. No hidden costs.
