# Remote MCP clients

Start the matching server first. Every client uses Streamable HTTP; none starts a
server subprocess. All accept MCP_AUTH_TOKEN. Numbered demo clients use MCP_URL to
override endpoints; the generic CLI takes its URL as a positional argument.

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

Install root requirements.txt for every client except the optional Claude agent:

```bash
python -m pip install -r clients/requirements.txt
```

That command installs runtime dependencies plus the Anthropic SDK.

## Generic inspector

```bash
python clients/05-interactive-cli.py http://localhost:8102/mcp --list
python clients/05-interactive-cli.py http://localhost:8102/mcp --call roll_dice --args '{"count": 3}'
python clients/05-interactive-cli.py http://localhost:8108/mcp
```

Interactive commands: `<tool-name> {JSON-object}`, `list`, `quit`. Non-object JSON
is rejected. One-shot tool errors return a failing exit status. Export
MCP_AUTH_TOKEN for protected servers; --token is also supported but exposes the
value in the process command line.

connection.py owns and closes an httpx.AsyncClient and passes it to the SDK's
streamable_http_client. Bearer headers belong on that HTTP client. Read timeouts
allow up to five minutes for streamed tool responses.

## Optional Claude agent

Set ANTHROPIC_API_KEY and ANTHROPIC_MODEL in your shell. Choose a model ID available
in your account; no model name or adaptive-thinking capability is assumed.

```bash
python clients/06-claude-agent.py "What's the weather in London?"
```

The tool runner receives discovered tools and invokes them while answering. The
loop is limited to ten iterations and 4,096 output tokens per model request;
this is a request limit, not a guaranteed spend cap. Calls use your API account
and can perform connected tools' mutations. Use a test instance for writable
examples. Deterministic tests never make paid model calls.

Bare clients and servers do not load .env. See the [root guide](../README.md) for
PowerShell/Bash setup and remote hosting requirements.
