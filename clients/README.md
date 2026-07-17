# MCP Client Examples

The other side of the protocol: programs that *connect to* MCP servers. Same
graded approach as the servers — each client pairs with one of the example
servers, so start the matching server first (or `docker compose up -d` for all
of them).

## The learning path

| # | Client | Pairs with server | What it teaches |
|---|--------|-------------------|-----------------|
| 01 | [01-stdio-client.py](01-stdio-client.py) | 01-hello-world | Spawning a stdio server yourself: initialize → list_tools → call_tool |
| 02 | [02-http-client.py](02-http-client.py) | 02-remote-basic | Connecting over Streamable HTTP; using resources and prompts, not just tools |
| 03 | [03-auth-client.py](03-auth-client.py) | 03-remote-auth | Sending bearer-token headers; what rejection looks like |
| 04 | [04-advanced-client.py](04-advanced-client.py) | 04-tool-features | Live progress bars and server log messages during long tool calls |
| 05 | [05-interactive-cli.py](05-interactive-cli.py) | any server | A generic inspector: list/call tools on any MCP URL, one-shot or REPL |
| 06 | [06-claude-agent.py](06-claude-agent.py) | 04 (or any) | **Claude drives the tools**: the full agentic loop via the Anthropic SDK's tool runner |

## Setup

```bash
pip install -r requirements.txt          # repo root — includes anthropic[mcp]
```

Run everything **from the repo root** (client 01 launches the server by
relative path):

```bash
python clients/01-stdio-client.py

python 02-remote-basic/server.py &                 # or docker compose up -d
python clients/02-http-client.py

export MCP_AUTH_TOKEN=$(openssl rand -hex 24)
python 03-remote-auth/server.py &
python clients/03-auth-client.py

python 04-tool-features/server.py &
python clients/04-advanced-client.py

# the generic CLI works against anything:
python clients/05-interactive-cli.py http://localhost:8102/mcp --list
python clients/05-interactive-cli.py http://localhost:8102/mcp --call roll_dice --args '{"count": 3}'
```

All HTTP clients honour `MCP_URL` if your server runs elsewhere.

## The Claude-powered agent (06)

This is the one that turns everything into an *agent*: Claude receives your
question, sees the MCP server's tools, and loops — plan → call tool → read
result → call again → answer.

```bash
export ANTHROPIC_API_KEY=sk-ant-...      # console.anthropic.com
python 04-tool-features/server.py &
python clients/06-claude-agent.py "Should I cycle in Manchester this weekend?"
```

Watch the output: Claude chains `find_city` → `get_weather` on its own, then
answers with reasoning. Point `MCP_URL` (and `MCP_AUTH_TOKEN` if needed) at
any other server — including your own apps — and it becomes *their* agent.

## Key client-side concepts

- **The handshake** — every session starts with `initialize()`; the result
  tells you the server's name and capabilities.
- **Transport choice** — `stdio_client(StdioServerParameters(...))` when the
  client owns the server process; `streamablehttp_client(url, headers=...)`
  for remote servers (auth headers ride along here).
- **Content blocks** — tool results are lists of typed blocks; check
  `block.type == "text"` before reading `block.text`.
- **Callbacks** — `ClientSession(..., logging_callback=...)` for server logs;
  `call_tool(..., progress_callback=...)` for progress updates.
- **Agentic loop** — you *can* write the request→execute→continue loop by
  hand, but the Anthropic SDK's `tool_runner` + `async_mcp_tool` wrapper does
  it in a few lines (example 06).
