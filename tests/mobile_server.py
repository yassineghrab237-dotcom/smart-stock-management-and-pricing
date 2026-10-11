"""Serveur de recette natif, toujours une base neuve et des identités QA."""

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
qa = ROOT / "runtime" / ("native-qa-" + uuid.uuid4().hex)
qa.mkdir(parents=True)
os.environ["SMART_STOCK_DB"] = str(qa / "isolated.sqlite3")
os.environ["SMART_STOCK_DEV"] = "0"

from fastapi.testclient import TestClient
from services.api_gateway.app.main import create_app
import uvicorn

app = create_app(os.environ["SMART_STOCK_DB"])
with TestClient(app) as client:
    response = client.post(
        "/api/auth/setup",
        json={
            "name": "QA Native",
            "email": "native@example.test",
            "password": "StockQaTest123!",
        },
    )
    assert response.status_code == 201
print("Recette native : http://127.0.0.1:8012 ; base neuve " + qa.name, flush=True)
uvicorn.run(app, host="127.0.0.1", port=8012)
