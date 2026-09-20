"""01 — Hello World: start an HTTP server, then connect a client to /mcp."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.runtime import create_server, run


import math

# The name is what the AI sees this server called.
mcp = create_server("hello-world", 8101)


@mcp.tool()
def say_hello(name: str) -> str:
    """Greet someone by name."""
    if not name.strip() or len(name) > 200:
        raise ValueError("name must contain 1-200 characters")
    return f"Hello, {name}! Greetings from your first MCP server."


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    result = a + b
    if not math.isfinite(result):
        raise ValueError("Sum must be finite")
    return result


if __name__ == "__main__":
    run(mcp, require_auth=False)
