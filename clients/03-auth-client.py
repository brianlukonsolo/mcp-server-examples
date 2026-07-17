"""Client 03 — authenticating with a bearer token.

Connects to the protected server (03-remote-auth). Custom headers go straight
into streamablehttp_client — the same mechanism hosted connectors use when you
fill in their auth/header fields.

Start the server first:  MCP_AUTH_TOKEN=<secret> python 03-remote-auth/server.py
Then:                    MCP_AUTH_TOKEN=<secret> python clients/03-auth-client.py
"""

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = os.environ.get("MCP_URL", "http://localhost:8103/mcp")
TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()


async def try_without_token():
    """Show what rejection looks like: the 401 surfaces as a connection error."""
    try:
        async with streamablehttp_client(URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
        print("!! connected without a token — the server is NOT protected")
    except Exception as e:
        print(f"without token -> rejected as expected ({type(e).__name__})")


async def with_token():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with streamablehttp_client(URL, headers=headers) as (read, write, _):
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
