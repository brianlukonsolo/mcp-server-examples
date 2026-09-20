"""Test all nine services in disposable containers, without mounting user data."""
import asyncio
import json
import subprocess
import time
import uuid

import httpx

from smoke_remote import ROOT, TOKEN, exercise


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


async def healthy(url):
    deadline = time.monotonic() + 60
    async with httpx.AsyncClient(timeout=2) as client:
        while time.monotonic() < deadline:
            try:
                if (await client.get(url + "/health")).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            await asyncio.sleep(.25)
    raise RuntimeError("Container did not become healthy within 60 seconds")


async def main():
    for folder in sorted(ROOT.glob("[0-9][0-9]-*")):
        number = int(folder.name[:2])
        volume = docker("volume", "create", "mcp-example-smoke-" + uuid.uuid4().hex) if number in (5, 7, 8, 9) else None
        mount = ["--volume", volume + ":/app/data"] if volume else ["--tmpfs", "/app/data:uid=10001,gid=10001,mode=0700"]
        cid = None
        try:
            cid = docker("run", "--detach", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                     "--tmpfs", "/tmp:size=32m,mode=1777", *mount,
                     "--publish", "127.0.0.1::8100", "--env", "PORT=8100", "--env", "ENVIRONMENT=production",
                     "--env", f"MCP_AUTH_TOKEN={TOKEN}", "--env", "TASKS_DB=/app/data/tasks.db",
                     "mcp-server-examples:local", "python", f"{folder.name}/server.py")
            info = json.loads(docker("inspect", cid))[0]
            assert info["Config"]["User"] == "10001:10001"
            port = info["NetworkSettings"]["Ports"]["8100/tcp"][0]["HostPort"]
            url = f"http://127.0.0.1:{port}"
            await healthy(url)
            await exercise(url + "/mcp", int(folder.name[:2]))
            if volume:
                database, table = {5: ("tasks", "tasks"), 7: ("knowledge", "documents"),
                                   8: ("workflows", "workflows"), 9: ("inventory", "audit")}[number]
                query = f"import sqlite3; c=sqlite3.connect('/app/data/{database}.db'); print(c.execute('SELECT COUNT(*) FROM {table}').fetchone()[0]); c.close()"
                count = docker("exec", cid, "python", "-c", query)
                assert int(count) > 0
                docker("restart", cid)
                restarted = json.loads(docker("inspect", cid))[0]
                port = restarted["NetworkSettings"]["Ports"]["8100/tcp"][0]["HostPort"]
                url = f"http://127.0.0.1:{port}"
                await healthy(url)
                assert docker("exec", cid, "python", "-c", query) == count
            print(f"PASS container {folder.name}", flush=True)
        except BaseException:
            if cid:
                print(docker("logs", cid))
            raise
        finally:
            if cid:
                docker("rm", "--force", cid)
            if volume:
                docker("volume", "rm", volume)


if __name__ == "__main__":
    asyncio.run(main())
