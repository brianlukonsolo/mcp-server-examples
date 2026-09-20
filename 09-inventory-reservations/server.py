"""09 — Transactional stock reservations, idempotency and an append-only audit log."""
import json
import sys
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.runtime import create_server, run
from common.storage import connect, database_path, nonempty, utc_now

mcp = create_server("inventory-reservations", 8109)
DB_PATH = database_path("inventory.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory (
    sku TEXT PRIMARY KEY, available INTEGER NOT NULL CHECK(available >= 0)
);
CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY, state TEXT NOT NULL, items TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    request_key TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
    subject TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,39}$")
    quantity: int = Field(strict=True, ge=1, le=1_000_000)


def replay(conn, request_key: str, payload: dict):
    nonempty(request_key, "request_key", 100)
    row = conn.execute("SELECT payload,result FROM requests WHERE request_key=?", (request_key,)).fetchone()
    if row:
        if row["payload"] != json.dumps(payload, sort_keys=True):
            raise ValueError("Idempotency key already used with different arguments")
        return json.loads(row["result"])
    return None


def record(conn, request_key, payload, result, action, subject):
    conn.execute("INSERT INTO requests VALUES(?,?,?)", (request_key, json.dumps(payload, sort_keys=True), json.dumps(result)))
    conn.execute("INSERT INTO audit(action,subject,detail,created_at) VALUES(?,?,?,?)",
                 (action, subject, json.dumps(result), utc_now()))
    return result


@mcp.tool()
def receive_stock(request_key: str, sku: str, quantity: int) -> dict:
    """Receive stock once per request_key; a retry returns the original response."""
    item = Item(sku=sku, quantity=quantity)
    payload = {"action": "receive", **item.model_dump()}
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        previous = replay(conn, request_key, payload)
        if previous is not None:
            return previous
        conn.execute("INSERT INTO inventory VALUES(?,?) ON CONFLICT(sku) DO UPDATE SET available=available+excluded.available",
                     (sku, quantity))
        available = conn.execute("SELECT available FROM inventory WHERE sku=?", (sku,)).fetchone()[0]
        if available > 1_000_000_000:
            raise ValueError("Stock exceeds the example's billion-unit limit")
        return record(conn, request_key, payload, {"sku": sku, "available": available}, "receive", sku)


@mcp.tool()
def reserve_stock(request_key: str, items: list[Item]) -> dict:
    """Reserve every item atomically, or reserve none if any SKU lacks stock.
    Duplicate SKUs are rejected. Retrying a request cannot reserve twice."""
    if not 1 <= len(items) <= 50 or len({i.sku for i in items}) != len(items):
        raise ValueError("Use 1-50 items with unique SKUs")
    normalized = [i.model_dump() for i in sorted(items, key=lambda i: i.sku)]
    payload = {"action": "reserve", "items": normalized}
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        previous = replay(conn, request_key, payload)
        if previous is not None:
            return previous
        for item in normalized:
            cur = conn.execute("UPDATE inventory SET available=available-? WHERE sku=? AND available>=?",
                               (item["quantity"], item["sku"], item["quantity"]))
            if cur.rowcount != 1:
                raise ValueError(f"Insufficient stock for {item['sku']}; no items reserved")
        reservation_id = uuid.uuid4().hex
        result = {"id": reservation_id, "state": "reserved", "items": normalized, "created_at": utc_now()}
        conn.execute("INSERT INTO reservations VALUES(?,?,?,?)",
                     (reservation_id, "reserved", json.dumps(normalized), result["created_at"]))
        return record(conn, request_key, payload, result, "reserve", reservation_id)


@mcp.tool()
def settle_reservation(request_key: str, reservation_id: str, action: Literal["confirm", "release"]) -> dict:
    """Confirm a sale or release its stock. Final states cannot be changed.
    Same-action retries with new keys are harmless; conflicting actions fail."""
    if action not in ("confirm", "release"):
        raise ValueError("action must be confirm or release")
    payload = {"action": action, "reservation_id": reservation_id}
    target = "confirmed" if action == "confirm" else "released"
    with connect(DB_PATH, SCHEMA, write=True) as conn:
        previous = replay(conn, request_key, payload)
        if previous is not None:
            return previous
        row = conn.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
        if row is None:
            raise ValueError("Reservation not found")
        if row["state"] not in ("reserved", target):
            raise ValueError(f"Cannot {action} a {row['state']} reservation")
        if row["state"] == "reserved":
            if action == "release":
                for item in json.loads(row["items"]):
                    conn.execute("UPDATE inventory SET available=available+? WHERE sku=?", (item["quantity"], item["sku"]))
            conn.execute("UPDATE reservations SET state=? WHERE id=?", (target, reservation_id))
        return record(conn, request_key, payload, {"id": reservation_id, "state": target}, action, reservation_id)


@mcp.tool()
def get_reservation(reservation_id: str) -> dict:
    """Read a reservation and its current state."""
    with connect(DB_PATH, SCHEMA) as conn:
        row = conn.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
    if row is None:
        raise ValueError("Reservation not found")
    return {**dict(row), "items": json.loads(row["items"])}


@mcp.tool()
def list_inventory(limit: int = 100, after_sku: str = "") -> list[dict]:
    """Keyset-paginated available stock; pass the last SKU to get the next page."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be 1-500")
    with connect(DB_PATH, SCHEMA) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM inventory WHERE sku>? ORDER BY sku LIMIT ?", (after_sku, limit))]


@mcp.tool()
def audit_log(after_id: int = 0, limit: int = 100) -> list[dict]:
    """Read the durable audit trail in ascending ID order."""
    if after_id < 0 or not 1 <= limit <= 500:
        raise ValueError("after_id must be nonnegative and limit 1-500")
    with connect(DB_PATH, SCHEMA) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM audit WHERE id>? ORDER BY id LIMIT ?", (after_id, limit))]


if __name__ == "__main__":
    run(mcp, require_auth=True)
