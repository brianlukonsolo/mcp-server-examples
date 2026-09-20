# 04 — Tool features in depth

Tools are the heart of MCP; this example is about making them *good*. It wraps
the free Open-Meteo weather API (no key required) plus some local tools.

## Concepts introduced

- **Async tools** — `async def` + `httpx.AsyncClient` for non-blocking calls
  to external APIs.
- **Tool chaining by design** — `find_city` returns coordinates that
  `get_weather` accepts, and the docstrings tell the model to use them in that
  order. Good descriptions are what make multi-step tool use work.
- **Constrained parameters** — `Literal["celsius", "fahrenheit"]` becomes an
  enum in the schema, so the model can't pass junk.
- **Optional parameters** — `top_words: Optional[int] = None` for behavior
  that's opt-in.
- **Structured results** — return dicts/lists, not prose; the model reasons
  better over structure.
- **Progress + logging** — a tool taking a `ctx: Context` parameter can call
  `await report_progress(ctx, done, total)` and `await ctx.info("...")` while it
  runs, so long jobs aren't a silent wait.
- **Clear errors** — validate early, raise `ValueError` with a message the
  model can act on.

## Run with Docker

Set up `.env` once using the [Docker quick start](../README.md#start-with-docker).
Then run these commands from the repository root:

```bash
docker compose up -d --build tool-features
docker compose exec tool-features python clients/04-advanced-client.py
```

The client connects over HTTP and inherits the container's authentication token.
For a host Python setup, see [MANUAL.md](../MANUAL.md).

## Try it

Connect an MCP client to `http://localhost:8104/mcp` with the bearer token from
`.env`, then ask:

> *"What's the weather looking like in Manchester for the next 5 days?"*
> (watch it chain find_city → get_weather)

> *"Run a batch job of 30 items"* (watch the progress updates)

The shared progress helper associates notifications with the active POST request,
so they reach stateless HTTP clients. Upstream inputs, response bodies and timeouts
are bounded; network errors become explicit tool errors.
