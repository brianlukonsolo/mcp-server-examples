"""SQLite connections with explicit transaction and connection lifetimes."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def database_path(name: str) -> str:
    return str(Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))) / name)


@contextmanager
def connect(path: str, schema: str = "", write: bool = False):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        if schema:
            conn.executescript(schema)
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        with conn:
            yield conn
    finally:
        conn.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def nonempty(value: str, name: str, maximum: int = 200) -> str:
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"{name} must contain 1-{maximum} characters")
    return value
