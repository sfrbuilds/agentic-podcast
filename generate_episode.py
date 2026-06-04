#!/usr/bin/env python3
"""
Agentic Podcast Generator — Core Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This file is the domain-agnostic core. It doesn't know what your podcast
is about — it only knows how to:
  1. Call your data source (any Python function that returns a dict)
  2. Feed that data to Claude Sonnet to generate a spoken script
  3. Synthesize audio with ElevenLabs
  4. Stitch in an intro jingle
  5. Upload to Spotify

To adapt to your domain, edit DATA_SOURCE below and write a fetch function
in data_sources/. See data_sources/README.md for instructions.

Run:  python3 generate_episode.py
Auto: python3 generate_episode.py --auto   (no confirmation prompts)
"""

import argparse, json, os, sys, time, requests
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]
ELEVEN_KEY     = os.environ["ELEVENLABS_API_KEY"]
ELEVEN_VOICE   = os.environ.get("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian
SHOW_ID        = os.environ.get("SPOTIFY_SHOW_ID", "")
SESSION_FILE   = Path(__file__).parent / "spotify_session.json"
JINGLE_FILE    = Path(__file__).parent / "intro_jingle.mp3"
USE_WEB_SEARCH = os.environ.get("USE_WEB_SEARCH", "true").lower() != "false"

# ── Choose your data source ─────────────────────────────────────────────────────
# Point this at any function in data_sources/ that returns a dict.
# The dict is passed directly to Claude as context — structure it however
# makes sense for your domain.
#
# Swap this import to use a different data source:
from data_sources.example_weather import fetch_data, PODCAST_NAME, PROMPT_TEMPLATE

# Other examples (uncomment to use):
# from data_sources.example_markets import fetch_data, PODCAST_NAME, PROMPT_TEMPLATE
# from data_sources.your_source     import fetch_data, PODCAST_NAME, PROMPT_TEMPLATE


# ── Step 1: Fetch data ──────────────────────────────────────────────────────────

def get_data() -> dict:
    print(f"[1/5] Fetching data for '{PODCAST_NAME}'...")
    data = fetch_data()
    print(f"      OK — {len(str(data))} chars of context")
    return data


# ── Step 2: Generate script via Claude ─────────────────────────────────────────

def generate_episode(data: dict, ep_num: int, recent_str: str) -> dict:
    today     = datetime.now().strftime("%A, %B %-d")
    today_iso = date.today().isoformat()

    print(f"\n[2/5] Generating episode #{ep_num} (Claude Sonnet"
          + (" + web search" if USE_WEB_SEARCH else "") + ")...")

    # Build prompt using simple replacement instead of .format() to avoid
    # KeyErrors from JSON braces in the data payload.
    prompt = (PROMPT_TEMPLATE
        .replace("{today}",      today)
        .replace("{today_iso}",  today_iso)
        .replace("{ep_num}",     str(ep_num))
        .replace("{recent_str}", recent_str)
        .replace("{data}",       json.dumps(data, indent=2))
    )

    client   = Anthropic(api_key=ANTHROPIC_KEY)
    messages = [{"role": "user", "content": prompt}]
    tools    = [{"type": "web_search_20250305", "name": "web_search"}] if USE_WEB_SEARCH else []

    searches = 0
    while True:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            tools=tools,
            messages=messages,
        )
        if msg.stop_reason == "tool_use":
            searches += 1
            print(f"      Web search #{searches}...")
            messages.append({"role": "assistant", "content": msg.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                for b in msg.content if b.type == "tool_use"
            ]})
        else:
            if searches: print(f"      {searches} web search(es) used")
            break

    raw = next((b.text for b in msg.content if hasattr(b, "text")), "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]

    import re
    episode = json.loads(re.search(r'\{[\s\S]*\}', raw.strip()).group(0))

    # Build Spotify description from referenced markets/items
    refs = episode.get("items_referenced", [])
    if refs:
        lines = [f"{r.get('name','')} — {r.get('detail','')}" for r in refs]
        episode["description"] = "\n".join(lines) + f"\n\n{PODCAST_NAME}\nveynor.xyz"
    else:
        episode["description"] = episode.get("description", f"{PODCAST_NAME}")

    return episode


# ── Step 3: Synthesize audio ────────────────────────────────────────────────────

def synthesize(script: str) -> bytes:
    print(f"\n[3/5] Synthesizing audio (ElevenLabs)...")

    t0   = time.time()
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={
            "text":     script,
            "model_id": "eleven_turbo_v2_5",
            "speed":    1.15,
            "voice_settings": {
                "stability":         0.72,
                "similarity_boost":  0.75,
                "style":             0.20,
                "use_speaker_boost": True,
            },
        },
        timeout=60,
    )
    resp.raise_for_status()
    speech = resp.content
    print(f"      Speech: {len(speech)//1024} KB ({time.time()-t0:.1f}s)")

    if JINGLE_FILE.exists():
        try:
            from pydub import AudioSegment
            from io import BytesIO
            jingle   = AudioSegment.from_mp3(BytesIO(JINGLE_FILE.read_bytes()))
            narration = AudioSegment.from_mp3(BytesIO(speech))
            combined = jingle + AudioSegment.silent(duration=400) + narration
            buf = BytesIO()
            combined.export(buf, format="mp3", bitrate="128k")
            audio = buf.getvalue()
            print(f"      Combined with jingle: {len(audio)//1024} KB ({len(combined)/1000:.1f}s)")
            return audio
        except ImportError:
            print("      pydub not installed — no jingle (pip install pydub)")
    else:
        print("      No intro_jingle.mp3 found — speech only")

    return speech


# ── Step 4: Save MP3 ────────────────────────────────────────────────────────────

def save_mp3(audio: bytes) -> Path:
    path = Path(__file__).parent / f"episode_{date.today().isoformat()}.mp3"
    path.write_bytes(audio)
    print(f"\n[4/5] Saved: {path}")
    return path


# ── Step 5: Upload to Spotify ───────────────────────────────────────────────────

def upload(mp3_path: Path, title: str, description: str):
    print(f"\n[5/5] Uploading to Spotify...")
    if not SESSION_FILE.exists():
        print("  No session. Run: python3 save_spotify_session.py")
        sys.exit(1)
    if not SHOW_ID:
        print("  SPOTIFY_SHOW_ID not set in .env — skipping upload")
        return
    import spotify_upload as su
    su.SESSION_FILE = SESSION_FILE
    su.SHOW_ID      = SHOW_ID
    su.NEW_EP_URL   = f"https://creators.spotify.com/pod/show/{SHOW_ID}/episodes/new"
    su.upload_episode(str(mp3_path), title, description)


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()

    def confirm(prompt):
        if args.auto: return True
        return input(f"\n{prompt} [y/N]: ").strip().lower() == "y"

    print(f"\n{'='*60}\n  {PODCAST_NAME.upper()} — Episode Generator\n{'='*60}")

    # State files
    counter_f = Path(__file__).parent / "episode_count.txt"
    recent_f  = Path(__file__).parent / "recent_topics.json"
    ep_num    = int(counter_f.read_text().strip()) + 1 if counter_f.exists() else 1
    recent    = json.loads(recent_f.read_text()) if recent_f.exists() else []
    recent_str = ", ".join(recent[-6:]) or "none"

    data    = get_data()
    episode = generate_episode(data, ep_num, recent_str)

    print(f"\n  Title:  {episode.get('title', '—')}")
    print(f"\n{'─'*60}\n  SCRIPT ({len(episode.get('script','').split())} words):\n{'─'*60}")
    print(episode.get("script", ""))
    print("─"*60)

    if not confirm("Generate audio?"): print("Aborted."); sys.exit(0)

    audio    = synthesize(episode["script"])
    mp3_path = save_mp3(audio)
    print("  Listen before uploading.")

    if not confirm("Upload to Spotify?"): print(f"  Saved at {mp3_path}"); sys.exit(0)

    upload(mp3_path, episode.get("title", f"Episode {ep_num}"), episode.get("description", ""))

    # Persist state
    counter_f.write_text(str(ep_num))
    new_topics = recent + [episode.get("title", "")]
    recent_f.write_text(json.dumps(new_topics[-12:]))

    print(f"\n✅  Episode #{ep_num} done: {episode.get('title')}")


if __name__ == "__main__":
    main()
