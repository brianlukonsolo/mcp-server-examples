"""05 — Task manager (stateful server with SQLite).

A small real application: a persistent to-do list the AI can drive. State
lives in SQLite, so it survives restarts, and a resource exposes the whole
list for the model to read into context.

Run:  python server.py  ->  http://localhost:8105/mcp
"""

import os
import sqlite3
from datetime import datetime
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("TASKS_DB", os.path.join(os.path.dirname(__file__), "tasks.db"))

mcp = FastMCP(
    "task-manager",
    instructions=(
        "A persistent to-do list. Add, list, complete, and delete tasks; "
        "each task has a priority and optional due date."
    ),
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8105")),
    stateless_http=True,
)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            due_date TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["done"] = bool(d["done"])
    return d


@mcp.tool()
def add_task(
    title: str,
    priority: Literal["low", "medium", "high"] = "medium",
    due_date: Optional[str] = None,
) -> dict:
    """Add a task. due_date is optional, format YYYY-MM-DD."""
    if due_date:
        datetime.strptime(due_date, "%Y-%m-%d")  # validate; raises on junk
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, priority, due_date, created_at) VALUES (?, ?, ?, ?)",
            (title.strip(), priority, due_date, datetime.now().isoformat(timespec="seconds")),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_to_dict(row)


@mcp.tool()
def list_tasks(
    status: Literal["all", "open", "done"] = "open",
    priority: Optional[Literal["low", "medium", "high"]] = None,
) -> list[dict]:
    """List tasks, optionally filtered by status and priority.
    Sorted: open before done, then high priority first, then oldest first."""
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list = []
    if status == "open":
        query += " AND done = 0"
    elif status == "done":
        query += " AND done = 1"
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += """ ORDER BY done,
        CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
        created_at"""
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]


@mcp.tool()
def complete_task(task_id: int) -> dict:
    """Mark a task as done."""
    with db() as conn:
        cur = conn.execute(
            "UPDATE tasks SET done = 1, completed_at = ? WHERE id = ? AND done = 0",
            (datetime.now().isoformat(timespec="seconds"), task_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"No open task with id {task_id}")
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_dict(row)


@mcp.tool()
def delete_task(task_id: int) -> dict:
    """Delete a task permanently."""
    with db() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise ValueError(f"No task with id {task_id}")
    return {"deleted": task_id}


@mcp.tool()
def task_stats() -> dict:
    """Counts of open/done tasks, split by priority, plus overdue count."""
    today = datetime.now().strftime("%Y-%m-%d")
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
        by_priority = {
            r["priority"]: r["n"]
            for r in conn.execute(
                "SELECT priority, COUNT(*) AS n FROM tasks WHERE done = 0 GROUP BY priority"
            )
        }
        overdue = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE done = 0 AND due_date IS NOT NULL AND due_date < ?",
            (today,),
        ).fetchone()[0]
    return {"total": total, "open": total - done, "done": done,
            "open_by_priority": by_priority, "overdue": overdue}


@mcp.resource("tasks://all")
def all_tasks_resource() -> str:
    """The full task list as readable text (for loading into context)."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY done, created_at").fetchall()
    if not rows:
        return "No tasks yet."
    lines = []
    for r in rows:
        box = "[x]" if r["done"] else "[ ]"
        due = f" (due {r['due_date']})" if r["due_date"] else ""
        lines.append(f"{box} #{r['id']} [{r['priority']}] {r['title']}{due}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
