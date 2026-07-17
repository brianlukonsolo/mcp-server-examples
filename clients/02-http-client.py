"""Client 02 — Streamable HTTP client.

Connects to a remote MCP server over HTTP (02-remote-basic) and exercises all
three MCP primitives from the client side: tools, resources, and prompts.

Start the server first:  python 02-remote-basic/server.py
Then:                    python clients/02-http-client.py
"""

import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = os.environ.get("MCP_URL", "http://localhost:8102/mcp")


async def main():
    # streamablehttp_client yields (read, write, get_session_id)
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Connected to: {init.serverInfo.name}")

            # ---- tools ----
            tools = await session.list_tools()
            print("tools:", ", ".join(t.name for t in tools.tools))

            result = await session.call_tool("roll_dice", {"sides": 20, "count": 2})
            print("roll_dice ->", result.content[0].text)

            result = await session.call_tool("convert_temperature", {"value": 21, "unit": "C"})
            print("convert_temperature ->", result.content[0].text)

            # ---- resources: read-only data you can pull into context ----
            resources = await session.list_resources()
            print("resources:", ", ".join(str(r.uri) for r in resources.resources))

            content = await session.read_resource("info://server")
            print("info://server ->", content.contents[0].text.splitlines()[0])

            # ---- prompts: server-provided prompt templates ----
            prompts = await session.list_prompts()
            print("prompts:", ", ".join(p.name for p in prompts.prompts))

            prompt = await session.get_prompt("brainstorm", {"topic": "YouTube channel growth"})
            print("brainstorm prompt ->", prompt.messages[0].content.text[:80], "...")


if __name__ == "__main__":
    asyncio.run(main())
