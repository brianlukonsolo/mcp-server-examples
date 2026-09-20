# 01 — Hello world over HTTP

The first example has two tools: `say_hello(name)` and `add(a, b)`. Tool
docstrings describe capabilities to the client; type hints become input schemas.
Names are bounded and arithmetic rejects non-finite results.

## Run with Docker

Set up `.env` once using the [Docker quick start](../README.md#start-with-docker).
Then run these commands from the repository root:

```bash
docker compose up -d --build hello-world
docker compose exec hello-world python clients/01-hello-client.py
```

The client connects over HTTP and inherits the container's authentication token.
For a host Python setup, see [MANUAL.md](../MANUAL.md).

The server listens on `http://localhost:8101/mcp`. The client initializes a
session, discovers tools and calls both tools. It does not launch the server.

`common.runtime.create_server` configures FastMCP for Streamable HTTP;
`run` wraps its ASGI app and serves it with Uvicorn. This shared code supplies
host validation, body limits, authentication and `/health`.

Connect a compatible client using that URL. All environment variables and remote
hosting instructions are in the [root guide](../README.md). Compose publishes
loopback ports with authentication; configure HTTPS before exposing a service remotely.
