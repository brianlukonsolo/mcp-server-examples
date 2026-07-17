# 05 — Task manager (stateful CRUD with SQLite)

The first example that's an actual *application*: a to-do list that persists
in SQLite, driven entirely by the AI. Ask Claude to plan your week and watch
it add, complete, and re-prioritise tasks.

## Concepts introduced

- **Persistent state** — a SQLite database (`tasks.db`) survives restarts.
  `stateless_http` refers to the *transport*; your app state can live wherever
  you want.
- **CRUD tool design** — create/read/update/delete as separate small tools,
  each with tight validation and structured returns. Small orthogonal tools
  beat one mega-tool: the model composes them.
- **Meaningful errors** — completing a non-existent task raises
  `ValueError("No open task with id 7")`, which the model reads and recovers
  from (usually by calling `list_tasks` to check).
- **A dynamic resource** — `tasks://all` renders the current list as text so
  a user/model can pull the whole state into context in one read.

## Run

```bash
python server.py            # -> http://localhost:8105/mcp
```

The database file is created next to the script (override with `TASKS_DB`).
In Docker the state is ephemeral unless you mount a volume.

## Try it

> *"Add three tasks for my video pipeline: record gameplay (high, due Friday),
> edit highlights (medium), design thumbnail (low). Then show me stats."*

> *"I finished the recording — mark it done and tell me what's next."*
