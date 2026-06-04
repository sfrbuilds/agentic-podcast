#!/usr/bin/env python3
"""
Agentic Podcast Generator
━━━━━━━━━━━━━━━━━━━━━━━━━
Full pipeline: data source → Claude Sonnet (+ web search) → ElevenLabs TTS
→ jingle stitch → MP3 → Spotify upload

Run: python3 generate_episode.py

This example fetches prediction market data from the Veynor API.
Replace the fetch_data() function with any data source for your domain.
See README.md for details.
"""

import json, os, sys, time, requests
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# ── Config (set in .env) ───────────────────────────────────────────────────────
VEYNOR_KEY    = os.environ["VEYNOR_API_KEY"]
ELEVEN_KEY    = os.environ["ELEVENLABS_API_KEY"]
ELEVEN_VOICE  = os.environ.get("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian (default)
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
SHOW_ID        = os.environ.get("SPOTIFY_SHOW_ID", "")
SESSION_FILE   = Path(__file__).parent / "spotify_session.json"
JINGLE_FILE    = Path(__file__).parent / "intro_jingle.mp3"
USE_WEB_SEARCH = True   # set False to skip web searches (faster, cheaper)

# ── Live sports/match filter ───────────────────────────────────────────────────
# These are intraday events — excluded from the daily macro briefing
LIVE_GAME_PATTERNS = [
    " vs ", " vs. ", " v ", " versus ",
    "round of 16", "round of 32", "r16", "r32", "r64",
    "quarterfinal", "semifinal", "group stage",
    "series game", "game 1", "game 2", "game 3", "game 4", "game 5",
    "set 1", "set 2", "set 3",
    "esport", "counter-strike", "cs2", "dota", "valorant",
]

def is_live_game(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in LIVE_GAME_PATTERNS)


# ── Step 1: Fetch market data ──────────────────────────────────────────────────

def fetch_data():
    print("[1/5] Fetching market data from Veynor...")
    h    = {"X-API-Key": VEYNOR_KEY}
    base = "https://api.veynor.xyz/v1"

    geo     = requests.get(f"{base}/markets/topic/geopolitics",           headers=h, timeout=30).json()
    macro   = requests.get(f"{base}/markets/topic/macro",                  headers=h, timeout=30).json()
    crypto  = requests.get(f"{base}/markets/topic/crypto",                 headers=h, timeout=30).json()
    politic = requests.get(f"{base}/markets/topic/us_politics",            headers=h, timeout=30).json()
    sports  = requests.get(f"{base}/markets/topic/sports",                 headers=h, timeout=30).json()
    movers  = requests.get(f"{base}/signals?signal_type=price_movers&limit=8", headers=h, timeout=30).json()
    whales  = requests.get(f"{base}/whale-trades?limit=20&min_notional=30000", headers=h, timeout=30).json()

    def veynor_url(m: dict) -> str:
        platform = str(m.get("platform", "")).lower()
        m_id     = str(m.get("id", ""))
        m_url    = str(m.get("url", ""))
        if platform == "polymarket":
            return f"https://veynor.xyz/trade?platform=POLY&condition={m_id}"
        elif platform == "kalshi":
            ticker = m_url.rstrip("/").split("/")[-1] if m_url else m_id.replace("KALSHI:", "")
            return f"https://veynor.xyz/trade?platform=KALSHI&ticker={ticker}"
        return "https://veynor.xyz"

    def top_markets(resp, n=4):
        mkts = [m for m in (resp.get("markets") or [])
                if not is_live_game(str(m.get("title", "")))][:n]
        for m in mkts:
            m["veynor_url"] = veynor_url(m)
        return mkts

    clean_whales = [
        t for t in (whales.get("trades") or [])
        if not is_live_game(str(t.get("market_name", "") or t.get("market", "")))
        and float(t.get("notional", 0) or 0) >= 30_000
    ][:3]

    clean_movers = []
    for m in (movers.get("price_movers") or []):
        if not is_live_game(str(m.get("title", ""))):
            m["veynor_url"] = veynor_url(m)
            clean_movers.append(m)

    context = {
        "geopolitics_markets": top_markets(geo),
        "macro_markets":       top_markets(macro),
        "crypto_markets":      top_markets(crypto),
        "us_politics_markets": top_markets(politic),
        "sports_futures":      top_markets(sports, n=4),
        "price_movers":        clean_movers[:5],
        "notable_whale_trades": clean_whales,
    }
    print(f"      Geo:{len(context['geopolitics_markets'])} Macro:{len(context['macro_markets'])} "
          f"Crypto:{len(context['crypto_markets'])} Sports:{len(context['sports_futures'])} "
          f"Movers:{len(context['price_movers'])} Whales:{len(context['notable_whale_trades'])}")
    return context


# ── Step 2: Generate script via Claude Sonnet ──────────────────────────────────

def generate_episode(context: dict, ep_num: int, recent_str: str) -> dict:
    today     = datetime.now().strftime("%A, %B %-d")
    today_iso = date.today().isoformat()

    print(f"\n[2/5] Generating episode #{ep_num} (Claude Sonnet + web search)...")

    prompt = f"""You are producing "Sharp Money" — a daily 90-second AI-powered prediction market briefing.

You have access to a web_search tool. Use it for 2-3 targeted searches to understand WHY markets are priced where they are. Keep the script grounded in market data.

Today: {today}  |  Episode: #{ep_num}

Market data:
{json.dumps(context, indent=2)}

Return a JSON object with exactly four fields:

"title": Spotify title. Format: "Sharp Money #{ep_num} — {today_iso}: [2-3 specific topics]". Max 90 chars.

"markets_referenced": Array of every market cited by price. Each entry: {{"name": short name, "venue": "Polymarket" or "Kalshi", "price": e.g. "11c", "volume": e.g. "$366K", "veynor_url": copy veynor_url exactly from data, "url": copy url from data}}.

"description": Empty string "" — auto-built later.

"script": Spoken episode. Rules:
  - 180-220 words. Natural speech. No markdown.
  - Open: "Good morning. It's {today}. This is Sharp Money, your daily prediction markets briefing."
  - Recently covered — skip unless materially changed: {recent_str}
  - Cover 2-3 markets from: geopolitics, macro, crypto, us_politics, sports_futures, or price_movers.
  - Sports futures = season/tournament winners only. No individual match outcomes.
  - One concrete trade angle (spread, divergence, term structure).
  - Close: "That's Sharp Money."
  - NEVER invent numbers. NEVER use prices as subjects ("30 cents say" = wrong).
  - Today's date is {today_iso}. Calibrate time horizons accordingly.

Return only valid JSON. No markdown fences."""

    client   = Anthropic(api_key=ANTHROPIC_KEY)
    messages = [{"role": "user", "content": prompt}]

    searches_run = 0
    while True:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )
        if msg.stop_reason == "tool_use":
            searches_run += 1
            print(f"      Web search #{searches_run}...")
            messages.append({"role": "assistant", "content": msg.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                for b in msg.content if b.type == "tool_use"
            ]})
        else:
            if searches_run: print(f"      {searches_run} web search(es) used")
            break

    raw = next((b.text for b in msg.content if hasattr(b, "text")), "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]

    import re
    episode = json.loads(re.search(r'\{[\s\S]*\}', raw.strip()).group(0))

    # Build description from markets_referenced
    refs = episode.get("markets_referenced", [])
    if refs:
        lines = []
        for m in refs:
            line = f"{m.get('name','')} — {m.get('venue','')} {m.get('price','')}"
            if m.get("volume"): line += f" | {m['volume']}/24h"
            url = m.get("veynor_url") or m.get("url", "")
            if url: line += f"\n{url}"
            lines.append(line)
        episode["description"] = "\n\n".join(lines) + "\n\nSharp Money is a daily AI-powered prediction markets briefing. No opinions. Just odds.\nveynor.xyz"
    else:
        episode["description"] = "Sharp Money is a daily AI-powered prediction markets briefing. No opinions. Just odds.\nveynor.xyz"

    return episode


# ── Step 3: Synthesize audio ───────────────────────────────────────────────────

def synthesize(script: str) -> bytes:
    print(f"\n[3/5] Synthesizing audio...")
    jingle_path = Path(__file__).parent / "sharp_money_jingle.mp3"

    # Speech
    t0   = time.time()
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={
            "text":     script,
            "model_id": "eleven_turbo_v2_5",
            "speed":    1.18,
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
    speech_bytes = resp.content
    print(f"      Speech: {len(speech_bytes)//1024} KB ({time.time()-t0:.1f}s)")

    # Stitch jingle + speech
    if JINGLE_FILE.exists():
        jingle_path = JINGLE_FILE
    elif (Path(__file__).parent / "sharp_money_jingle.mp3").exists():
        jingle_path = Path(__file__).parent / "sharp_money_jingle.mp3"
    else:
        jingle_path = None

    if jingle_path and jingle_path.exists():
        try:
            from pydub import AudioSegment
            from io import BytesIO
            jingle   = AudioSegment.from_mp3(BytesIO(jingle_path.read_bytes()))
            speech   = AudioSegment.from_mp3(BytesIO(speech_bytes))
            combined = jingle + AudioSegment.silent(duration=400) + speech
            buf = BytesIO()
            combined.export(buf, format="mp3", bitrate="128k")
            audio = buf.getvalue()
            print(f"      Combined: {len(audio)//1024} KB ({len(combined)/1000:.1f}s)")
            return audio
        except ImportError:
            print("      pydub not installed — no jingle (pip install pydub ffmpeg)")
    else:
        print("      No jingle file found — speech only")
    return speech_bytes


# ── Step 4: Save MP3 ───────────────────────────────────────────────────────────

def save_mp3(audio: bytes) -> Path:
    filename = f"sharp_money_{date.today().isoformat()}.mp3"
    path     = Path(__file__).parent / filename
    path.write_bytes(audio)
    print(f"\n[4/5] Saved: {path}")
    return path


# ── Step 5: Upload to Spotify ──────────────────────────────────────────────────

def upload_to_spotify(mp3_path: Path, title: str, description: str):
    print(f"\n[5/5] Uploading to Spotify for Creators...")
    if not SESSION_FILE.exists():
        print("  No session file. Run: python3 save_spotify_session.py")
        sys.exit(1)
    import spotify_upload as su
    su.SESSION_FILE = SESSION_FILE
    su.SHOW_ID      = SHOW_ID
    su.NEW_EP_URL   = f"https://creators.spotify.com/pod/show/{SHOW_ID}/episodes/new"
    su.upload_episode(str(mp3_path), title, description)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("SHARP MONEY — Episode Generator")
    print("="*60)

    # Episode counter
    counter_f = Path(__file__).parent / "episode_count.txt"
    ep_num    = int(counter_f.read_text().strip()) + 1 if counter_f.exists() else 1

    # Recent markets (avoid repetition)
    recent_f       = Path(__file__).parent / "recent_markets.json"
    recent_markets = json.loads(recent_f.read_text())[-6:] if recent_f.exists() else []
    recent_str     = ", ".join(m.get("name","") for m in recent_markets) or "none"

    context = fetch_data()
    episode = generate_episode(context, ep_num, recent_str)

    print(f"\n  Title: {episode['title']}")
    print(f"\n{'─'*60}\n  SCRIPT ({len(episode['script'].split())} words):\n{'─'*60}")
    print(episode["script"])
    print("─"*60)

    if input("\nGenerate audio? [y/N]: ").strip().lower() != "y":
        print("Aborted."); sys.exit(0)

    audio    = synthesize(episode["script"])
    mp3_path = save_mp3(audio)
    print("Open and listen before uploading.")

    if input("\nUpload to Spotify? [y/N]: ").strip().lower() != "y":
        print(f"Saved at {mp3_path}"); sys.exit(0)

    if SHOW_ID:
        upload_to_spotify(mp3_path, episode["title"], episode["description"])
    else:
        print("  SPOTIFY_SHOW_ID not set in .env — skipping upload")

    # Persist state
    counter_f.write_text(str(ep_num))
    all_recent = recent_markets + episode.get("markets_referenced", [])
    recent_f.write_text(json.dumps(all_recent[-12:]))

    print(f"\n✅ Episode #{ep_num} done: {episode['title']}")


if __name__ == "__main__":
    main()
