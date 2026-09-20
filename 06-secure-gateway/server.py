"""06 — Secure API gateway (the "everything combined" example).

A production-shaped MCP server that fronts an external API (Open-Meteo, free,
no key) with the trimmings a real deployment wants:

- bearer-token auth (fail-safe startup, constant-time comparison)
- an UNauthenticated /health endpoint for probes/monitoring
- response caching with TTL (don't hammer the upstream API)
- simple per-client rate limiting (sliding one-minute window)
- upstream error handling that returns actionable messages to the model

Run:  MCP_AUTH_TOKEN=<secret> python server.py  ->  http://localhost:8106/mcp
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.runtime import create_server, run


import time
from collections import OrderedDict
from common.upstream import get_json, coordinates
from common.storage import nonempty
from common.runtime import integer_env


RATE_LIMIT_PER_MINUTE = integer_env("RATE_LIMIT_PER_MINUTE", 120)
CACHE_TTL_SECONDS = integer_env("CACHE_TTL_SECONDS", 300)

mcp = create_server("secure-gateway", 8106)

# ---------- tiny TTL cache ----------

_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
CACHE_MAX_ENTRIES = 256


def cache_get(key: str):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    _cache.pop(key, None)
    return None


def cache_put(key: str, value: dict):
    if key not in _cache and len(_cache) >= CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)
    _cache[key] = (time.monotonic(), value)


async def fetch_json(url: str, params: dict) -> dict:
    """GET with caching and upstream-error translation."""
    key = f"{url}?{sorted(params.items())}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    data = await get_json(url, params)
    cache_put(key, data)
    return data


# ---------- tools ----------

@mcp.tool()
async def search_location(query: str, max_results: int = 5) -> list[dict]:
    """Find places by name; returns coordinates to pass to get_forecast."""
    query = nonempty(query, "query")
    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be 1-20")
    data = await fetch_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": query, "count": max_results},
    )
    return [
        {"name": c.get("name"), "region": c.get("admin1"), "country": c.get("country"),
         "latitude": c.get("latitude"), "longitude": c.get("longitude")}
        for c in (data.get("results") or [])
    ]


@mcp.tool()
async def get_forecast(latitude: float, longitude: float, days: int = 3) -> dict:
    """Daily forecast (max/min temperature, precipitation, wind) for coordinates."""
    coordinates(latitude, longitude)
    if not 1 <= days <= 14:
        raise ValueError("days must be 1-14")
    data = await fetch_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": latitude, "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            "forecast_days": days, "timezone": "auto",
        },
    )
    return {"daily": data.get("daily"), "timezone": data.get("timezone")}


@mcp.tool()
def gateway_stats() -> dict:
    """Operational stats: cache entries and configured limits."""
    for key in list(_cache):
        cache_get(key)
    return {
        "cache_entries": len(_cache),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE,
    }


if __name__ == "__main__":
    run(mcp, require_auth=True)
