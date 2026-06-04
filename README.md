# Agentic Podcast Generator

> **Automatically generate, narrate, and publish a daily data-driven podcast using Claude, ElevenLabs, and Spotify — with zero human intervention.**

A fully automated pipeline that fetches live data from any source, generates a spoken briefing script using Claude Sonnet (with real-time web search for context), synthesizes audio with ElevenLabs TTS, and publishes to Spotify every morning via headless browser automation running on an AWS EC2 server.

Built as a general framework. The included examples cover weather and prediction markets, but the pattern works for any domain: financial data, sports, research, product analytics, news — anything that produces structured daily data.

---

## Architecture

```
Your Data Source      →  Fetch structured daily data (any API)
      ↓
Claude Sonnet         →  Generate spoken script + web search for context
      ↓
ElevenLabs TTS        →  Synthesize audio (your voice or built-in)
      ↓
pydub                 →  Stitch intro jingle + speech
      ↓
Playwright            →  Automated Spotify upload (headless Chromium)
      ↓
Spotify               →  Published episode, every morning at 7am
```

---

## Quick start (local)

```bash
git clone https://github.com/sfrbuilds/agentic-podcast
cd agentic-podcast
pip install -r requirements.txt
brew install ffmpeg        # macOS — needed for audio stitching

cp .env.example .env       # fill in your API keys
python3 generate_episode.py
```

Out of the box this runs the **weather briefing** example — no data API key needed (uses [Open-Meteo](https://open-meteo.com), free and open). To switch to a different data source, change one import line at the top of `generate_episode.py`.

The script pauses twice for human review — once after generating the script, once after generating the audio — before uploading. Safe to run interactively while you're iterating. Once you're happy with the output, deploy to EC2 and let the cron job take over.

---

## Setup

### API keys

Copy `.env.example` to `.env` and fill in:

| Variable | Where to get it | Required |
|----------|----------------|----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Yes |
| `ELEVENLABS_API_KEY` | [elevenlabs.io](https://elevenlabs.io) | Yes |
| `ELEVENLABS_VOICE_ID` | See voice setup below | Yes |
| `SPOTIFY_SHOW_ID` | From your Spotify for Creators URL | For upload |
| `DATA_API_KEY` | Your data source API key | Depends on source |

### Spotify show setup

1. Create a show at [creators.spotify.com](https://creators.spotify.com)
2. Copy your show ID from the URL: `creators.spotify.com/pod/show/YOUR_SHOW_ID/home`
3. Set `SPOTIFY_SHOW_ID=YOUR_SHOW_ID` in `.env`
4. Run the one-time session login:
   ```bash
   playwright install chromium
   python3 save_spotify_session.py
   ```
   A browser opens — log in, press Enter. Session persists for weeks.

---

## Voice setup

### Option A: Built-in ElevenLabs voice (easiest)

No extra setup. Pick from ElevenLabs' library and paste the voice ID into `.env`.

Good options for a professional briefing style:

| Voice | ID | Character |
|-------|----|-----------|
| **Brian** | `nPczCjzI2devNBz1zQrb` | American, deep, resonant **(default)** |
| Daniel | `onwK4e9ZLuTAKqWW03F9` | British, broadcaster style |
| Adam | `pNInz6obpgDQGcFmaJgB` | American, authoritative |

### Option B: Clone your own voice

1. Go to [elevenlabs.io/app/voice-lab](https://elevenlabs.io/app/voice-lab)
2. Click **Add Voice → Instant Voice Clone**
3. Upload 1-3 minutes of clean audio of yourself speaking naturally (no background noise)
4. Copy the resulting voice ID → paste into `.env` as `ELEVENLABS_VOICE_ID`

> Instant Voice Clone requires ElevenLabs Creator plan ($22/mo). Recommended voice settings are already tuned in the script for cloned voices.

---

## Adapting to your data source

Each data source lives in `data_sources/` as a self-contained Python file.
To switch domains, change **one import line** at the top of `generate_episode.py`:

```python
# Default — weather briefing (no API key needed)
from data_sources.example_weather import fetch_data, PODCAST_NAME, PROMPT_TEMPLATE

# Swap to prediction markets
# from data_sources.example_markets import fetch_data, PODCAST_NAME, PROMPT_TEMPLATE

# Or write your own in data_sources/my_domain.py
# from data_sources.my_domain import fetch_data, PODCAST_NAME, PROMPT_TEMPLATE
```

To write your own, create a file in `data_sources/` with three exports:

```python
# data_sources/my_domain.py

PODCAST_NAME = "My Daily Briefing"

PROMPT_TEMPLATE = """\
You are producing "{podcast_name}" — a 90-second daily briefing.
Today: {{today}} | Episode: #{{ep_num}}
Data: {{data}}
Return JSON with: title, script, description, items_referenced.
"""  # Note: use {{double braces}} for today/data — single braces are for podcast_name only

def fetch_data() -> dict:
    # Return any dict — it gets passed to Claude as context
    return requests.get("https://your-api.com/data").json()
```

See `data_sources/README.md` for more examples and the full interface spec.

---

## Generating an intro jingle

Add a short 2-3 second audio signature before each episode using the ElevenLabs Sound Effects API:

```python
import requests, os

prompts = [
    "two quick keyboard clicks then a single soft chime, minimal and clean",
    "short punchy news intro, three ascending electronic tones",
    "single clean electric piano chord, bright, short decay",
]

for i, prompt in enumerate(prompts, 1):
    r = requests.post(
        "https://api.elevenlabs.io/v1/sound-generation",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={"text": prompt, "duration_seconds": 2.0, "prompt_influence": 0.5},
    )
    with open(f"jingle_{i}.mp3", "wb") as f:
        f.write(r.content)

# Pick your favourite, then:
# cp jingle_1.mp3 intro_jingle.mp3
```

Save your chosen jingle as `intro_jingle.mp3` in the project directory. It auto-stitches before every episode.

---

## Production deployment on AWS EC2

Running `generate_episode.py` locally works for testing, but for a truly
automated daily podcast you need an always-on server with a cron job.
Here's the full path from zero to a daily episode publishing itself every morning.

### 1. Launch an EC2 instance

1. Sign in to [console.aws.amazon.com](https://console.aws.amazon.com) → **EC2 → Launch instance**
2. **Name:** `podcast-server` (or whatever you like)
3. **AMI:** Amazon Linux 2023 (free tier eligible, works well)
4. **Instance type:** `t3.micro` (~$8/mo) — plenty for this workload
5. **Key pair:** Create a new key pair, download the `.pem` file, save it somewhere safe (e.g. `~/Downloads/podcast-key.pem`)
6. **Security group:** Allow inbound SSH (port 22) from your IP only
7. **Storage:** Default 8GB is fine
8. Click **Launch instance**

Once it's running, note the **Public IPv4 address** from the EC2 console.

```bash
# Fix key permissions (required by SSH)
chmod 400 ~/Downloads/podcast-key.pem

# Connect
ssh -i ~/Downloads/podcast-key.pem ec2-user@YOUR_EC2_IP
```

### 2. Install dependencies

```bash
# Update system packages
sudo dnf update -y

# Python packages
pip3 install anthropic requests python-dotenv pydub

# Playwright + Chromium (for Spotify upload)
pip3 install playwright
playwright install chromium
playwright install-deps chromium

# Verify Chromium works headlessly (important — not all servers support it)
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    print('Chromium OK:', b.version)
    b.close()
"

# ffmpeg (for audio stitching)
sudo dnf install ffmpeg -y
```

> **Note:** If the Chromium test fails with a missing library error, run
> `playwright install-deps chromium` again and check the error message. On
> Amazon Linux you may also need `sudo dnf install atk cups-libs gtk3 -y`.

### 3. Upload the project

```bash
# From your Mac — upload the whole project to the server
scp -i ~/Downloads/podcast-key.pem -r \
  /path/to/agentic-podcast \
  ec2-user@YOUR_EC2_IP:~/agentic-podcast
```

### 4. Configure credentials on the server

```bash
# SSH into server
ssh -i ~/Downloads/podcast-key.pem ec2-user@YOUR_EC2_IP

cd ~/agentic-podcast
cp .env.example .env
nano .env   # fill in ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, etc.
```

### 5. Set up the Spotify session (one-time, from your Mac)

The Spotify upload uses a saved browser session. You generate it once on
your Mac (where you can see the browser), then copy it to the server.
You will need to repeat this every few weeks when the session expires.

```bash
# On your Mac — run the login helper
cd /path/to/agentic-podcast
python3 save_spotify_session.py
# A browser opens. Log into Spotify for Creators. Press Enter when done.

# Copy the session file to the server
scp -i ~/Downloads/podcast-key.pem \
  spotify_session.json \
  ec2-user@YOUR_EC2_IP:~/agentic-podcast/spotify_session.json
```

### 6. Test a full run on the server

```bash
# SSH in and do a dry run with --auto to skip the interactive prompts
ssh -i ~/Downloads/podcast-key.pem ec2-user@YOUR_EC2_IP

cd ~/agentic-podcast
mkdir -p logs
python3 generate_episode.py --auto
```

Check that an episode appears in your Spotify for Creators dashboard before setting up the cron job.

### 7. Set up the cron job

```bash
# On the server — open crontab
crontab -e

# Add these two lines (runs at 7am Eastern, every day):
CRON_TZ=America/New_York
0 7 * * * cd ~/agentic-podcast && python3 generate_episode.py --auto >> ~/agentic-podcast/logs/podcast.log 2>&1
```

Verify it was saved:
```bash
crontab -l
```

### 8. Monitor

```bash
# Check today's log
tail -50 ~/agentic-podcast/logs/podcast.log

# Check the episode counter (increments each day)
cat ~/agentic-podcast/episode_count.txt

# Watch logs live (useful after first scheduled run)
tail -f ~/agentic-podcast/logs/podcast.log
```

### 9. Get email alerts on failure (optional but recommended)

Add this to your crontab so you get an email if the episode fails:

```bash
MAILTO=you@youremail.com
CRON_TZ=America/New_York
0 7 * * * cd ~/agentic-podcast && python3 generate_episode.py --auto >> ~/agentic-podcast/logs/podcast.log 2>&1 || echo "Episode failed — check ~/agentic-podcast/logs/podcast.log" | mail -s "Podcast failed" you@youremail.com
```

Or add a simple check at the end of the cron command that pings you on Slack/Discord via webhook if the exit code is non-zero.

### 10. Updating the code

When you make changes locally and want to deploy them to the server:

```bash
# From your Mac — sync only changed files
scp -i ~/Downloads/podcast-key.pem \
  generate_episode.py data_sources/my_domain.py \
  ec2-user@YOUR_EC2_IP:~/agentic-podcast/

# Or sync the whole project (excludes .env and session files)
rsync -av --exclude='.env' --exclude='spotify_session.json' \
  --exclude='*.mp3' --exclude='logs/' \
  -e "ssh -i ~/Downloads/podcast-key.pem" \
  /path/to/agentic-podcast/ \
  ec2-user@YOUR_EC2_IP:~/agentic-podcast/
```

### Session refresh

When the Spotify session expires (every few weeks), the log will show:
```
Session fully expired. Run: python3 save_spotify_session.py
```

Fix it in 2 minutes from your Mac:

```bash
python3 save_spotify_session.py   # log in when browser opens

scp -i ~/Downloads/podcast-key.pem \
  spotify_session.json \
  ec2-user@YOUR_EC2_IP:~/agentic-podcast/spotify_session.json
```

### Cost summary

| Item | Cost |
|------|------|
| EC2 t3.micro | ~$8/mo |
| Claude Sonnet (~0.08/episode × 30) | ~$2.50/mo |
| ElevenLabs Creator plan | $22/mo |
| Web search (~3 searches/episode) | ~$0.90/mo |
| **Total** | **~$33/mo** |

That's a fully automated daily podcast for about $1/day.

---

## Project structure

```
agentic-podcast/
├── generate_episode.py          # Main pipeline — domain-agnostic core
├── spotify_upload.py            # Playwright Spotify upload module
├── save_spotify_session.py      # One-time Spotify browser login (run on Mac)
├── data_sources/
│   ├── example_weather.py       # Default example — weather briefing (no API key)
│   ├── example_markets.py       # Example — prediction markets via Veynor API
│   └── README.md                # How to write your own data source
├── intro_jingle.mp3             # Intro sound (not tracked in git)
├── spotify_session.json         # Browser session cache (not tracked)
├── episode_count.txt            # Persistent episode counter (not tracked)
├── recent_topics.json           # Repeat-prevention memory (not tracked)
├── logs/                        # Cron job output (not tracked)
├── .env                         # Your credentials (not tracked)
├── .env.example                 # Credential template
├── requirements.txt
└── README.md
```

---

## How the script generation works

Claude Sonnet receives your structured data and a prompt describing the format. Before writing the script, it runs 2-3 web searches to understand *why* the data looks the way it does — adding real-world context that makes the episode sound like a human who read the news, not a ticker readout.

The web search integration uses Anthropic's built-in `web_search` tool ([$10/1000 searches](https://platform.claude.com/docs/about-claude/pricing)). You can disable it to reduce latency and cost:

```python
# In .env
USE_WEB_SEARCH=false
```

---

## Cost estimate (API only, per episode)

| Service | Usage | Cost |
|---------|-------|------|
| Claude Sonnet | ~2,000 input + ~600 output tokens | ~$0.03 |
| Web search | 2-3 searches | ~$0.03 |
| ElevenLabs | ~250 words (~1,500 chars) | ~$0.03 |
| **Total** | | **~$0.09/episode** |

Monthly at daily cadence: **~$2.50/month** in API costs (not counting ElevenLabs plan or EC2).

---

## License

MIT. Fork it, build your own automated voice, ship something.

---

*Built by [@sfrbuilds](https://github.com/sfrbuilds)*
