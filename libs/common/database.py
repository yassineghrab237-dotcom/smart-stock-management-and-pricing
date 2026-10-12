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
        CREATE TABLE IF NOT EXISTS local_recovery_events(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),reason TEXT NOT NULL,created_at TEXT NOT NULL);
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
        CREATE TABLE IF NOT EXISTS inventory_sessions(id INTEGER PRIMARY KEY,title TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,closed_at TEXT,actor_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS inventory_lines(id INTEGER PRIMARY KEY,session_id INTEGER NOT NULL REFERENCES inventory_sessions(id),product_id INTEGER NOT NULL REFERENCES products(id),expected_stock INTEGER NOT NULL,product_version INTEGER NOT NULL,counted INTEGER,version INTEGER NOT NULL DEFAULT 1,UNIQUE(session_id,product_id));
        CREATE TABLE IF NOT EXISTS inventory_events(id INTEGER PRIMARY KEY,session_id INTEGER NOT NULL REFERENCES inventory_sessions(id),detail TEXT NOT NULL,actor_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS replenishment_policies(product_id INTEGER PRIMARY KEY REFERENCES products(id),supplier_id INTEGER NOT NULL REFERENCES crm_contacts(id),unit_cost_ht TEXT NOT NULL,lead_days INTEGER NOT NULL,min_quantity INTEGER NOT NULL,pack_size INTEGER NOT NULL,enabled INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS replenishment_events(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),detail TEXT NOT NULL,actor_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS purchase_orders_local(id INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE, supplier_id INTEGER NOT NULL REFERENCES crm_contacts(id), status TEXT NOT NULL, expected_on TEXT NOT NULL, note TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, ordered_at TEXT, actor_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS purchase_lines_local(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES purchase_orders_local(id), product_id INTEGER NOT NULL REFERENCES products(id), sku TEXT NOT NULL, name TEXT NOT NULL, quantity INTEGER NOT NULL, unit_cost_ht TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS purchase_receipts_local(id INTEGER PRIMARY KEY, line_id INTEGER NOT NULL REFERENCES purchase_lines_local(id), quantity INTEGER NOT NULL, reason TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS purchase_line_order ON purchase_lines_local(order_id,id);
        CREATE TABLE IF NOT EXISTS commercial_documents(id INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, status TEXT NOT NULL, customer_id INTEGER REFERENCES crm_contacts(id), currency TEXT NOT NULL DEFAULT 'TND', note TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, source_quote_id INTEGER UNIQUE REFERENCES commercial_documents(id), created_at TEXT NOT NULL, confirmed_at TEXT, actor_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS commercial_sale_dates(document_id INTEGER PRIMARY KEY REFERENCES commercial_documents(id),sold_on TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commercial_lines(id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES commercial_documents(id), product_id INTEGER NOT NULL REFERENCES products(id), sku TEXT NOT NULL, name TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_ttc TEXT NOT NULL, discount_ttc TEXT NOT NULL, tax_rate TEXT NOT NULL, unit_cost_ht TEXT);
        CREATE INDEX IF NOT EXISTS commercial_line_document ON commercial_lines(document_id,id);
        CREATE TABLE IF NOT EXISTS commercial_returns(id INTEGER PRIMARY KEY, line_id INTEGER NOT NULL REFERENCES commercial_lines(id), quantity INTEGER NOT NULL, restock INTEGER NOT NULL, reason TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_contacts(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, company TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL, stage TEXT NOT NULL, contact_permission TEXT NOT NULL, lead_days INTEGER NOT NULL, min_order INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_opportunities(id INTEGER PRIMARY KEY,contact_id INTEGER NOT NULL REFERENCES crm_contacts(id),title TEXT NOT NULL,stage TEXT NOT NULL,expected_ttc TEXT,close_on TEXT NOT NULL,quote_id INTEGER REFERENCES commercial_documents(id),version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_events(id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES crm_contacts(id), kind TEXT NOT NULL, detail TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_tasks(id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES crm_contacts(id), title TEXT NOT NULL, due_on TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, actor_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS crm_event_contact ON crm_events(contact_id,id DESC);
        CREATE INDEX IF NOT EXISTS crm_task_contact ON crm_tasks(contact_id,status,due_on);
        CREATE TABLE IF NOT EXISTS market_observations(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), retailer TEXT NOT NULL, source_url TEXT NOT NULL, manufacturer_ref TEXT NOT NULL, variant TEXT NOT NULL, price TEXT NOT NULL, currency TEXT NOT NULL, tax_basis TEXT NOT NULL, delivery TEXT, availability TEXT NOT NULL, confirmed INTEGER NOT NULL, note TEXT NOT NULL, observed_at TEXT NOT NULL, created_at TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id));
        CREATE INDEX IF NOT EXISTS market_product_date ON market_observations(product_id, observed_at DESC, id DESC);
        CREATE TABLE IF NOT EXISTS decision_events(id INTEGER PRIMARY KEY,action_key TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,actor_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS decision_key ON decision_events(action_key,id DESC);
        CREATE TABLE IF NOT EXISTS product_identities(product_id INTEGER PRIMARY KEY REFERENCES products(id),brand TEXT NOT NULL,manufacturer_ref TEXT NOT NULL,gtin TEXT NOT NULL,variant TEXT NOT NULL,version INTEGER NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS collection_watches(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),retailer TEXT NOT NULL,source_url TEXT NOT NULL,interval_hours INTEGER NOT NULL,enabled INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,next_due TEXT NOT NULL,actor_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,UNIQUE(product_id,source_url));
        CREATE TABLE IF NOT EXISTS collection_jobs(id INTEGER PRIMARY KEY,watch_id INTEGER NOT NULL REFERENCES collection_watches(id),watch_version INTEGER NOT NULL,identity_version INTEGER NOT NULL,status TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,result TEXT,observation_id INTEGER REFERENCES market_observations(id),review_state TEXT NOT NULL DEFAULT 'PENDING',actor_id INTEGER NOT NULL REFERENCES users(id));
        CREATE UNIQUE INDEX IF NOT EXISTS collection_active ON collection_jobs(watch_id) WHERE status IN ('QUEUED','RUNNING');
        CREATE TABLE IF NOT EXISTS collection_hosts(retailer TEXT PRIMARY KEY,next_request REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS collection_events(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),detail TEXT NOT NULL,actor_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
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
