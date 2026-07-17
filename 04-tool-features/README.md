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
  `await ctx.report_progress(done, total)` and `await ctx.info("...")` while it
  runs, so long jobs aren't a silent wait.
- **Clear errors** — validate early, raise `ValueError` with a message the
  model can act on.

## Run

```bash
python server.py            # -> http://localhost:8104/mcp
```

## Try it

Connect (`claude mcp add --transport http tool-features http://localhost:8104/mcp`)
and ask:

> *"What's the weather looking like in Manchester for the next 5 days?"*
> (watch it chain find_city → get_weather)

> *"Run a batch job of 30 items"* (watch the progress updates)
