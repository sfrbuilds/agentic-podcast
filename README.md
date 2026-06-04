# Agentic Podcast Generator

> **Automatically generate, narrate, and publish a daily data-driven podcast using Claude, ElevenLabs, and Spotify — with zero human intervention.**

A fully automated pipeline that fetches live data from any source, generates a spoken briefing script using Claude Sonnet (with real-time web search for context), synthesizes audio with ElevenLabs TTS, and publishes to Spotify every morning via headless browser automation.

Built as a general framework. The included example uses prediction market data, but the pattern works for any domain: financial data, sports, weather, news, research, analytics dashboards — anything that produces structured daily data.

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
brew install ffmpeg   # macOS — needed for audio stitching

cp .env.example .env  # fill in your API keys
python3 generate_episode.py
```

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

## Scheduling (fully automated, 7am daily)

### Linux server (recommended)

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Add cron job — runs at 7am in your timezone
(crontab -l 2>/dev/null; \
 echo "CRON_TZ=America/New_York"; \
 echo "0 7 * * * cd /path/to/agentic-podcast && python3 generate_episode.py --auto >> logs/podcast.log 2>&1") \
| crontab -
```

Pass `--auto` flag to skip the interactive confirmation prompts.

### macOS

Use [launchd](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html) or a tool like [LaunchControl](https://www.soma-zone.com/LaunchControl/).

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
