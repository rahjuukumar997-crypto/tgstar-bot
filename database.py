"""
SQLite storage layer for the wallet bot.
Swap to Postgres/MySQL later by replacing the connection logic if you scale up —
the query shapes below stay the same.
"""
import sqlite3
import time
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username    TEXT,
    balance_mmk INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS topups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    amount_mmk  INTEGER NOT NULL,
    method      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
    proof_file_id TEXT,
    created_at  INTEGER NOT NULL,
    reviewed_by INTEGER,
    reviewed_at INTEGER
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    order_type  TEXT NOT NULL,   -- 'stars' or 'premium'
    detail      TEXT NOT NULL,   -- e.g. "250 Stars" or "Premium 6m"
    price_mmk   INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending / fulfilled / failed / refunded
    target_username TEXT,        -- telegram @username stars/premium is delivered to
    created_at  INTEGER NOT NULL,
    fulfilled_by INTEGER,
    fulfilled_at INTEGER,
    note        TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def get_or_create_user(telegram_id: int, username: str | None):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        if row:
            if username and row["username"] != username:
                conn.execute("UPDATE users SET username=? WHERE telegram_id=?", (username, telegram_id))
            return dict(row)
        conn.execute(
            "INSERT INTO users (telegram_id, username, balance_mmk, created_at) VALUES (?,?,0,?)",
            (telegram_id, username, int(time.time())),
        )
        row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        return dict(row)


def get_balance(telegram_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT balance_mmk FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        return row["balance_mmk"] if row else 0


def adjust_balance(telegram_id: int, delta_mmk: int):
    """Positive delta credits, negative delta debits. Caller must ensure sufficient balance for debits."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET balance_mmk = balance_mmk + ? WHERE telegram_id=?",
            (delta_mmk, telegram_id),
        )


def create_topup(telegram_id: int, amount_mmk: int, method: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO topups (telegram_id, amount_mmk, method, status, created_at) VALUES (?,?,?,'pending',?)",
            (telegram_id, amount_mmk, method, int(time.time())),
        )
        return cur.lastrowid


def attach_topup_proof(topup_id: int, file_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE topups SET proof_file_id=? WHERE id=?", (file_id, topup_id))


def get_topup(topup_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM topups WHERE id=?", (topup_id,)).fetchone()
        return dict(row) if row else None


def set_topup_status(topup_id: int, status: str, reviewer_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE topups SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
            (status, reviewer_id, int(time.time()), topup_id),
        )


def create_order(telegram_id: int, order_type: str, detail: str, price_mmk: int, target_username: str | None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders (telegram_id, order_type, detail, price_mmk, status, target_username, created_at)
               VALUES (?,?,?,?,'pending',?,?)""",
            (telegram_id, order_type, detail, price_mmk, target_username, int(time.time())),
        )
        return cur.lastrowid


def get_order(order_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def set_order_status(order_id: int, status: str, admin_id: int | None = None, note: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status=?, fulfilled_by=?, fulfilled_at=?, note=? WHERE id=?",
            (status, admin_id, int(time.time()), note, order_id),
        )


def list_pending_topups():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM topups WHERE status='pending' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def list_pending_orders():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def list_user_history(telegram_id: int, limit: int = 20):
    with get_conn() as conn:
        topups = conn.execute(
            "SELECT * FROM topups WHERE telegram_id=? ORDER BY id DESC LIMIT ?", (telegram_id, limit)
        ).fetchall()
        orders = conn.execute(
            "SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT ?", (telegram_id, limit)
        ).fetchall()
        return {"topups": [dict(r) for r in topups], "orders": [dict(r) for r in orders]}
