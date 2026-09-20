# Remote MCP clients

Run the bundled clients inside the matching Compose service. They connect over
Streamable HTTP and inherit its `MCP_AUTH_TOKEN`; no host Python installation is
needed. Set up `.env` using the [Docker quick start](../README.md#start-with-docker).
All commands below run from the repository root.

## Run a client with Docker

```bash
docker compose up -d --build hello-world
docker compose exec hello-world python clients/01-hello-client.py
```

Other examples use the same pattern:

```bash
docker compose up -d --build remote-basic remote-auth tool-features workflow-engine inventory-reservations
docker compose exec remote-basic python clients/02-http-client.py
docker compose exec remote-auth python clients/03-auth-client.py
docker compose exec tool-features python clients/04-advanced-client.py
docker compose exec workflow-engine python clients/07-workflow-client.py
docker compose exec inventory-reservations python clients/08-inventory-client.py
```

The workflow and inventory clients write demonstration data; use test instances.
Inventory retains sample stock and audit records after the demo.

## Client reference

| Client | Server | Teaches |
|---|---|---|
| [01-hello-client.py](01-hello-client.py) | 01, port 8101 | Initialize, discover, call |
| [02-http-client.py](02-http-client.py) | 02, port 8102 | Tools, resources, prompts |
| [03-auth-client.py](03-auth-client.py) | 03, port 8103 | Verify an actual 401, then authenticate |
| [04-advanced-client.py](04-advanced-client.py) | 04, port 8104 | Streaming progress and logs |
| [05-interactive-cli.py](05-interactive-cli.py) | Any | Discovery, one-shot calls, REPL |
| [06-claude-agent.py](06-claude-agent.py) | 04 by default | Optional model-driven tool loop |
| [07-workflow-client.py](07-workflow-client.py) | 08, port 8108 | Checkpoints, failure and retry |
| [08-inventory-client.py](08-inventory-client.py) | 09, port 8109 | Idempotent reservations |

The optional Claude agent has a separate dependency and credential setup in
[MANUAL.md](../MANUAL.md#optional-claude-agent); it is not included in the default
server image's installed dependencies.

## Generic inspector

```bash
docker compose up -d --build remote-basic
docker compose exec remote-basic python clients/05-interactive-cli.py http://localhost:8102/mcp --list
docker compose exec remote-basic python clients/05-interactive-cli.py http://localhost:8102/mcp
```

In interactive mode, enter `<tool-name> {JSON-object}`, `list`, or `quit`. Example:

```text
roll_dice {"count": 3}
```

Non-object JSON is rejected. One-shot tool errors return a failing exit status.
The generic CLI takes the URL as a positional argument. Numbered clients accept
`MCP_URL` for an alternative endpoint. When using `docker compose exec`, localhost
refers to that service's container, so the commands above run each client inside
its matching server container.

The token is already in the container environment; no `--token` argument is
needed. Clients on your host or another machine need the same token and the
published or public URL; see [manual client setup](../MANUAL.md#run-clients-on-the-host).

## Implementation notes

`connection.py` owns and closes an `httpx.AsyncClient` and passes it to the SDK's
`streamable_http_client`. Bearer headers belong on that HTTP client. Read timeouts
allow up to five minutes for streamed tool responses. Every client initializes
its MCP session before discovering or calling tools.
