import asyncio
import importlib.util
import math
import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from starlette.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.runtime import Ingress, application, create_server
from common.storage import connect
from common.upstream import get_json


def load(number):
    path = next(ROOT.glob(f"{number:02}-*/server.py"))
    spec = importlib.util.spec_from_file_location(f"example_{number}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Databases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tasks, self.kb, self.flow, self.stock = [load(n) for n in (5, 7, 8, 9)]
        for mod in (self.tasks, self.kb, self.flow, self.stock):
            mod.DB_PATH = str(Path(self.temp.name) / (mod.__name__ + ".db"))

    def test_task_validation_and_pagination(self):
        for value in ("", " " * 3, "x" * 501):
            with self.assertRaises(ValueError):
                self.tasks.add_task(value)
        for value in ("2026-2-3", "20260203", "2026-02-30", ""):
            with self.assertRaises(ValueError):
                self.tasks.add_task("task", due_date=value)
        first = self.tasks.add_task("First", due_date="2026-02-03")
        second = self.tasks.add_task("Second")
        self.assertEqual(self.tasks.list_tasks(limit=1, offset=1)[0]["id"], second["id"])
        self.tasks.complete_task(first["id"])
        self.assertEqual(self.tasks.task_stats()["done"], 1)
        self.assertIn("+00:00", self.tasks.list_tasks(status="done")[0]["completed_at"])
        self.tasks.delete_task(second["id"])
        self.assertEqual(self.tasks.task_stats()["total"], 1)

    def test_connections_close(self):
        with connect(self.tasks.DB_PATH) as conn:
            conn.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_document_revision_and_index_replace(self):
        self.kb.put_document("guide", "Guide", "oldtoken safety")
        self.kb.put_document("guide", "New guide", "newtoken safety", 1)
        self.assertEqual(self.kb.get_document("guide", 1)["body"], "oldtoken safety")
        self.assertEqual(self.kb.search_documents("oldtoken"), [])
        self.assertEqual(self.kb.search_documents('"newtoken"')[0]["version"], 2)
        self.assertEqual(self.kb.search_documents("newtoken OR absent"), [])
        with self.assertRaises(ValueError):
            self.kb.put_document("guide", "Stale", "data", 1)
        self.assertEqual(self.kb.get_document("guide")["version"], 2)

    def test_concurrent_document_updates(self):
        self.kb.put_document("guide", "Guide", "body")
        def edit(i):
            try:
                self.kb.put_document("guide", "Guide", str(i), 1)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(4) as pool:
            self.assertEqual(sum(pool.map(edit, range(4))), 1)
        self.assertEqual(self.kb.get_document("guide")["version"], 2)

    def test_document_bounds(self):
        with self.assertRaises(ValueError):
            self.kb.put_document("../escape", "x", "x")
        with self.assertRaises(ValueError):
            self.kb.search_documents("***")
        with self.assertRaises(ValueError):
            self.kb.list_documents(limit=1000)

    def test_workflow_graph_validation(self):
        Step = self.flow.Step
        for steps in ([Step(name="a", operation="sort", depends_on=["b"])],
                      [Step(name="a", operation="sort", depends_on=["a"])],
                      [Step(name="a", operation="sort"), Step(name="a", operation="sum")]):
            with self.assertRaises(ValueError):
                self.flow.create_workflow("bad", [1], steps)
        with self.assertRaises(ValueError):
            self.flow.create_workflow("bad", [math.inf], [Step(name="a", operation="sum")])

    def test_workflow_retry_and_checkpoints(self):
        Step = self.flow.Step
        steps = [Step(name="total", operation="sum", depends_on=["retry"]),
                 Step(name="double", operation="scale", factor=2),
                 Step(name="retry", operation="fail_once", depends_on=["double"])]
        job = self.flow.create_workflow("request", [1, 2, 3], steps)
        self.assertEqual(job["id"], self.flow.create_workflow("request", [1, 2, 3], steps)["id"])
        with self.assertRaises(ValueError):
            self.flow.create_workflow("request", [4], steps)
        self.flow.advance(job["id"])
        self.flow.advance(job["id"])
        failed = self.flow.get_workflow(job["id"])
        self.assertEqual(failed["state"], "failed")
        self.flow.retry_workflow(job["id"])
        self.flow.advance(job["id"])
        self.flow.advance(job["id"])
        done = self.flow.get_workflow(job["id"])
        self.assertEqual(done["state"], "completed")
        self.assertEqual([s["attempts"] for s in done["steps"]], [1, 2, 1])
        self.assertEqual(done["steps"][-1]["output"], [12])
        self.assertEqual(self.flow.advance(job["id"])["state"], "completed")

    def test_workflow_concurrent_runners(self):
        job = self.flow.create_workflow("parallel", [2], [self.flow.Step(name=f"s{i}", operation="sum") for i in range(10)])
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: self.flow.advance(job["id"]), range(20)))
        state = self.flow.get_workflow(job["id"])
        self.assertEqual(state["state"], "completed")
        self.assertTrue(all(s["attempts"] == 1 for s in state["steps"]))

    def test_workflow_cancel(self):
        job = self.flow.create_workflow("cancel", [2], [self.flow.Step(name="sum", operation="sum")])
        self.flow.cancel_workflow(job["id"])
        self.assertEqual(self.flow.advance(job["id"])["state"], "cancelled")
        self.assertEqual(self.flow.get_workflow(job["id"])["steps"][0]["attempts"], 0)

    def test_stock_idempotency_and_atomic_rollback(self):
        first = self.stock.receive_stock("in", "A", 10)
        self.assertEqual(self.stock.receive_stock("in", "A", 10), first)
        with self.assertRaises(ValueError):
            self.stock.receive_stock("in", "A", 9)
        with self.assertRaises(ValueError):
            self.stock.reserve_stock("bad", [self.stock.Item(sku="A", quantity=3), self.stock.Item(sku="B", quantity=1)])
        self.assertEqual(self.stock.list_inventory()[0]["available"], 10)
        self.assertEqual(len(self.stock.audit_log()), 1)
        result = self.stock.reserve_stock("buy", [self.stock.Item(sku="A", quantity=3)])
        self.assertEqual(self.stock.reserve_stock("buy", [self.stock.Item(sku="A", quantity=3)]), result)
        self.assertEqual(self.stock.list_inventory()[0]["available"], 7)
        self.stock.settle_reservation("release", result["id"], "release")
        self.stock.settle_reservation("release2", result["id"], "release")
        self.assertEqual(self.stock.list_inventory()[0]["available"], 10)
        with self.assertRaises(ValueError):
            self.stock.settle_reservation("confirm", result["id"], "confirm")

    def test_stock_concurrency_prevents_oversell(self):
        self.stock.receive_stock("in", "A", 10)
        def reserve(i):
            try:
                return self.stock.reserve_stock(str(i), [self.stock.Item(sku="A", quantity=3)])
            except ValueError:
                return None
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(reserve, range(8)))
        self.assertEqual(sum(r is not None for r in results), 3)
        self.assertEqual(self.stock.list_inventory()[0]["available"], 1)


class AsyncExamples(unittest.IsolatedAsyncioTestCase):
    async def test_tool_validation(self):
        tools, gateway = load(4), load(6)
        for module, search, forecast in [(tools, "find_city", "get_weather"), (gateway, "search_location", "get_forecast")]:
            with self.assertRaises(ValueError):
                await getattr(module, search)("city", 1000)
            with self.assertRaises(ValueError):
                await getattr(module, forecast)(math.nan, 0)
        with self.assertRaises(ValueError):
            tools.text_stats("hello", -1)
        with self.assertRaises(ValueError):
            load(1).add(math.inf, 1)
        with self.assertRaises(ValueError):
            load(2).convert_temperature(math.nan, "C")

    async def test_gateway_cache_bound_and_expiry(self):
        gateway = load(6)
        for i in range(300):
            gateway.cache_put(str(i), {"i": i})
        self.assertEqual(len(gateway._cache), 256)
        with patch.object(gateway.time, "monotonic", return_value=1e20):
            self.assertEqual(gateway.gateway_stats()["cache_entries"], 0)
        with patch.object(gateway, "get_json", AsyncMock(return_value={"ok": True})) as upstream:
            await gateway.fetch_json("https://example.test", {"q": 1})
            await gateway.fetch_json("https://example.test", {"q": 1})
            upstream.assert_awaited_once()

    async def test_upstream_failures(self):
        original = httpx.AsyncClient
        async def handler(request):
            return httpx.Response(200, text="not json")
        with patch("common.upstream.httpx.AsyncClient", side_effect=lambda **kwargs: original(transport=httpx.MockTransport(handler))):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                await get_json("https://example.test", {})

    async def test_auth_limit_and_size(self):
        async def ok(scope, receive, send):
            await JSONResponse({"ok": True})(scope, receive, send)
        app = Ingress(ok, "a" * 32, limit=2, max_body=10)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as client:
            self.assertEqual((await client.post("/mcp")).status_code, 401)
            self.assertEqual((await client.get("/health")).status_code, 200)
            headers = {"Authorization": "Bearer " + "a" * 32}
            self.assertEqual((await client.post("/mcp", headers=headers, content=b"x" * 11)).status_code, 413)
            self.assertEqual((await client.post("/mcp", headers=headers)).status_code, 200)
            response = await client.post("/mcp", headers=headers)
            self.assertEqual(response.status_code, 429)
            self.assertIn("Retry-After", response.headers)

    async def test_auth_duplicate_and_non_ascii(self):
        app = Ingress(AsyncMock(), "a" * 32)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as client:
            duplicate = [("Authorization", "Bearer " + "a" * 32)] * 2
            self.assertEqual((await client.post("/mcp", headers=duplicate)).status_code, 401)
            self.assertEqual((await client.post("/mcp", headers={b"Authorization": b"Bearer \xff"})).status_code, 401)

    async def test_chunked_size_and_malformed_length(self):
        app = Ingress(AsyncMock(), "", max_body=10)
        async def chunks():
            yield b"123456"
            yield b"123456"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as client:
            self.assertEqual((await client.post("/mcp", content=chunks())).status_code, 413)
            self.assertEqual((await client.post("/mcp", headers={"Content-Length": "-1"})).status_code, 400)

    async def test_required_auth_at_app_construction(self):
        with patch.dict(os.environ, {"MCP_AUTH_TOKEN": "", "ENVIRONMENT": "development"}):
            with self.assertRaises(ValueError):
                application(create_server("test", 8100), require_auth=True)


if __name__ == "__main__":
    unittest.main()
