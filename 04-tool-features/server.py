"""04 — Tool features in depth (Streamable HTTP, no auth).

What makes tools *good*: rich typed parameters, structured results, clear
errors, async calls to real external APIs, and progress/log reporting back to
the client while a long tool runs.

Uses the free Open-Meteo API (no API key needed).

Run:  python server.py  ->  http://localhost:8104/mcp
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.runtime import create_server, run, report_progress


import asyncio
from typing import Literal, Optional

from common.upstream import get_json, coordinates
from common.storage import nonempty
from mcp.server.fastmcp import Context

mcp = create_server("tool-features", 8104)

OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"


# ---------- async tools calling a real external API ----------

@mcp.tool()
async def find_city(name: str, max_results: int = 5) -> list[dict]:
    """Look up cities by name; returns name, country, coordinates, population.
    Use this first to get coordinates for get_weather."""
    name = nonempty(name, "name")
    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be 1-20")
    data = await get_json(OPEN_METEO_GEO, {"name": name, "count": max_results})
    results = data.get("results") or []
    return [
        {
            "name": c.get("name"),
            "country": c.get("country"),
            "latitude": c.get("latitude"),
            "longitude": c.get("longitude"),
            "population": c.get("population"),
        }
        for c in results
    ]


@mcp.tool()
async def get_weather(
    latitude: float,
    longitude: float,
    days: int = 3,
    units: Literal["celsius", "fahrenheit"] = "celsius",
) -> dict:
    """Weather forecast for coordinates (use find_city to get them).
    Returns current conditions plus a daily min/max/precipitation forecast."""
    if not 1 <= days <= 14:
        raise ValueError("days must be 1-14")
    coordinates(latitude, longitude)
    data = await get_json(OPEN_METEO_FORECAST, {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": days,
            "temperature_unit": units,
            "timezone": "auto",
        })
    return {
        "current": data.get("current"),
        "daily": data.get("daily"),
        "units": units,
        "timezone": data.get("timezone"),
    }


# ---------- structured output & optional parameters ----------

@mcp.tool()
def text_stats(text: str, top_words: Optional[int] = None) -> dict:
    """Statistics for a piece of text: characters, words, lines, and
    optionally the most frequent words (top_words)."""
    if len(text) > 100_000:
        raise ValueError("text must be at most 100000 characters")
    if top_words is not None and not 1 <= top_words <= 100:
        raise ValueError("top_words must be 1-100")
    words = text.split()
    result = {
        "characters": len(text),
        "words": len(words),
        "lines": text.count("\n") + 1 if text else 0,
        "average_word_length": round(sum(len(w) for w in words) / len(words), 2) if words else 0,
    }
    if top_words:
        freq: dict[str, int] = {}
        for w in words:
            key = w.lower().strip(".,!?;:\"'()")
            if key:
                freq[key] = freq.get(key, 0) + 1
        ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        result["most_frequent"] = [{"word": w, "count": n} for w, n in ranked[:top_words]]
    return result


# ---------- long-running tool with progress + logging ----------

@mcp.tool()
async def simulate_batch_job(items: int, ctx: Context) -> str:
    """Simulate processing a batch of items (1-50), reporting progress as it
    goes. Demonstrates how long tools keep the client informed."""
    if not 1 <= items <= 50:
        raise ValueError("items must be 1-50")
    for i in range(items):
        await asyncio.sleep(0.15)  # pretend each item takes work
        # Progress bar in clients that render it:
        await report_progress(ctx, i + 1, items)
        # Log messages the client can surface:
        if (i + 1) % 10 == 0:
            await ctx.info(f"Processed {i + 1}/{items} items")
    return f"Batch complete: {items} items processed successfully."


if __name__ == "__main__":
    run(mcp, require_auth=False)
