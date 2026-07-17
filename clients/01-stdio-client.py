"""Client 01 — stdio client.

The client-side mirror of 01-hello-world: this script LAUNCHES the server
itself as a subprocess and talks to it over stdin/stdout — exactly what
Claude Desktop / Claude Code do with local MCP servers.

Run from the repo root:
    python clients/01-stdio-client.py
"""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    # How to start the server. The client owns the process lifecycle.
    params = StdioServerParameters(command="python", args=["01-hello-world/server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. Handshake: exchange protocol versions and capabilities.
            init = await session.initialize()
            print(f"Connected to: {init.serverInfo.name} v{init.serverInfo.version}")

            # 2. Discover what the server offers.
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"  tool: {tool.name} — {tool.description}")

            # 3. Call tools. Results arrive as content blocks.
            result = await session.call_tool("say_hello", {"name": "Brian"})
            print("say_hello ->", result.content[0].text)

            result = await session.call_tool("add", {"a": 2.5, "b": 4})
            print("add ->", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
