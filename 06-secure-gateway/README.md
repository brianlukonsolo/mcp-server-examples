# 06 — Secure API gateway

The capstone: everything from examples 02–05 combined into the shape a real
personal deployment should take. It fronts the free Open-Meteo API, but the
pattern applies to any upstream service (swap the fetches, keep the shell).

## Concepts introduced

- **Auth + open health probe** — bearer token on everything *except*
  `/health`, so monitors and load balancers can check liveness without
  credentials. Added via `@mcp.custom_route`.
- **TTL response caching** — identical upstream requests within 5 minutes are
  served from memory. Models often re-ask for the same data; don't make the
  upstream pay for that.
- **Rate limiting** — a sliding one-minute window per client IP returns 429 +
  `Retry-After` when exceeded. A runaway agent loop can fire tools far faster
  than a human ever would.
- **Upstream error translation** — timeouts and 5xx from the API are caught
  and re-raised as messages the model can act on ("try again shortly"), rather
  than raw tracebacks.

## Run

```bash
export MCP_AUTH_TOKEN=$(openssl rand -hex 24)
python server.py            # -> http://localhost:8106/mcp
curl http://localhost:8106/health    # no auth needed -> {"status": "ok"}
```

## Connect

```bash
claude mcp add --transport http secure-gateway http://localhost:8106/mcp \
  --header "Authorization: Bearer $MCP_AUTH_TOKEN"
```

Then: *"What's the weekend weather in London vs Lisbon? Recommend one for a
bike ride."*

## Where to go from here

- Swap Open-Meteo for any API you actually use (add its key as another env var).
- Put the server behind HTTPS (reverse proxy or tunnel) before exposing it.
- For multi-user products, replace the static token with the MCP OAuth 2.1 flow.

The cache is bounded to 256 entries. Expired entries are removed when queried or
when stats are requested. The shared ingress defaults to 120 requests per minute
per socket peer; it does not trust forwarded IP headers. Configure exact public
hostnames before using a proxy (see the [root guide](../README.md)).
