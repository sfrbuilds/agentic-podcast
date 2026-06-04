# Data Sources

Each file in this directory is a self-contained data plugin.
`generate_episode.py` imports one of them via a single line swap.

## Interface

Every data source must export three things:

```python
PODCAST_NAME = "Your Podcast Name"

PROMPT_TEMPLATE = """
You are producing "{podcast_name}" — a daily spoken briefing.
...
"""  # Claude receives this with {today}, {ep_num}, {data} filled in

def fetch_data() -> dict:
    """Fetch and return structured data for today's episode."""
    ...
    return {...}
```

The dict returned by `fetch_data()` is serialized to JSON and injected
into `PROMPT_TEMPLATE` as `{data}`. Structure it however makes sense for
your domain — Claude will read it.

Claude should return a JSON object with at minimum:
- `title` — Spotify episode title
- `script` — the spoken episode text (180-250 words)
- `description` — show notes / episode description
- `items_referenced` — list of `{name, detail}` for the description

## Included examples

| File | Domain | Data source |
|------|--------|-------------|
| `example_markets.py` | Prediction markets | Veynor API (free) |
| `example_weather.py` | Weather briefing | Open-Meteo API (free, no key) |

## Writing your own

Copy `example_weather.py` as a starting point — it's the simplest.
Your `fetch_data()` just needs to return a dict. Some ideas:

```python
# Financial data
import yfinance as yf
def fetch_data():
    tickers = ["SPY", "BTC-USD", "GLD"]
    return {t: yf.Ticker(t).fast_info for t in tickers}

# Your product's analytics
def fetch_data():
    return requests.get("https://your-api.com/daily-stats",
                        headers={"Authorization": f"Bearer {os.environ['API_KEY']}"}).json()

# RSS / news headlines
import feedparser
def fetch_data():
    feed = feedparser.parse("https://feeds.reuters.com/reuters/topNews")
    return {"headlines": [e.title for e in feed.entries[:10]]}

# Sports scores
def fetch_data():
    return requests.get("https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/TODAY",
                        params={"key": os.environ["SPORTS_API_KEY"]}).json()
```
