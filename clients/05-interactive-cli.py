"""Client 05 — a generic MCP inspector/CLI.

Point it at ANY Streamable HTTP MCP server (including your own apps) to list
its tools or call them — one-shot from the command line, or as an interactive
REPL. Handy for debugging servers before wiring them into an AI client.

Examples:
    python clients/05-interactive-cli.py http://localhost:8102/mcp --list
    python clients/05-interactive-cli.py http://localhost:8102/mcp \
        --call roll_dice --args '{"sides": 6, "count": 3}'
    python clients/05-interactive-cli.py http://localhost:8103/mcp --token <secret>
"""

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def parse_args():
    p = argparse.ArgumentParser(description="Generic MCP client CLI")
    p.add_argument("url", help="MCP endpoint, e.g. http://localhost:8102/mcp")
    p.add_argument("--token", help="Bearer token for authenticated servers")
    p.add_argument("--list", action="store_true", help="List tools and exit")
    p.add_argument("--call", metavar="TOOL", help="Call one tool and exit")
    p.add_argument("--args", default="{}", help="JSON arguments for --call")
    return p.parse_args()


def print_tools(tools):
    for t in tools:
        required = (t.inputSchema or {}).get("required", [])
        props = (t.inputSchema or {}).get("properties", {})
        params = ", ".join(
            f"{name}{'' if name in required else '?'}: {spec.get('type', 'any')}"
            for name, spec in props.items()
        )
        summary = (t.description or "").split("\n")[0]
        print(f"  {t.name}({params})")
        print(f"      {summary}")


async def repl(session: ClientSession, tools):
    print("\nInteractive mode. Commands: <tool> {json-args} | list | quit")
    while True:
        try:
            line = input("mcp> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "list":
            print_tools(tools)
            continue
        name, _, raw_args = line.partition(" ")
        try:
            arguments = json.loads(raw_args) if raw_args.strip() else {}
            result = await session.call_tool(name, arguments)
            for block in result.content:
                if block.type == "text":
                    print(block.text)
        except Exception as e:
            print(f"error: {e}")


async def main():
    opts = parse_args()
    headers = {"Authorization": f"Bearer {opts.token}"} if opts.token else None

    async with streamablehttp_client(opts.url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Connected to: {init.serverInfo.name} v{init.serverInfo.version}")
            tools = (await session.list_tools()).tools

            if opts.list:
                print_tools(tools)
            elif opts.call:
                result = await session.call_tool(opts.call, json.loads(opts.args))
                for block in result.content:
                    if block.type == "text":
                        print(block.text)
            else:
                print_tools(tools)
                await repl(session, tools)


if __name__ == "__main__":
    asyncio.run(main())
