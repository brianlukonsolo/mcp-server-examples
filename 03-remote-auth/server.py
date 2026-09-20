"""03 — Remote with bearer-token auth (Streamable HTTP).

Identical tool surface to a basic remote server, but every request must carry
`Authorization: Bearer <token>`. Three security habits worth copying:

1. The server REFUSES TO START without a token — you can't accidentally
   deploy it open.
2. Token comparison uses hmac.compare_digest (constant-time, no timing leaks).
3. Failures return 401 with a WWW-Authenticate header, the standard signal.

Run:  MCP_AUTH_TOKEN=<secret> python server.py  ->  http://localhost:8103/mcp
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.runtime import create_server, run


import secrets



mcp = create_server("remote-auth", 8103)


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
    if len(seed) > 1000:
        raise ValueError("seed must be at most 1000 characters")
    return int.from_bytes(seed.encode(), "big") % 900000 + 100000


if __name__ == "__main__":
    run(mcp, require_auth=True)
