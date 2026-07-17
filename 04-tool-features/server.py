"""04 — Tool features in depth (Streamable HTTP, no auth).

What makes tools *good*: rich typed parameters, structured results, clear
errors, async calls to real external APIs, and progress/log reporting back to
the client while a long tool runs.

Uses the free Open-Meteo API (no API key needed).

Run:  python server.py  ->  http://localhost:8104/mcp
"""

import asyncio
import os
from typing import Literal, Optional

import httpx
from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP(
    "tool-features",
    instructions=(
        "Demonstrates well-designed MCP tools: weather lookups via Open-Meteo, "
        "text statistics, and a long-running task with progress reporting."
    ),
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8104")),
    stateless_http=True,
)

OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"


# ---------- async tools calling a real external API ----------

@mcp.tool()
async def find_city(name: str, max_results: int = 5) -> list[dict]:
    """Look up cities by name; returns name, country, coordinates, population.
    Use this first to get coordinates for get_weather."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(OPEN_METEO_GEO, params={"name": name, "count": max_results})
        r.raise_for_status()
    results = r.json().get("results") or []
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
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(OPEN_METEO_FORECAST, params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": days,
            "temperature_unit": units,
            "timezone": "auto",
        })
        r.raise_for_status()
    data = r.json()
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
        await ctx.report_progress(i + 1, items)
        # Log messages the client can surface:
        if (i + 1) % 10 == 0:
            await ctx.info(f"Processed {i + 1}/{items} items")
    return f"Batch complete: {items} items processed successfully."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
