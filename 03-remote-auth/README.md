# 03 — Remote with bearer-token auth

Example 02 with the front door locked. Same transport, but every MCP request must
present `Authorization: Bearer <token>`.

## Concepts introduced

- **`mcp.streamable_http_app()`** — instead of `mcp.run()`, get the raw ASGI
  app so you can add Starlette middleware, then serve it with uvicorn.
- **Bearer-token middleware** — checks the `Authorization` header on every
  MCP request (except the public `/health` probe); 401 + `WWW-Authenticate: Bearer` otherwise.
- **Constant-time comparison** — `hmac.compare_digest`, never `==`, so an
  attacker can't measure how many characters matched.
- **Fail-safe startup** — token shorter than 32 characters → the process exits instead of
  serving unauthenticated. Secure by default beats secure by memo.

## Run

```bash
export MCP_AUTH_TOKEN=$(openssl rand -hex 24)
python server.py            # or: docker compose up remote-auth (token from .env)
```

## Connect

```bash
claude mcp add --transport http remote-auth http://localhost:8103/mcp \
  --header "Authorization: Bearer $MCP_AUTH_TOKEN"
```

For remote hosting and bearer-header client compatibility, see the [root guide](../README.md).

## Verify it's actually locked

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8103/mcp   # 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8103/mcp \
  -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'   # 200
```

## Limits of this scheme

A static bearer token is the right *first* step for a personal server. It does
not give you: per-user identity, expiry/rotation without restarts, or
protection on plain HTTP (use an HTTPS tunnel / reverse proxy). For
multi-user products, the MCP spec defines a full OAuth 2.1 flow.
