"""01 — Hello World (stdio transport).

The smallest possible MCP server: two tools, no configuration, no network.
stdio transport means the AI client launches this script itself and talks to
it over stdin/stdout — perfect for local tools in Claude Desktop / Claude Code.

Run it via a client, e.g.:
    claude mcp add hello -- python server.py
"""

from mcp.server.fastmcp import FastMCP

# The name is what the AI sees this server called.
mcp = FastMCP("hello-world")


@mcp.tool()
def say_hello(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}! Greetings from your first MCP server."


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


if __name__ == "__main__":
    # No transport argument = stdio (the default).
    mcp.run()
