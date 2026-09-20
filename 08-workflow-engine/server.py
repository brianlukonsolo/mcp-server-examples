"""08 — Durable DAG workflows with atomic checkpoints, retries and cancellation.

Steps are bounded, pure numeric transforms, never arbitrary Python or shell.
Each step runs inside a SQLite write transaction; parallel callers serialize.
"""
import asyncio
import json
import math
import sys
import uuid
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.runtime import create_server, run, report_progress
from common.storage import connect, database_path, nonempty, utc_now

mcp = create_server("workflow-engine", 8108)
DB_PATH = database_path("workflows.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, definition TEXT NOT NULL,
    state TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    workflow_id TEXT NOT NULL REFERENCES workflows(id), name TEXT NOT NULL,
    position INTEGER NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    output TEXT, error TEXT, PRIMARY KEY(workflow_id,name)
);
"""


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    operation: Literal["scale", "positive", "sort", "unique", "sum", "fail_once"]
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    factor: float = Field(default=1, ge=-1e6, le=1e6)


@mcp.tool()
def create_workflow(request_key: str, values: list[float], steps: list[Step]) -> dict:
    """Create an idempotent DAG of 1-20 numeric steps over 1-1000 values.
    Roots read values; children concatenate dependency outputs in declared order.
    fail_once deliberately fails its first attempt so clients can learn retries."""
    request_key = nonempty(request_key, "request_key", 100)
    if not 1 <= len(values) <= 1000 or any(not math.isfinite(v) or abs(v) > 1e12 for v in values):
        raise ValueError("Use 1-1000 finite values in +/-1e12")
    if not 1 <= len(steps) <= 20:
        raise ValueError("Use 1-20 steps")
    names = {s.name for s in steps}
    if len(names) != len(steps):
        raise ValueError("Step names must be unique")
    for step in steps:
        if len(step.depends_on) != len(set(step.depends_on)) or not set(step.depends_on) <= names:
            raise ValueError("Dependencies must be unique existing step names")
    remaining, ordered = list(steps), []
    while remaining:
        ready = [s for s in remaining if set(s.depends_on) <= {r.name for r in ordered}]
        if not ready:
            raise ValueError("Workflow contains a dependency cycle")
        ordered.extend(ready)
        remaining = [s for s in remaining if s not in ready]
    definition = json.dumps({"values": values, "steps": [s.model_dump() for s in ordered]}, sort_keys=True, allow_nan=False)
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        prior = conn.execute("SELECT id,definition FROM workflows WHERE request_key=?", (request_key,)).fetchone()
        if prior:
            if prior["definition"] != definition:
                raise ValueError("Idempotency key was already used for a different workflow")
            workflow_id = prior["id"]
        else:
            workflow_id = uuid.uuid4().hex
            conn.execute("INSERT INTO workflows VALUES(?,?,?,?,?)", (workflow_id, request_key, definition, "pending", utc_now()))
            conn.executemany("INSERT INTO steps(workflow_id,name,position,state) VALUES(?,?,?,?)",
                             [(workflow_id, step.name, i, "pending") for i, step in enumerate(ordered)])
    return get_workflow(workflow_id)


def workflow_row(conn, workflow_id):
    row = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    if row is None:
        raise ValueError("Workflow not found")
    return row


@mcp.tool()
def get_workflow(workflow_id: str) -> dict:
    """Inspect durable status, step attempts, errors and checkpoint outputs."""
    with connect(DB_PATH, SCHEMA) as conn:
        result = dict(workflow_row(conn, workflow_id))
        result.pop("definition")
        result["steps"] = [dict(row) for row in conn.execute(
            "SELECT name,state,attempts,output,error FROM steps WHERE workflow_id=? ORDER BY position", (workflow_id,))]
        for step in result["steps"]:
            step["output"] = json.loads(step["output"]) if step["output"] is not None else None
    return result


def advance(workflow_id: str) -> dict:
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        workflow = workflow_row(conn, workflow_id)
        if workflow["state"] in ("completed", "cancelled", "failed"):
            return {"state": workflow["state"]}
        definition = json.loads(workflow["definition"])
        row = conn.execute("SELECT * FROM steps WHERE workflow_id=? AND state='pending' ORDER BY position LIMIT 1",
                           (workflow_id,)).fetchone()
        step = definition["steps"][row["position"]]
        values = list(definition["values"]) if not step["depends_on"] else []
        for parent in step["depends_on"]:
            output = conn.execute("SELECT output FROM steps WHERE workflow_id=? AND name=? AND state='completed'",
                                  (workflow_id, parent)).fetchone()
            if output is None:
                raise RuntimeError("Dependency checkpoint missing")
            values.extend(json.loads(output[0]))
        try:
            if len(values) > 10_000:
                raise ValueError("Step input exceeds 10000 values")
            op = step["operation"]
            if op == "fail_once" and row["attempts"] == 0:
                raise ValueError("Demonstration failure; call retry_workflow then run_workflow")
            if op == "scale":
                values = [v * step["factor"] for v in values]
            elif op == "positive":
                values = [v for v in values if v > 0]
            elif op == "sort":
                values = sorted(values)
            elif op == "unique":
                values = list(dict.fromkeys(values))
            elif op == "sum":
                values = [sum(values)]
            if any(not math.isfinite(v) or abs(v) > 1e100 for v in values):
                raise ValueError("Step output exceeds finite numeric limits")
        except ValueError as exc:
            conn.execute("UPDATE steps SET state='failed',attempts=attempts+1,error=? WHERE workflow_id=? AND name=?",
                         (str(exc), workflow_id, step["name"]))
            conn.execute("UPDATE workflows SET state='failed' WHERE id=?", (workflow_id,))
            return {"state": "failed", "step": step["name"]}
        conn.execute("UPDATE steps SET state='completed',attempts=attempts+1,output=?,error=NULL WHERE workflow_id=? AND name=?",
                     (json.dumps(values, allow_nan=False), workflow_id, step["name"]))
        pending = conn.execute("SELECT COUNT(*) FROM steps WHERE workflow_id=? AND state='pending'", (workflow_id,)).fetchone()[0]
        state = "running" if pending else "completed"
        conn.execute("UPDATE workflows SET state=? WHERE id=?", (state, workflow_id))
        return {"state": state, "completed": len(definition["steps"]) - pending, "total": len(definition["steps"])}


@mcp.tool()
async def run_workflow(workflow_id: str, ctx: Context, max_steps: int = 20) -> dict:
    """Execute up to max_steps with progress. Call again to resume checkpoints.
    Execution is request-driven, not a background job; disconnected calls may
    stop between steps and can be resumed without repeating committed work."""
    if not 1 <= max_steps <= 20:
        raise ValueError("max_steps must be 1-20")
    for _ in range(max_steps):
        result = await asyncio.to_thread(advance, workflow_id)
        if "completed" in result:
            await report_progress(ctx, result["completed"], result["total"])
        if result["state"] != "running":
            break
        await asyncio.sleep(0)
    return await asyncio.to_thread(get_workflow, workflow_id)


@mcp.tool()
def retry_workflow(workflow_id: str) -> dict:
    """Retry a failed workflow, preserving completed steps. Maximum 3 attempts per step."""
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        row = workflow_row(conn, workflow_id)
        if row["state"] != "failed":
            raise ValueError("Only failed workflows can be retried")
        failed = conn.execute("SELECT attempts FROM steps WHERE workflow_id=? AND state='failed'", (workflow_id,)).fetchone()
        if failed[0] >= 3:
            raise ValueError("Step exhausted its 3 attempts")
        conn.execute("UPDATE steps SET state='pending',error=NULL WHERE workflow_id=? AND state='failed'", (workflow_id,))
        conn.execute("UPDATE workflows SET state='pending' WHERE id=?", (workflow_id,))
    return get_workflow(workflow_id)


@mcp.tool()
def cancel_workflow(workflow_id: str) -> dict:
    """Cancel between atomic steps; completed/cancelled workflows are unchanged."""
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        workflow_row(conn, workflow_id)
        conn.execute("UPDATE workflows SET state='cancelled' WHERE id=? AND state NOT IN ('completed','cancelled')", (workflow_id,))
    return get_workflow(workflow_id)


if __name__ == "__main__":
    run(mcp, require_auth=True)
