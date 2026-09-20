"""Client 03 — authenticating with a bearer token.

Connects to the protected server. The shared HTTP client carries bearer headers.
The rejection demonstration requires an actual HTTP 401, not just any error.

Start the server first:  MCP_AUTH_TOKEN=<secret> python 03-remote-auth/server.py
Then:                    MCP_AUTH_TOKEN=<secret> python clients/03-auth-client.py
"""

import asyncio
import os
import sys

from mcp import ClientSession
from connection import remote_transport

URL = os.environ.get("MCP_URL", "http://localhost:8103/mcp")
TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()


async def try_without_token():
    """Show what rejection looks like: the 401 surfaces as a connection error."""
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(URL, json={})
    if response.status_code != 401:
        raise RuntimeError(f"Expected HTTP 401, got {response.status_code}")
    print("without token -> HTTP 401 as expected")


async def with_token():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with remote_transport(URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("whoami", {})
            print("with token ->", result.content[0].text)

            result = await session.call_tool("generate_password", {"length": 24})
            print("generate_password ->", result.content[0].text)


async def main():
    if not TOKEN:
        sys.exit("Set MCP_AUTH_TOKEN to the same value the server uses.")
    await try_without_token()
    await with_token()


if __name__ == "__main__":
    asyncio.run(main())
