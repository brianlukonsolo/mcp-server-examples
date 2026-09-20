# MCP server and client examples

Nine examples, from two simple tools to transactional applications. **Docker
Compose is the default way to run them; no host Python installation is needed.**
Every server exposes remote Streamable HTTP at `/mcp` and a liveness probe at
`/health`.

## Start with Docker

Install Docker Desktop (or Docker Engine with the Compose plugin), start Docker,
and run these commands from the repository root.

1. Copy `.env.example` to `.env` if you do not already have one:

   ```powershell
   # PowerShell
   Copy-Item .env.example .env
   ```

   ```bash
   # Bash
   cp .env.example .env
   ```

2. Generate a token with Docker, then paste the output into `MCP_AUTH_TOKEN` in
   `.env`. Keep your existing token if it already has at least 32 random characters.

   ```bash
   docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(24))"
   ```

3. Build and start all nine services:

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

4. Call the hello-world server using a client inside its container:

   ```bash
   docker compose exec hello-world python clients/01-hello-client.py
   ```

The client connects over HTTP and inherits the container's bearer token. All
Compose services run in production mode with authentication, including the first
example. Ports are published only on `127.0.0.1`.

To start just one example:

```bash
docker compose up -d --build workflow-engine
docker compose exec workflow-engine python clients/07-workflow-client.py
```

The workflow demo deliberately fails one step, retries it, and prints the saved
results. All commands in the example guides run from the repository root.

## Learning path

| # | Example | Default port | What it teaches |
|---|---|---:|---|
| 01 | [Hello world](01-hello-world/) | 8101 | Tools, typed inputs, remote initialization |
| 02 | [Remote basic](02-remote-basic/) | 8102 | Tools, resources and prompts |
| 03 | [Remote auth](03-remote-auth/) | 8103 | Required bearer authentication |
| 04 | [Tool features](04-tool-features/) | 8104 | Async upstream calls, structured results, progress and logging |
| 05 | [Task manager](05-task-manager/) | 8105 | Persistent SQLite CRUD and pagination |
| 06 | [Secure gateway](06-secure-gateway/) | 8106 | Bounded TTL caching, rate limiting, upstream failures |
| 07 | [Knowledge base](07-knowledge-base/) | 8107 | FTS5 search, immutable revisions, optimistic concurrency |
| 08 | [Workflow engine](08-workflow-engine/) | 8108 | DAG validation, durable checkpoints, retries, cancellation |
| 09 | [Inventory reservations](09-inventory-reservations/) | 8109 | Atomic multi-item reservations, idempotency, audit trails |

## Connect clients

A compatible MCP client on your computer can connect to
`http://localhost:<port>/mcp` using `Authorization: Bearer <your .env token>`.
For example, hello-world uses `http://localhost:8101/mcp`.

The bundled clients can run inside the containers without installing anything
on your host. To inspect the knowledge-base tools interactively:

```bash
docker compose up -d --build knowledge-base
docker compose exec knowledge-base python clients/05-interactive-cli.py http://localhost:8107/mcp
```

Enter `list` to discover tools, `<tool-name> {JSON-object}` to call one, or `quit`
to exit. See the [client guide](clients/README.md) for all client commands.

## Manage the services and data

```bash
docker compose logs --tail=100 workflow-engine
docker compose restart workflow-engine
docker compose down
```

All services share one image and run as UID 10001 with read-only application
files. Task manager, knowledge base, workflow engine and inventory reservations
each have a writable named volume mounted at `/app/data`. Data survives container
recreation and `docker compose down`; adding `-v` deletes the volumes.

After changing `.env`, run `docker compose up -d` to recreate affected containers
with the new configuration. `restart` alone does not apply environment changes.
After changing source files, use `docker compose up -d --build`.

## Compose configuration

Compose reads these settings from `.env`:

| Variable | Default | Meaning |
|---|---|---|
| `MCP_AUTH_TOKEN` | Required | Random bearer token of at least 32 characters |
| `MCP_ALLOWED_HOSTS` | Localhost addresses only | Additional exact public hostnames, optionally with ports; comma-separated |
| `RATE_LIMIT_PER_MINUTE` | 120 | Request limit per socket peer IP, per process |
| `MAX_REQUEST_BYTES` | 1048576 | Request body ceiling; reading also has a 15-second deadline |

Compose sets each service's port, `HOST=0.0.0.0`, `ENVIRONMENT=production`, and
`DATA_DIR=/app/data` inside the container. Task manager also uses
`TASKS_DB=/app/data/tasks.db`. These are service settings in
[docker-compose.yml](docker-compose.yml), not additional `.env` substitutions.
The gateway cache defaults to 300 seconds and at most 256 entries; change
`CACHE_TTL_SECONDS` through a service environment override if needed.

## Access from another machine

Terminate HTTPS at a reverse proxy and set `MCP_ALLOWED_HOSTS` to the public
hostname, e.g. `knowledge.example.com`. Preserve the original Host header. A
proxy on the same host can reach the loopback-published ports; a containerized
proxy can join the Compose network. Public DNS, TLS and hosting are not
provisioned here. Connect remote clients to `https://<public-host>/mcp`.

Host and Origin validation remain enabled on `/mcp`. `/health` is public and
reports liveness only. Rate limits use the socket peer rather than forwarded
headers: behind a proxy, clients share its quota. Caches and rate limits are
process-local, not distributed.

Static bearer tokens demonstrate service authentication. They do not implement
OAuth discovery, consent, scopes, user identity or tenant isolation. Use a client
that supports custom bearer headers; clients requiring OAuth need an OAuth
implementation before they can connect.

## Advanced walkthroughs

- [Knowledge base](07-knowledge-base/README.md): create, search and version
  documents, then try a stale edit.
- [Workflow engine](08-workflow-engine/README.md): checkpoint a branching
  pipeline, retry a failed step, and inspect saved outputs.
- [Inventory](09-inventory-reservations/README.md): reserve multiple SKUs
  atomically, retry safely, then confirm or release the reservation.

Each walkthrough includes Compose startup and a container-based client command.

## Validate with Docker

Run isolated tests without starting the Compose services or mounting their data:

```bash
docker build -t mcp-server-examples:local .
docker run --rm --read-only --tmpfs /tmp:mode=1777 mcp-server-examples:local python -m unittest discover -s tests -v
docker run --rm --read-only --tmpfs /tmp:mode=1777 mcp-server-examples:local python scripts/smoke_remote.py
```

The regression suite covers rollback, concurrency, retries, bounds and ingress
failures. HTTP smoke tests launch all nine servers inside the test container,
using temporary databases and ports, and exercise tools, clients, resources and
progress. Weather calls are mocked; paid model calls are not required.

GitHub Actions also tests Windows, Linux and database persistence across container
restarts. The [manual validation guide](MANUAL.md#validation) covers running
those host-side checks and the Docker orchestration test script.

## Manual development and migration

For running servers or clients directly on your host, virtualenv setup, optional
Claude agent setup and host environment variables, use [MANUAL.md](MANUAL.md).

Example 01 now uses port 8101 and `clients/01-hello-client.py`. Replace old
command/args client entries with its Streamable HTTP URL. There are no stdio
server entry points. Existing task databases remain compatible; manual and
Compose execution use different data locations, described in the manual guide.

The shared runtime uses `FastMCP.streamable_http_app()` served by Uvicorn.
See the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1)
for the underlying APIs. Progress notifications are explicitly routed to the
active POST stream for compatibility with stateless HTTP in SDK 1.28.1.
