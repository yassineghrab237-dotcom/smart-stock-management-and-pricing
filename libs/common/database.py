"""SQLite transactionnel partagé, indépendant des CSV de démonstration."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript(
            """
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('ADMIN','MANAGER','VIEWER')), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS mobile_sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS user_access(user_id INTEGER PRIMARY KEY REFERENCES users(id), active INTEGER NOT NULL CHECK(active IN (0,1)), reason TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(id INTEGER PRIMARY KEY, identity TEXT NOT NULL, attempted_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS login_attempt_identity ON login_attempts(identity, attempted_at);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT, unit TEXT, cost_price TEXT, current_price TEXT, min_price TEXT, threshold_min INTEGER NOT NULL DEFAULT 0, threshold_max INTEGER, current_stock INTEGER NOT NULL DEFAULT 0 CHECK(current_stock >= 0), version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), type TEXT NOT NULL, quantity INTEGER NOT NULL, reason TEXT NOT NULL, stock_before INTEGER NOT NULL, stock_after INTEGER NOT NULL, created_at TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS price_history(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), old_price TEXT, new_price TEXT NOT NULL, reason TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, actor_id INTEGER NOT NULL, payload TEXT NOT NULL, response TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS csv_imports(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, digest TEXT NOT NULL, filename TEXT NOT NULL, row_count INTEGER NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(kind,digest));
        CREATE TABLE IF NOT EXISTS sales_history(id INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE, product_id INTEGER NOT NULL REFERENCES products(id), sold_on TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0), unit_price TEXT NOT NULL, import_id INTEGER NOT NULL REFERENCES csv_imports(id));
        CREATE TABLE IF NOT EXISTS analysis_jobs(id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER NOT NULL, message TEXT NOT NULL, result TEXT, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        """
        )


@contextmanager
def connect(path, write=False):
    db = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        if write:
            db.commit()
    except BaseException:
        if write:
            db.rollback()
        raise
    finally:
        db.close()


def db_path(request):
    return request.app.state.db_path


def default_path():
    return os.getenv("SMART_STOCK_DB", str(ROOT / "runtime" / "stock.sqlite3"))
