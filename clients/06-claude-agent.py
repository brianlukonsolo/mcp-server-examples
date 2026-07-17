"""Client 06 — a Claude-powered agent that drives MCP tools.

The capstone: instead of YOU calling tools, Claude does. This connects to an
MCP server, hands its tools to Claude via the Anthropic SDK's tool runner,
and lets the model plan, call tools, read results, and answer — the same loop
Claude Desktop runs internally, in ~40 lines you control.

Requires:
    pip install "anthropic[mcp]"
    export ANTHROPIC_API_KEY=sk-ant-...   (from console.anthropic.com)

Start the weather server first:  python 04-tool-features/server.py
Then, for example:
    python clients/06-claude-agent.py "Should I cycle in Manchester this weekend?"
"""

import asyncio
import os
import sys

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8104/mcp")
TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()  # only for authed servers

QUESTION = " ".join(sys.argv[1:]) or "What's the weather in London for the next 3 days?"


async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY (get one at console.anthropic.com).")

    claude = AsyncAnthropic()
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else None

    async with streamablehttp_client(MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()
            mcp_tools = (await mcp_session.list_tools()).tools
            print(f"Claude has {len(mcp_tools)} MCP tools: "
                  f"{', '.join(t.name for t in mcp_tools)}\n")

            # The tool runner drives the whole agentic loop: Claude requests a
            # tool -> the SDK calls it on the MCP session -> the result goes
            # back to Claude -> repeat until Claude answers in plain text.
            runner = claude.beta.messages.tool_runner(
                model="claude-opus-4-8",
                max_tokens=16000,
                thinking={"type": "adaptive"},
                tools=[async_mcp_tool(t, mcp_session) for t in mcp_tools],
                messages=[{"role": "user", "content": QUESTION}],
            )

            async for message in runner:
                for block in message.content:
                    if block.type == "tool_use":
                        print(f"[Claude calls] {block.name}({block.input})")
                    elif block.type == "text" and block.text.strip():
                        print(f"\n{block.text}")


if __name__ == "__main__":
    asyncio.run(main())
