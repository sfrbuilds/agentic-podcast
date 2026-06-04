# Agentic Podcast Generator

> **Automatically generate, narrate, and publish a daily data-driven podcast using Claude, ElevenLabs, and Spotify — with zero human intervention.**

A fully automated pipeline that fetches live data from any source, generates a spoken briefing script using Claude Sonnet (with real-time web search for context), synthesizes audio with ElevenLabs TTS, and publishes to Spotify every morning via headless browser automation.

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
Spotify               →  Published episode, every morning
```

---

## Quick start

```bash
git clone https://github.com/sfrbuilds/agentic-podcast
cd agentic-podcast
pip install -r requirements.txt
brew install ffmpeg        # macOS — needed for audio stitching

cp .env.example .env       # fill in your API keys
python3 generate_episode.py
```

Out of the box this runs the **weather briefing** example — no data API key needed (uses [Open-Meteo](https://open-meteo.com), free and open). To switch to a different data source, change one import line at the top of `generate_episode.py`.

The script pauses twice for human review — once after generating the script, once after generating the audio — before uploading. Safe to run interactively while you're iterating.

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

The data fetching section in `generate_episode.py` is intentionally isolated. Replace it with your own:

```python
# ── REPLACE THIS with your data source ────────────────────────────────────────

def fetch_data() -> dict:
    """
    Return a dict of structured data to pass to Claude.
    Examples:
      - Financial: stock prices, earnings, economic indicators
      - Sports: scores, standings, betting odds
      - News: top headlines with metadata
      - Research: paper abstracts, citation counts
      - Analytics: your product's daily metrics
    """
    # Example: fetch from a REST API
    response = requests.get(
        "https://your-api.com/daily-data",
        headers={"Authorization": f"Bearer {os.environ['DATA_API_KEY']}"},
    )
    return response.json()

# ─────────────────────────────────────────────────────────────────────────────
```

Then update the Claude prompt in `generate_episode.py` to describe your domain and what a good episode sounds like for your audience.

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

## Production deployment (truly automated)

Running `generate_episode.py` locally works for testing, but for a fully
automated daily podcast you need an always-on server with a cron job.
Here's the full path from zero to a daily episode publishing itself every morning.

### 1. Provision a server

Any Linux VPS works. AWS EC2 `t3.micro` (~$8/mo) or a $6 DigitalOcean droplet
are both fine — the workload is light (one API call chain per day).

```bash
# Connect to your server
ssh -i your_key.pem ec2-user@YOUR_SERVER_IP
```

### 2. Install dependencies

```bash
# Python deps
pip install anthropic requests python-dotenv pydub

# Playwright + Chromium (for Spotify upload)
pip install playwright
playwright install chromium
playwright install-deps chromium   # installs system libs

# ffmpeg (for audio stitching)
sudo apt install ffmpeg -y         # Debian/Ubuntu
# sudo yum install ffmpeg -y       # Amazon Linux / RHEL
```

### 3. Deploy the code

```bash
# Upload the project
scp -r /path/to/agentic-podcast ec2-user@YOUR_SERVER_IP:~/agentic-podcast
```

### 4. Configure credentials on the server

```bash
cd ~/agentic-podcast
cp .env.example .env
nano .env   # fill in your API keys
```

### 5. Set up the Spotify session (one-time, from your Mac)

The Spotify upload uses a saved browser session. You generate it once on
your Mac (where you can see the browser), then copy it to the server.

```bash
# On your Mac:
python3 save_spotify_session.py
# A browser opens — log into Spotify for Creators, press Enter

# Copy the session to the server:
scp spotify_session.json ec2-user@YOUR_SERVER_IP:~/agentic-podcast/spotify_session.json
```

The session stays valid for several weeks. When it expires, repeat this step.

### 6. Test a full run on the server

```bash
# SSH into server, run once with --auto to skip prompts
cd ~/agentic-podcast
python3 generate_episode.py --auto
```

Check the output and verify an episode appears in Spotify for Creators.

### 7. Set up the cron job

```bash
# Open crontab
crontab -e

# Add these two lines (7am Eastern Time, daily):
CRON_TZ=America/New_York
0 7 * * * cd ~/agentic-podcast && python3 generate_episode.py --auto >> ~/agentic-podcast/logs/podcast.log 2>&1
```

```bash
# Create the logs directory
mkdir -p ~/agentic-podcast/logs
```

Verify the cron is set:
```bash
crontab -l
```

### 8. Monitor

```bash
# Check today's log
tail -50 ~/agentic-podcast/logs/podcast.log

# Check episode counter (should increment each day)
cat ~/agentic-podcast/episode_count.txt
```

### Session refresh

When the Spotify session expires (every few weeks), you'll see an error
in the log like `Session fully expired`. Fix it in 2 minutes:

```bash
# On your Mac:
python3 save_spotify_session.py

# Copy fresh session to server:
scp spotify_session.json ec2-user@YOUR_SERVER_IP:~/agentic-podcast/spotify_session.json
```

### Cost summary (server + APIs)

| Item | Cost |
|------|------|
| EC2 t3.micro (or equivalent VPS) | ~$8/mo |
| Claude Sonnet (per episode) | ~$0.05 |
| ElevenLabs Creator plan | $22/mo |
| Web search (3 searches/episode) | ~$0.03 |
| **Total** | **~$31/mo** |

That's a fully automated daily podcast for about $1/day.

---

## Project structure

```
agentic-podcast/
├── generate_episode.py      # Main pipeline — data → script → audio → upload
├── spotify_upload.py        # Playwright Spotify upload module
├── save_spotify_session.py  # One-time Spotify browser login
├── intro_jingle.mp3         # Your intro sound (not tracked in git)
├── spotify_session.json     # Browser session cache (not tracked)
├── .env                     # Your credentials (not tracked)
├── .env.example             # Credential template
├── requirements.txt
└── README.md
```

---

## How the script generation works

Claude Sonnet receives your structured data and a prompt describing the format. Before writing the script, it runs 2-3 web searches to understand *why* the data looks the way it does — adding real-world context that makes the episode sound like a human who read the news, not a ticker readout.

The web search integration uses Anthropic's built-in `web_search` tool ([$10/1000 searches](https://platform.claude.com/docs/about-claude/pricing)). You can disable it to reduce latency and cost.

```python
# In generate_episode.py — set to False to skip web searches
USE_WEB_SEARCH = True
```

---

## Cost estimate (per episode)

| Service | Usage | Cost |
|---------|-------|------|
| Claude Sonnet | ~2,000 input + ~600 output tokens | ~$0.03 |
| Web search | 2-3 searches | ~$0.02 |
| ElevenLabs | ~250 words (~1,500 chars) | ~$0.03 |
| **Total** | | **~$0.08/episode** |

Monthly at daily cadence: **~$2.50/month** in API costs.

---

## License

MIT. Fork it, build your own automated voice, ship something.

---

*Built by [@sfrbuilds](https://github.com/sfrbuilds)*
