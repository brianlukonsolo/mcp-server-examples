"""Client 04 — progress, logging, and long-running tools.

The client-side view of 04-tool-features' `simulate_batch_job`: while the tool
runs, the server streams progress updates and log messages, and this client
renders them live instead of sitting in silence.

Start the server first:  python 04-tool-features/server.py
Then:                    python clients/04-advanced-client.py
"""

import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import LoggingMessageNotificationParams

URL = os.environ.get("MCP_URL", "http://localhost:8104/mcp")


async def on_log(params: LoggingMessageNotificationParams):
    """Called whenever the server emits ctx.info / ctx.warning / ctx.error."""
    print(f"  [server log/{params.level}] {params.data}")


async def on_progress(progress: float, total: float | None, message: str | None):
    """Called for every ctx.report_progress the tool makes."""
    if total:
        pct = int(progress / total * 100)
        bar = "#" * (pct // 5)
        print(f"  [{bar:<20}] {pct:3d}%", end="\r" if pct < 100 else "\n")


async def main():
    async with streamablehttp_client(URL) as (read, write, _):
        # logging_callback receives server-side log notifications for the session
        async with ClientSession(read, write, logging_callback=on_log) as session:
            await session.initialize()

            print("Running simulate_batch_job(25) with live progress:")
            result = await session.call_tool(
                "simulate_batch_job",
                {"items": 25},
                progress_callback=on_progress,  # per-call progress hook
            )
            print("result ->", result.content[0].text)

            # A quick structured-output call for contrast
            result = await session.call_tool(
                "text_stats",
                {"text": "to be or not to be that is the question", "top_words": 3},
            )
            print("text_stats ->", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
