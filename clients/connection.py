"""Shared remote transport; owns and closes its HTTP client and MCP session."""
import os
import json
from contextlib import asynccontextmanager

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def json_result(result):
    """Read JSON tools from structuredContent or a legacy text content block."""
    if result.isError:
        raise RuntimeError(result.content)
    if result.structuredContent is not None:
        return result.structuredContent
    text = "\n".join(block.text for block in result.content if block.type == "text")
    return json.loads(text)


@asynccontextmanager
async def remote_transport(url: str, headers: dict | None = None):
    if headers is None:
        token = os.getenv("MCP_AUTH_TOKEN", "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30, read=300)) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            yield streams


@asynccontextmanager
async def session(url: str):
    async with remote_transport(url) as (read, write, _):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client
