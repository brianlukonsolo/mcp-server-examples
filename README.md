# MCP Server Examples

A graded collection of [Model Context Protocol](https://modelcontextprotocol.io)
servers, from "hello world" to a production-shaped secure API gateway. Every
example works with **Claude** (Claude Code, Claude Desktop, claude.ai
connectors) and **ChatGPT** (developer-mode connectors), because they all use
the transports those clients speak: **stdio** for local servers and
**Streamable HTTP** for remote ones.

## The learning path

| # | Example | Transport | Auth | What it teaches |
|---|---------|-----------|------|-----------------|
| 01 | [hello-world](01-hello-world/) | stdio | — | The absolute minimum: one file, two tools |
| 02 | [remote-basic](02-remote-basic/) | Streamable HTTP | none | A remote server: tools + a resource + a prompt |
| 03 | [remote-auth](03-remote-auth/) | Streamable HTTP | bearer token | The same server, locked down properly |
| 04 | [tool-features](04-tool-features/) | Streamable HTTP | none | Typed params, structured output, errors, async HTTP calls, progress + logging |
| 05 | [task-manager](05-task-manager/) | Streamable HTTP | none | A stateful app: SQLite-backed CRUD the AI can drive |
| 06 | [secure-gateway](06-secure-gateway/) | Streamable HTTP | bearer token | Everything combined: auth + external API + caching + rate limiting + health endpoint |

Work through them in order — each README explains the new concepts it adds.

## Quick start

### Run one example directly

```bash
pip install -r requirements.txt
python 02-remote-basic/server.py
# -> Streamable HTTP MCP server on http://localhost:8102/mcp
```

### Run all the remote examples at once (Docker)

```bash
cp .env.example .env      # then set MCP_AUTH_TOKEN (e.g. openssl rand -hex 24)
docker compose up -d --build
```

| Example | URL |
|---|---|
| 02 remote-basic | `http://localhost:8102/mcp` |
| 03 remote-auth | `http://localhost:8103/mcp` |
| 04 tool-features | `http://localhost:8104/mcp` |
| 05 task-manager | `http://localhost:8105/mcp` |
| 06 secure-gateway | `http://localhost:8106/mcp` |

## Connecting the AI clients

### Claude Code (CLI)

```bash
# local stdio server
claude mcp add hello -- python 01-hello-world/server.py

# remote server, no auth
claude mcp add --transport http remote-basic http://localhost:8102/mcp

# remote server with bearer auth
claude mcp add --transport http remote-auth http://localhost:8103/mcp \
  --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

### Claude Desktop (local stdio servers)

Add to `claude_desktop_config.json`:

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

### claude.ai and ChatGPT (remote connectors)

Both need a **publicly reachable HTTPS URL**. From your machine, tunnel one
example:

```bash
cloudflared tunnel --url http://localhost:8102     # or: ngrok http 8102
```

Then add `https://<tunnel-host>/mcp` as a custom connector. For the
authenticated examples (03, 06), also supply the
`Authorization: Bearer <token>` header in the connector's auth settings.

> ChatGPT: connectors are added under Settings → Connectors (developer mode
> must be enabled for custom MCP connectors).

## Security ladder

- **01–02** have no auth. Fine for localhost experiments; never tunnel these.
- **03** shows the minimum viable protection: a static bearer token checked
  with a constant-time comparison, and a server that *refuses to start*
  without a token configured.
- **06** adds the rest of what a real deployment wants: per-client rate
  limiting, an unauthenticated `/health` probe, and upstream API caching.
- Plain HTTP means the token is visible on-path — for anything beyond your
  LAN, terminate TLS in front (a tunnel like cloudflared/ngrok does this for
  you).

## Requirements

- Python 3.11+ (`pip install -r requirements.txt` — the `mcp` SDK, `httpx`, `uvicorn`)
- Docker Desktop only if you want the compose setup
