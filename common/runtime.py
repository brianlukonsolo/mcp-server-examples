"""Remote-only FastMCP construction and bounded ASGI ingress."""
import asyncio
import hmac
import os
import time
from collections import OrderedDict, deque

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse


def integer_env(name: str, default: int, minimum: int = 1, maximum: int = 1_000_000) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def create_server(name: str, port: int, instructions: str = "") -> FastMCP:
    hosts = ["localhost:*", "127.0.0.1:*", "[::1]:*"]
    hosts += [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if any("/" in h or "*" in h for h in hosts[3:]):
        raise ValueError("MCP_ALLOWED_HOSTS requires exact hostnames with optional ports, without schemes")
    origins = [f"{scheme}://{host}" for host in hosts for scheme in ("http", "https")]
    mcp = FastMCP(name, instructions=instructions, host=os.getenv("HOST", "127.0.0.1"),
                  port=integer_env("PORT", port, maximum=65535), stateless_http=True,
                  transport_security=TransportSecuritySettings(
                      enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins))

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):
        return JSONResponse({"status": "ok", "service": name})

    return mcp


class Ingress:
    """Pure ASGI: authenticate before reading; preserve outbound SSE streaming.

    Rate limits are process-local and use socket peer IPs, never untrusted
    forwarded headers. At a proxy this intentionally limits the proxy as a unit.
    """
    def __init__(self, app, token: str, limit: int = 120, max_body: int = 1_048_576):
        self.app, self.token, self.limit, self.max_body = app, token.encode(), limit, max_body
        self.windows = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def reject(status, message, **headers):
            await JSONResponse({"error": message}, status_code=status, headers=headers)(scope, receive, send)

        if scope["path"] == "/health" and scope["method"] == "GET":
            return await self.app(scope, receive, send)
        auth = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
        if self.token and (len(auth) != 1 or not hmac.compare_digest(auth[0], b"Bearer " + self.token)):
            return await reject(401, "Missing or invalid bearer token", **{"WWW-Authenticate": "Bearer"})
        now = time.monotonic()
        peer = (scope.get("client") or ("unknown",))[0]
        if peer not in self.windows and len(self.windows) >= 4096:
            self.windows.popitem(last=False)
        window = self.windows.setdefault(peer, deque())
        self.windows.move_to_end(peer)
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self.limit:
            return await reject(429, "Rate limit exceeded", **{"Retry-After": str(max(1, int(61 - now + window[0])))})
        window.append(now)
        lengths = [v for k, v in scope["headers"] if k.lower() == b"content-length"]
        if len(lengths) > 1 or (lengths and (not lengths[0].isdigit() or len(lengths[0]) > 12)):
            return await reject(400, "Invalid Content-Length")
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > self.max_body:
            return await reject(413, "Request body too large")
        body = bytearray()
        try:
            async with asyncio.timeout(15):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > self.max_body:
                        return await reject(413, "Request body too large")
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, "Request body timed out")
        if declared is not None and declared != len(body):
            return await reject(400, "Content-Length does not match body")
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"), (b"cache-control", b"no-store")]
            await send(message)

        await self.app(scope, replay, secured_send)


def application(mcp: FastMCP, require_auth: bool = False):
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if (require_auth or os.getenv("ENVIRONMENT") == "production") and len(token) < 32:
        raise ValueError("Set MCP_AUTH_TOKEN to a random token of at least 32 characters")
    if token and (not token.isascii() or any(c.isspace() for c in token)):
        raise ValueError("MCP_AUTH_TOKEN must contain only non-whitespace ASCII characters")
    return Ingress(mcp.streamable_http_app(), token,
                   limit=integer_env("RATE_LIMIT_PER_MINUTE", 120),
                   max_body=integer_env("MAX_REQUEST_BYTES", 1_048_576, maximum=16_777_216))


def run(mcp: FastMCP, require_auth: bool = False):
    uvicorn.run(application(mcp, require_auth), host=mcp.settings.host, port=mcp.settings.port,
                proxy_headers=False, limit_concurrency=100, timeout_graceful_shutdown=15)


async def report_progress(ctx, progress: float, total: float):
    """Route progress to the POST SSE stream in stateless MCP SDK 1.x.

    Context.report_progress in SDK 1.28.1 omits related_request_id, sending
    progress to a standalone GET stream that stateless clients do not have.
    """
    meta = ctx.request_context.meta
    if meta is not None and meta.progressToken is not None:
        await ctx.session.send_progress_notification(
            progress_token=meta.progressToken, progress=progress, total=total,
            related_request_id=ctx.request_id)
