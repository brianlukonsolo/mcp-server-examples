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

import hmac
import os
import time
from collections import defaultdict, deque

import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", "8106"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))

mcp = FastMCP(
    "secure-gateway",
    instructions=(
        "A secured gateway to weather data (Open-Meteo). Look up places with "
        "search_location, then fetch forecasts with get_forecast. Responses "
        "are cached for a few minutes; requests are rate limited."
    ),
    host="0.0.0.0",
    port=PORT,
    stateless_http=True,
)

# ---------- tiny TTL cache ----------

_cache: dict[str, tuple[float, dict]] = {}


def cache_get(key: str):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    _cache.pop(key, None)
    return None


def cache_put(key: str, value: dict):
    _cache[key] = (time.monotonic(), value)


async def fetch_json(url: str, params: dict) -> dict:
    """GET with caching and upstream-error translation."""
    key = f"{url}?{sorted(params.items())}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        raise RuntimeError("Upstream weather API timed out — try again shortly.")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Upstream weather API returned {e.response.status_code}.")
    cache_put(key, data)
    return data


# ---------- tools ----------

@mcp.tool()
async def search_location(query: str, max_results: int = 5) -> list[dict]:
    """Find places by name; returns coordinates to pass to get_forecast."""
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
    return {
        "cache_entries": len(_cache),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE,
    }


# ---------- unauthenticated health endpoint ----------

@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "secure-gateway"})


# ---------- middleware: auth + rate limiting ----------

_requests_by_client: dict[str, deque] = defaultdict(deque)


class GatewayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # health probe stays open so load balancers/monitors can reach it
        if request.url.path == "/health":
            return await call_next(request)

        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {AUTH_TOKEN}"):
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # sliding-window rate limit per client IP
        client = request.client.host if request.client else "unknown"
        window = _requests_by_client[client]
        now = time.monotonic()
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                {"error": "rate_limited", "detail": f"Max {RATE_LIMIT_PER_MINUTE} requests/minute"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        window.append(now)

        return await call_next(request)


if __name__ == "__main__":
    if not AUTH_TOKEN:
        raise SystemExit(
            "Refusing to start without authentication.\n"
            "Set MCP_AUTH_TOKEN (e.g. `openssl rand -hex 24`) and run again."
        )
    app = mcp.streamable_http_app()
    app.add_middleware(GatewayMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
