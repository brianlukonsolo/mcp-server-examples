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

## Run with Docker

Set up `.env` once using the [Docker quick start](../README.md#start-with-docker).
Then run these commands from the repository root:

```bash
docker compose up -d --build remote-auth
docker compose exec remote-auth python clients/03-auth-client.py
```

The client connects over HTTP and inherits the container's authentication token.
For a host Python setup, see [MANUAL.md](../MANUAL.md).

## Connect

Use the token you configured in `.env` for an external client:

```bash
claude mcp add --transport http remote-auth http://localhost:8103/mcp \
  --header "Authorization: Bearer <token-from-.env>"
```

For remote hosting and bearer-header client compatibility, see the [root guide](../README.md).

## Verify authentication

The container client command above first makes a request without credentials and
requires HTTP 401, then connects with the inherited bearer token and calls the
protected tools. The public `/health` probe remains available without a token.

## Limits of this scheme

A static bearer token is the right *first* step for a personal server. It does
not give you: per-user identity, expiry/rotation without restarts, or
protection on plain HTTP (use an HTTPS tunnel / reverse proxy). For
multi-user products, the MCP spec defines a full OAuth 2.1 flow.
