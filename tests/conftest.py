"""Isoler aussi l'application globale construite à l'import du gateway."""

import os
import tempfile
from pathlib import Path


def pytest_configure(config):
    config.stock_original_db = os.environ.get("SMART_STOCK_DB")
    bootstrap = Path(tempfile.mkdtemp(prefix="smart-stock-test-bootstrap-"))
    os.environ["SMART_STOCK_DB"] = str(bootstrap / "bootstrap.sqlite3")


def pytest_unconfigure(config):
    previous = config.stock_original_db
    if previous is None:
        os.environ.pop("SMART_STOCK_DB", None)
    else:
        os.environ["SMART_STOCK_DB"] = previous
