"""03 — Remote with bearer-token auth (Streamable HTTP).

Identical tool surface to a basic remote server, but every request must carry
`Authorization: Bearer <token>`. Three security habits worth copying:

1. The server REFUSES TO START without a token — you can't accidentally
   deploy it open.
2. Token comparison uses hmac.compare_digest (constant-time, no timing leaks).
3. Failures return 401 with a WWW-Authenticate header, the standard signal.

Run:  MCP_AUTH_TOKEN=<secret> python server.py  ->  http://localhost:8103/mcp
"""

import hmac
import os
import secrets

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", "8103"))

mcp = FastMCP(
    "remote-auth",
    instructions="A bearer-token protected demo server.",
    host="0.0.0.0",
    port=PORT,
    stateless_http=True,
)


@mcp.tool()
def whoami() -> str:
    """Confirm you are talking to the authenticated server."""
    return "You reached the protected server — your bearer token was accepted."


@mcp.tool()
def generate_password(length: int = 20) -> str:
    """Generate a cryptographically secure random password (8-64 chars)."""
    if not 8 <= length <= 64:
        raise ValueError("length must be between 8 and 64")
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@mcp.tool()
def secret_number(seed: str) -> int:
    """Derive a deterministic 6-digit number from a seed string."""
    return int.from_bytes(seed.encode(), "big") % 900000 + 100000


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't present the expected bearer token."""

    async def dispatch(self, request, call_next):
        supplied = request.headers.get("authorization", "")
        # compare_digest = constant-time comparison; == would leak timing info
        if not hmac.compare_digest(supplied, f"Bearer {AUTH_TOKEN}"):
            return JSONResponse(
                {"error": "unauthorized", "detail": "Missing or invalid bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


if __name__ == "__main__":
    if not AUTH_TOKEN:
        raise SystemExit(
            "Refusing to start without authentication.\n"
            "Set MCP_AUTH_TOKEN (e.g. `openssl rand -hex 24`) and run again."
        )
    # Instead of mcp.run(), grab the underlying ASGI app so we can wrap it
    # with middleware, then serve it ourselves.
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
