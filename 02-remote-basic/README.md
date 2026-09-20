# 02 — Tools, resources and prompts

This example adds MCP's other primitives to an HTTP server:

- `roll_dice`, `current_time`, `convert_temperature`: callable tools.
- `info://server`: a read-only resource.
- `brainstorm(topic)`: a reusable prompt template.

## Run with Docker

Set up `.env` once using the [Docker quick start](../README.md#start-with-docker).
Then run these commands from the repository root:

```bash
docker compose up -d --build remote-basic
docker compose exec remote-basic python clients/02-http-client.py
```

The client connects over HTTP and inherits the container's authentication token.
For a host Python setup, see [MANUAL.md](../MANUAL.md).

The endpoint is `http://localhost:8102/mcp`. Requests are stateless at the transport
layer; clients still initialize their MCP session before listing or calling tools.

Compose runs this example with authentication enabled. See the [root guide](../README.md)
for HTTPS, host validation and client compatibility.
