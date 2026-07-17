"""02 — Remote basic (Streamable HTTP, no auth).

The same idea as hello-world, but served over HTTP so *remote* clients —
claude.ai connectors, ChatGPT connectors, Claude Code with --transport http —
can reach it. Also introduces the two other MCP primitives besides tools:
resources (data the client can read) and prompts (reusable prompt templates).

⚠️ No authentication: anyone who can reach the port can call the tools.
Fine on localhost; see example 03 before exposing anything.

Run:  python server.py   ->  http://localhost:8102/mcp
"""

import os
import random
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "remote-basic",
    instructions="A demo server with dice, time, and unit-conversion tools.",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8102")),
    # stateless_http means every request is self-contained — no server-side
    # session to resume. This is the most compatible mode for hosted
    # connectors (claude.ai, ChatGPT), which may not pin requests to one node.
    stateless_http=True,
)


# ---------- tools ----------

@mcp.tool()
def roll_dice(sides: int = 6, count: int = 1) -> dict:
    """Roll one or more dice. Returns each roll and the total."""
    if not (2 <= sides <= 1000 and 1 <= count <= 100):
        raise ValueError("sides must be 2-1000 and count 1-100")
    rolls = [random.randint(1, sides) for _ in range(count)]
    return {"rolls": rolls, "total": sum(rolls)}


@mcp.tool()
def current_time() -> str:
    """Current UTC date and time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def convert_temperature(value: float, unit: str) -> dict:
    """Convert a temperature. unit is the unit of `value`: 'C' or 'F'."""
    unit = unit.upper().strip()
    if unit == "C":
        return {"celsius": value, "fahrenheit": value * 9 / 5 + 32}
    if unit == "F":
        return {"celsius": (value - 32) * 5 / 9, "fahrenheit": value}
    raise ValueError("unit must be 'C' or 'F'")


# ---------- a resource: read-only data the client can load ----------

@mcp.resource("info://server")
def server_info() -> str:
    """About this server."""
    return (
        "remote-basic: an example MCP server over Streamable HTTP.\n"
        "It has three tools (roll_dice, current_time, convert_temperature),\n"
        "this resource, and one prompt template."
    )


# ---------- a prompt: a reusable prompt template ----------

@mcp.prompt()
def brainstorm(topic: str) -> str:
    """Brainstorm ideas about a topic in a structured way."""
    return (
        f"Brainstorm 10 ideas about: {topic}.\n"
        "Group them into safe bets, bold moves, and wildcards, "
        "then recommend the single best one with reasoning."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
