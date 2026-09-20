"""Bounded JSON reads and explicit network/protocol errors for API examples."""
import json
import math

import httpx


def coordinates(latitude: float, longitude: float):
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("latitude must be finite and between -90 and 90")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("longitude must be finite and between -180 and 180")


async def get_json(url: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            async with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise RuntimeError("Upstream response exceeded 2 MB")
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                return data
    except httpx.TimeoutException:
        raise RuntimeError("Upstream weather API timed out; try again shortly") from None
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Upstream weather API returned HTTP {exc.response.status_code}") from None
    except httpx.RequestError:
        raise RuntimeError("Could not connect to the upstream weather API") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("Upstream weather API returned invalid JSON") from None
