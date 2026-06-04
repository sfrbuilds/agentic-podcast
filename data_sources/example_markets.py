"""
Data source: Prediction Markets (via Veynor API)
─────────────────────────────────────────────────
Fetches live market data from Kalshi and Polymarket across
geopolitics, macro, crypto, and US politics topics.

Requires: VEYNOR_API_KEY in .env (free at veynor.xyz/agents)
"""

import os, requests
from dotenv import load_dotenv

load_dotenv()

PODCAST_NAME = "Sharp Money"

PROMPT_TEMPLATE = """\
You are producing "{podcast_name}" — a daily 90-second AI-powered prediction market briefing.

You have access to a web_search tool. Use it for 2-3 targeted searches to explain
WHY markets are priced where they are. Ground the script in market data, not opinion.

Today: {{today}}  |  Episode: #{{ep_num}}
Recently covered (skip unless materially changed): {{recent_str}}

Market data:
{{data}}

Return a JSON object with exactly these fields:

"title": Spotify title. Format: "{podcast_name} #{{ep_num}} — {{today_iso}}: [2-3 specific topics]". Max 90 chars.

"items_referenced": Array of markets cited. Each: {{"name": short name, "detail": "venue price volume"}}.

"description": Empty string "" — auto-built from items_referenced.

"script": Spoken episode. Rules:
  - 180-220 words. Natural speech. No markdown.
  - Open: "Good morning. It's {{today}}. This is {podcast_name}, your daily prediction markets briefing."
  - Cover 2-3 markets from: geopolitics, macro, crypto, us_politics, or sports futures (season winners only).
  - One concrete trade angle — spread, divergence, or term structure.
  - Close: "That's {podcast_name}."
  - Never invent numbers. Never use prices as subjects ("30 cents say" is wrong).

Return only valid JSON. No markdown fences.\
""".format(podcast_name=PODCAST_NAME)


def fetch_data() -> dict:
    api_key = os.environ.get("VEYNOR_API_KEY") or os.environ.get("DATA_API_KEY")
    if not api_key:
        raise ValueError("Set VEYNOR_API_KEY or DATA_API_KEY in .env")

    h    = {"X-API-Key": api_key}
    base = "https://api.veynor.xyz/v1"

    # Topics to pull
    topics = ["geopolitics", "macro", "crypto", "us_politics", "sports"]
    data   = {}

    for topic in topics:
        resp = requests.get(f"{base}/markets/topic/{topic}", headers=h, timeout=30)
        if resp.ok:
            markets = resp.json().get("markets", [])
            # Keep top 4 by volume, strip live game markets
            filtered = [
                m for m in markets
                if not any(kw in str(m.get("title","")).lower()
                           for kw in [" vs ", " v ", "r16", "r32", "semifinal",
                                      "esport", "counter-strike", "cs2"])
            ][:4]
            data[f"{topic}_markets"] = [
                {
                    "title":      m.get("title"),
                    "yes_price":  f"{round(float(m.get('yes_price',0))*100)}c",
                    "volume_24h": m.get("volume_24h"),
                    "platform":   m.get("platform"),
                    "url":        m.get("url"),
                }
                for m in filtered
            ]

    # Top price movers
    movers = requests.get(f"{base}/signals?signal_type=price_movers&limit=5",
                          headers=h, timeout=30)
    if movers.ok:
        data["price_movers"] = movers.json().get("price_movers", [])[:5]

    return data
