# 02 — Tools, resources and prompts

This example adds MCP's other primitives to an HTTP server:

- `roll_dice`, `current_time`, `convert_temperature`: callable tools.
- `info://server`: a read-only resource.
- `brainstorm(topic)`: a reusable prompt template.

```bash
python 02-remote-basic/server.py
# Another terminal:
python clients/02-http-client.py
```

The endpoint is `http://localhost:8102/mcp`. Requests are stateless at the transport
layer; clients still initialize their MCP session before listing or calling tools.

Authentication is optional for local exploration. The shared runtime enables it
when `MCP_AUTH_TOKEN` is set; production requires a token. See the [root guide](../README.md)
for host validation, HTTPS and client compatibility rather than tunneling an open service.
