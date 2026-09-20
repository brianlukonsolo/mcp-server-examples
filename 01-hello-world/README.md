# 01 — Hello world over HTTP

The first example has two tools: `say_hello(name)` and `add(a, b)`. Tool
docstrings describe capabilities to the client; type hints become input schemas.
Names are bounded and arithmetic rejects non-finite results.

From the repository root:

```bash
python 01-hello-world/server.py
# Another terminal:
python clients/01-hello-client.py
```

The server listens on `http://localhost:8101/mcp`. The client initializes a
session, discovers tools and calls both tools. It does not launch the server.

`common.runtime.create_server` configures FastMCP for Streamable HTTP;
`run` wraps its ASGI app and serves it with Uvicorn. This shared code supplies
host validation, body limits, optional authentication and `/health`.

Connect a compatible client using that URL. All environment variables and remote
hosting instructions are in the [root guide](../README.md). Start with loopback;
set a token and configure HTTPS before exposing a service remotely.
