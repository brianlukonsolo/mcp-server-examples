# Manual host development

[Docker Compose is the recommended setup](README.md#start-with-docker). This
optional guide is for running Python servers and clients directly on your host.
Use Python 3.11 or newer; CI and the Docker image use Python 3.12. Run commands
from the repository root and keep the `common/` directory with the examples.

## Install dependencies

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Bash:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Activate the virtualenv in each additional terminal too. If PowerShell activation
is unavailable, invoke `.\.venv\Scripts\python.exe` in place of `python`.

## Start a server and client

In the server terminal:

```bash
python 01-hello-world/server.py
```

In a second terminal with the virtualenv activated:

```bash
python clients/01-hello-client.py
```

The endpoint is `http://localhost:8101/mcp`. See the [learning path](README.md#learning-path)
for the other server folders and ports. Stop a foreground server with Ctrl+C.
If Compose already occupies that port, stop the corresponding Compose service or
choose another `PORT` and point the client at it with `MCP_URL`.

## Authentication and environment variables

Bare Python servers and clients do **not** load `.env`. Export variables in the
terminal. Examples 03 and 06–09 require a random token of at least 32 characters.
Examples 01, 02, 04 and 05 permit unauthenticated local development; setting a
token enables authentication, and `ENVIRONMENT=production` requires it on all servers.

Generate a token once:

```bash
python -c "import secrets; print(secrets.token_hex(24))"
```

Copy that same generated token into both server and client terminals. PowerShell:

```powershell
$env:MCP_AUTH_TOKEN = "paste-your-generated-token"
python 08-workflow-engine/server.py
# In another activated terminal, set the same MCP_AUTH_TOKEN, then:
python clients/07-workflow-client.py
```

Bash:

```bash
export MCP_AUTH_TOKEN='paste-your-generated-token'
python 08-workflow-engine/server.py
# In another activated terminal, export the same MCP_AUTH_TOKEN, then:
python clients/07-workflow-client.py
```

| Variable | Host default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | Listener address |
| `PORT` | Per-example port (8101–8109) | Listener port |
| `MCP_AUTH_TOKEN` | Empty | Bearer token |
| `ENVIRONMENT` | Development unless set | `production` requires authentication |
| `MCP_ALLOWED_HOSTS` | Localhost addresses | Additional exact hostnames, optionally with ports |
| `RATE_LIMIT_PER_MINUTE` | 120 | Requests per socket peer per process |
| `MAX_REQUEST_BYTES` | 1048576 | Body size limit |
| `CACHE_TTL_SECONDS` | 300 | Gateway cache lifetime |
| `TASKS_DB` | `05-task-manager/tasks.db` | Task database path |
| `DATA_DIR` | Repository `data/` | New examples' database directory |

`HOST=0.0.0.0` permits connections on other interfaces. Configure authentication,
allowed hosts and HTTPS before remote access; see the [deployment notes](README.md#access-from-another-machine).

Host databases and Compose named volumes are separate. Switching launch methods
does not migrate existing records. Stop writes and make a consistent SQLite
backup before copying a database into a different data location; the container
user (UID 10001) must be able to write its database and parent directory.

## Run clients on the host

A host client can connect to either a manual server or a Compose-published URL.
Use the server's token; for Compose, copy `MCP_AUTH_TOKEN` from `.env` into the
client terminal's environment.

```bash
python clients/02-http-client.py
python clients/03-auth-client.py
python clients/04-advanced-client.py
python clients/05-interactive-cli.py http://localhost:8107/mcp --list
python clients/05-interactive-cli.py http://localhost:8107/mcp
python clients/07-workflow-client.py
python clients/08-inventory-client.py
```

Numbered demo clients honor `MCP_URL`; the generic CLI takes an explicit URL.
For a different endpoint:

```powershell
$env:MCP_URL = "http://localhost:9001/mcp"
python clients/01-hello-client.py
```

```bash
export MCP_URL='http://localhost:9001/mcp'
python clients/01-hello-client.py
```

The generic CLI accepts interactive commands such as `roll_dice {"count":3}`.
Its `--args` option also accepts JSON for one-shot calls; shell quoting varies,
so interactive mode is the simplest way to paste JSON on either platform.

## Optional Claude agent

The default server image contains the MCP clients but not the Anthropic SDK.
Install the optional dependency in your host virtualenv:

```bash
python -m pip install -r clients/requirements.txt
```

Set `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (a model ID available in your account),
and `MCP_AUTH_TOKEN` in your shell. The default target is tool-features at port
8104; start it with Compose or manually, or set `MCP_URL` to another endpoint.

PowerShell:

```powershell
$env:ANTHROPIC_API_KEY = "your-api-key"
$env:ANTHROPIC_MODEL = "your-model-id"
python clients/06-claude-agent.py "What's the weather in London?"
```

Bash:

```bash
export ANTHROPIC_API_KEY='your-api-key'
export ANTHROPIC_MODEL='your-model-id'
python clients/06-claude-agent.py "What's the weather in London?"
```

The tool runner discovers MCP tools and calls them while answering. It allows
up to ten iterations and 4,096 output tokens per model request; this is not a
spending cap. Calls use your paid API account and may mutate the connected
service's data. Use a test instance for writable examples. See the
[Anthropic tool runner documentation](https://github.com/anthropics/anthropic-sdk-python/blob/main/tools.md).

## Validation

With the virtualenv activated:

```bash
python -m unittest discover -s tests -v
python scripts/smoke_remote.py
```

The HTTP test runner uses temporary databases, ephemeral ports and test tokens.
It does not require running Compose services or external API credentials.

To test container workflows and database persistence, keep Docker running, then
run the orchestration script from the host virtualenv:

```bash
docker build -t mcp-server-examples:local .
python scripts/smoke_containers.py
```

This script controls Docker from the host, creates disposable containers and
volumes, verifies data across restarts, and removes its test resources afterward.
It never mounts the application's existing data. For tests needing only Docker,
see [the root guide](README.md#validate-with-docker).
