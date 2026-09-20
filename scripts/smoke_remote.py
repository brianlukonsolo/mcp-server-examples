"""Exercise every example over real TCP using initialized MCP SDK sessions.

No external API calls, credentials, existing databases or default ports needed.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "local-smoke-token-" + "x" * 32


async def exercise(url: str, number: int):
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert (await session.list_tools()).tools

                async def call(name, args=None, **kwargs):
                    result = await session.call_tool(name, args or {}, **kwargs)
                    assert not result.isError, (name, result.content)
                    if result.structuredContent is not None:
                        content = result.structuredContent
                        return content.get("result", content)
                    return json.loads(result.content[0].text)

                if number == 1:
                    assert await call("add", {"a": 2, "b": 3}) == 5
                elif number == 2:
                    assert (await call("roll_dice", {"sides": 6, "count": 2}))["total"] >= 2
                    assert (await session.read_resource("info://server")).contents
                    assert (await session.get_prompt("brainstorm", {"topic": "tests"})).messages
                elif number == 3:
                    assert len(await call("generate_password", {"length": 24})) == 24
                elif number == 4:
                    progress = []
                    async def track(value, total, message):
                        progress.append(value)
                    await call("simulate_batch_job", {"items": 3}, progress_callback=track)
                    assert progress == [1, 2, 3], progress
                    assert (await call("text_stats", {"text": "hello world"}))["words"] == 2
                elif number == 5:
                    task = await call("add_task", {"title": "smoke task"})
                    assert (await call("complete_task", {"task_id": task["id"]}))["done"]
                    await call("delete_task", {"task_id": task["id"]})
                    await call("add_task", {"title": "Persistence check"})
                elif number == 6:
                    assert (await call("gateway_stats"))["cache_entries"] == 0
                elif number == 7:
                    definition = next(t for t in (await session.list_tools()).tools if t.name == "put_document")
                    assert definition.outputSchema is not None
                    await call("put_document", {"slug": "guide", "title": "Guide", "body": "searchable content"})
                    results = await call("search_documents", {"query": "searchable"})
                    assert results[0]["slug"] == "guide"
                    assert (await session.read_resource("knowledge://documents/guide")).contents
                elif number == 8:
                    job = await call("create_workflow", {"request_key": "smoke", "values": [1, 2], "steps": [
                        {"name": "retry", "operation": "fail_once"},
                        {"name": "sum", "operation": "sum", "depends_on": ["retry"]}]})
                    assert (await call("run_workflow", {"workflow_id": job["id"]}))["state"] == "failed"
                    await call("retry_workflow", {"workflow_id": job["id"]})
                    done = await call("run_workflow", {"workflow_id": job["id"]})
                    assert done["state"] == "completed" and done["steps"][-1]["output"] == [3]
                elif number == 9:
                    await call("receive_stock", {"request_key": "receive", "sku": "BOOK", "quantity": 5})
                    reservation = await call("reserve_stock", {"request_key": "reserve", "items": [{"sku": "BOOK", "quantity": 2}]})
                    await call("settle_reservation", {"request_key": "release", "reservation_id": reservation["id"], "action": "release"})
                    assert (await call("list_inventory"))[0]["available"] == 5


async def main():
    for path in sorted(ROOT.glob("[0-9][0-9]-*/server.py")):
        with tempfile.TemporaryDirectory() as temp:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(port), "MCP_AUTH_TOKEN": TOKEN,
                   "DATA_DIR": temp, "TASKS_DB": str(Path(temp) / "tasks.db"), "RATE_LIMIT_PER_MINUTE": "1000",
                   "MCP_ALLOWED_HOSTS": "", "ENVIRONMENT": "production", "PYTHONIOENCODING": "utf-8"}
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
                process = subprocess.Popen([sys.executable, str(path)], cwd=ROOT, env=env, stdout=log, stderr=log,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                try:
                    url = f"http://127.0.0.1:{port}"
                    async with httpx.AsyncClient(timeout=1) as client:
                        deadline = time.monotonic() + 30
                        while True:
                            try:
                                if (await client.get(url + "/health")).status_code == 200:
                                    break
                            except httpx.RequestError:
                                pass
                            if process.poll() is not None or time.monotonic() > deadline:
                                log.seek(0)
                                raise RuntimeError(log.read())
                            await asyncio.sleep(.15)
                        assert (await client.post(url + "/mcp", json={})).status_code == 401
                        invalid_host = await client.post(url + "/mcp", json={}, headers={"Authorization": f"Bearer {TOKEN}", "Host": "evil.example"})
                        assert invalid_host.status_code == 421, invalid_host.status_code
                    await exercise(url + "/mcp", int(path.parent.name[:2]))
                    clients = {1: "01-hello-client.py", 2: "02-http-client.py", 3: "03-auth-client.py",
                               4: "04-advanced-client.py", 8: "07-workflow-client.py", 9: "08-inventory-client.py"}
                    number = int(path.parent.name[:2])
                    if number in clients:
                        result = await asyncio.to_thread(subprocess.run,
                            [sys.executable, str(ROOT / "clients" / clients[number])],
                            env={**env, "MCP_URL": url + "/mcp"}, capture_output=True, text=True,
                            encoding="utf-8", timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                        assert result.returncode == 0, (clients[number], result.stdout, result.stderr)
                    if number == 5:
                        cli = [sys.executable, str(ROOT / "clients/05-interactive-cli.py"), url + "/mcp"]
                        for args, expected in [(["--list"], 0), (["--call", "missing_tool"], 1)]:
                            result = await asyncio.to_thread(subprocess.run, cli + args, env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                            assert result.returncode == expected, (result.returncode, result.stderr)
                    print(f"PASS {path.parent.name}", flush=True)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
