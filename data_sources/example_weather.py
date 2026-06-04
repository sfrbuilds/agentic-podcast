"""
Data source: Weather Briefing (Open-Meteo)
──────────────────────────────────────────
Minimal example showing the pattern with a completely free,
no-auth-required API. Generates a daily weather briefing
for a configurable city.

Requires: nothing (Open-Meteo is free and open)
Optional: set WEATHER_CITY and WEATHER_LAT/LON in .env
"""

import os, requests
from dotenv import load_dotenv

load_dotenv()

PODCAST_NAME = "Morning Weather"

PROMPT_TEMPLATE = """\
You are producing "{podcast_name}" — a friendly 60-second daily weather briefing.

Today: {{today}}  |  Episode: #{{ep_num}}

Weather data for today:
{{data}}

Return a JSON object with:

"title": Episode title. Format: "{podcast_name} — {{today_iso}}: [weather summary]". Max 80 chars.

"items_referenced": [{{"name": "Today's forecast", "detail": "high/low, conditions"}}]

"description": One sentence summary of today's weather.

"script": Spoken briefing. Rules:
  - 60-90 words. Friendly, conversational.
  - Open: "Good morning. It's {{today}}."
  - Cover: high/low temps, conditions, anything notable (storms, heatwave, etc.)
  - One practical tip (umbrella, sunscreen, layers, etc.)
  - Close: "Have a great day."

Return only valid JSON. No markdown fences.\
""".format(podcast_name=PODCAST_NAME)


def fetch_data() -> dict:
    # Default: New York City
    lat = float(os.environ.get("WEATHER_LAT", "40.7128"))
    lon = float(os.environ.get("WEATHER_LON", "-74.0060"))
    city = os.environ.get("WEATHER_CITY", "New York City")

    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude":       lat,
            "longitude":      lon,
            "daily":          ["temperature_2m_max", "temperature_2m_min",
                               "precipitation_sum", "weathercode"],
            "temperature_unit": "fahrenheit",
            "timezone":       "America/New_York",
            "forecast_days":  1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    d = resp.json()["daily"]

    wmo_codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 51: "Light drizzle", 61: "Light rain", 63: "Moderate rain",
        71: "Light snow", 80: "Rain showers", 95: "Thunderstorm",
    }
    code = d["weathercode"][0]
    condition = wmo_codes.get(code, f"Weather code {code}")

    return {
        "city":          city,
        "date":          d["time"][0],
        "high_f":        d["temperature_2m_max"][0],
        "low_f":         d["temperature_2m_min"][0],
        "precipitation": f"{d['precipitation_sum'][0]}mm",
        "condition":     condition,
    }
