# 01 — Hello World (stdio)

The absolute minimum MCP server: ~20 lines, two tools, no network, no auth.

**Transport:** stdio — the AI client starts the process itself and exchanges
JSON-RPC over stdin/stdout. There is no port and nothing to secure; only
programs on your machine that can launch the script can talk to it.

## Concepts introduced

- `FastMCP("name")` — creates a server; the name is shown to the AI.
- `@mcp.tool()` — any typed Python function becomes a callable tool. The
  **docstring becomes the tool description** the model reads to decide when to
  call it, and the **type hints become the input schema** — write both well.
- `mcp.run()` — with no arguments, serves over stdio.

## Connect

Claude Code:

```bash
claude mcp add hello -- python 01-hello-world/server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hello": {
      "command": "python",
      "args": ["C:/path/to/mcp-server-examples/01-hello-world/server.py"]
    }
  }
}
```

Then ask: *"Use the hello server to greet Brian and add 2.5 and 4"*.

> stdio servers can't be used by claude.ai or ChatGPT — those need a remote
> HTTP server, which is exactly what example 02 covers.
