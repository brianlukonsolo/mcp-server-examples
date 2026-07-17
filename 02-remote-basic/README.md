# 02 — Remote basic (Streamable HTTP, no auth)

The first *remote* server: reachable over the network at
`http://localhost:8102/mcp`, so hosted clients (claude.ai, ChatGPT) can
connect to it — via an HTTPS tunnel — as well as Claude Code locally.

## Concepts introduced

- **Streamable HTTP transport** — `mcp.run(transport="streamable-http")` with
  `host`/`port` on the constructor. The endpoint is always `/mcp`.
- **`stateless_http=True`** — each request is self-contained. Best
  compatibility with hosted connectors that don't pin sessions to one node.
- **Resources** — `@mcp.resource("info://server")` exposes read-only data the
  client can load into context (like a GET endpoint).
- **Prompts** — `@mcp.prompt()` exposes reusable prompt templates the user can
  invoke.
- **Input validation** — raise `ValueError` with a clear message; the client
  shows the model the error so it can correct itself.

## Run

```bash
python server.py            # or: docker compose up remote-basic
```

## Connect

```bash
claude mcp add --transport http remote-basic http://localhost:8102/mcp
```

For claude.ai / ChatGPT: `cloudflared tunnel --url http://localhost:8102`,
then add `https://<tunnel-host>/mcp` as a custom connector.

## ⚠️ Security

**None.** Anyone who can reach port 8102 can call these tools. Harmless here
(dice and temperatures), but the moment tools touch files, money, or accounts
you need example 03.
