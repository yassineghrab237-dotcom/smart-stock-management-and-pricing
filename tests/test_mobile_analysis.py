import sqlite3
from datetime import date, timedelta
from fastapi.testclient import TestClient
from libs.common.security import COOKIE
from test_imports import client, source, commit  # fixtures partagées isolées


def native(client, email="import@example.test", password="ImportTest123!"):
    response = client.post(
        "/api/mobile/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_native_token_hash_expiry_and_web_independence(client):
    cookie = client.cookies.get(COOKIE)
    headers = native(client)
    assert client.cookies.get(COOKIE) == cookie
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    with sqlite3.connect(client.app.state.db_path) as db:
        saved = db.execute("SELECT token_hash FROM mobile_sessions").fetchone()[0]
        assert saved != headers["Authorization"].split()[1] and len(saved) == 64
    assert client.post("/api/mobile/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/auth/me").status_code == 200
    headers = native(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    with sqlite3.connect(client.app.state.db_path) as db:
        db.execute("UPDATE mobile_sessions SET expires_at=0")
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_native_no_cookie_fallback_and_roles(client):
    assert (
        client.get(
            "/api/products", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/products", headers={"Authorization": "Basic invalid"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/products",
            headers={"Authorization": "Bearer " + client.cookies.get(COOKIE)},
        ).status_code
        == 401
    )
    client.post(
        "/api/auth/users",
        json={
            "name": "QA Lecteur",
            "email": "view@example.test",
            "password": "ImportTest123!",
            "role": "VIEWER",
        },
    )
    headers = native(client, "view@example.test")
    assert client.get("/api/dashboard", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/products", json={"sku": "NO", "name": "NO"}, headers=headers
        ).status_code
        == 403
    )
    assert client.post("/api/analysis/jobs", headers=headers).status_code == 403


def test_account_access_revokes_native_web_and_can_reactivate(client):
    created = client.post(
        "/api/auth/users",
        json={
            "name": "QA Accès",
            "email": "access@example.test",
            "password": "ImportTest123!",
            "role": "MANAGER",
        },
    ).json()
    headers = native(client, "access@example.test")
    with TestClient(client.app) as manager:
        assert (
            manager.post(
                "/api/auth/login",
                json={"email": "access@example.test", "password": "ImportTest123!"},
            ).status_code
            == 200
        )
        assert manager.get("/api/products").status_code == 200
        assert (
            manager.post(
                f'/api/auth/users/{created["id"]}/access',
                json={"active": False, "reason": "QA"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f'/api/auth/users/{created["id"]}/access',
                json={"active": False, "reason": "Fin de mission QA"},
            ).status_code
            == 200
        )
        assert manager.get("/api/products").status_code == 401
    assert client.get("/api/products", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/mobile/auth/login",
            json={"email": "access@example.test", "password": "ImportTest123!"},
        ).status_code
        == 401
    )
    assert (
        next(
            u
            for u in client.get("/api/auth/users").json()["items"]
            if u["id"] == created["id"]
        )["active"]
        is False
    )
    assert (
        client.post(
            f'/api/auth/users/{created["id"]}/access',
            json={"active": True, "reason": "Retour QA"},
        ).status_code
        == 200
    )
    assert client.get("/api/products", headers=headers).status_code == 401
    assert (
        client.get(
            "/api/products", headers=native(client, "access@example.test")
        ).status_code
        == 200
    )


def test_account_revoke_sessions_preserves_access_and_self_disable_refused(client):
    current = client.get("/api/auth/me").json()
    assert (
        client.post(
            f'/api/auth/users/{current["id"]}/access',
            json={"active": False, "reason": "QA"},
        ).status_code
        == 409
    )
    created = client.post(
        "/api/auth/users",
        json={
            "name": "QA Révocation",
            "email": "revoke@example.test",
            "password": "ImportTest123!",
            "role": "VIEWER",
        },
    ).json()
    headers = native(client, "revoke@example.test")
    with TestClient(client.app) as viewer:
        assert (
            viewer.post(
                "/api/auth/login",
                json={"email": "revoke@example.test", "password": "ImportTest123!"},
            ).status_code
            == 200
        )
        assert (
            client.post(f'/api/auth/users/{created["id"]}/revoke-sessions').status_code
            == 200
        )
        assert viewer.get("/api/products").status_code == 401
    assert client.get("/api/products", headers=headers).status_code == 401
    assert (
        client.get(
            "/api/products", headers=native(client, "revoke@example.test")
        ).status_code
        == 200
    )


def test_native_and_web_share_rate_limit(client):
    for _ in range(5):
        assert (
            client.post(
                "/api/mobile/auth/login",
                json={"email": "import@example.test", "password": "wrong"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "import@example.test", "password": "ImportTest123!"},
        ).status_code
        == 429
    )


def test_native_http_remote_and_external_origin_refused(client):
    body = {"email": "import@example.test", "password": "ImportTest123!"}
    assert (
        client.post(
            "/api/mobile/auth/login",
            json=body,
            headers={"Origin": "https://other.test"},
        ).status_code
        == 403
    )
    with TestClient(client.app, client=("203.0.113.10", 5000)) as remote:
        assert remote.post("/api/mobile/auth/login", json=body).status_code == 403


def test_native_stock_idempotency_visible_to_web(client):
    item = client.post(
        "/api/products", json={"sku": "MOBILE", "name": "QA Mobile"}
    ).json()
    headers = native(client)
    body = {
        "product_id": item["id"],
        "type": "IN",
        "quantity": 20,
        "reason": "Recette native",
        "expected_version": 1,
        "idempotency_key": "qa-native-idempotent",
    }
    first = client.post("/api/movements", json=body, headers=headers)
    second = client.post("/api/movements", json=body, headers=headers)
    assert (
        first.status_code == second.status_code == 201 and first.json() == second.json()
    )
    assert client.get(f'/api/products/{item["id"]}').json()["current_stock"] == 20
    assert len(client.get("/api/movements").json()["items"]) == 1


def test_analysis_empty_finishes_and_same_snapshot_reuses_job(client):
    first = client.post("/api/analysis/jobs")
    assert first.status_code == 200
    jobs = client.get("/api/analysis/jobs").json()["items"]
    assert jobs[0]["status"] == "SUCCEEDED" and jobs[0]["progress"] == 100
    assert jobs[0]["result"]["products"] == []
    assert client.post("/api/analysis/jobs").json()["id"] == first.json()["id"]


def import_weeks(client, quantities, missing=None):
    item = client.post(
        "/api/products", json={"sku": "FORECAST", "name": "QA Prévision"}
    ).json()
    monday = date.today() - timedelta(days=date.today().weekday())
    rows = [
        f"QA-W-{i},FORECAST,{(monday-timedelta(weeks=len(quantities)-i)).isoformat()},{q},10"
        for i, q in enumerate(quantities)
        if i != missing
    ]
    body = source(
        "reference,sku,sold_on,quantity,unit_price\n" + "\n".join(rows), "sales"
    )
    assert commit(client, body).status_code == 200
    client.post("/api/analysis/jobs")
    return item, client.get("/api/analysis/jobs").json()["items"][0]


def test_analysis_temporal_evaluation_not_writes_stock_prices(client):
    item, job = import_weeks(client, [20, 80] * 12)
    forecast = job["result"]["products"][0]
    assert job["status"] == "SUCCEEDED" and forecast["status"] == "available"
    assert (
        forecast["evaluation_weeks"] == 4
        and forecast["model_mae"] < forecast["baseline_mae"]
    )
    assert (
        forecast["target_week"]
        == (date.today() - timedelta(days=date.today().weekday())).isoformat()
    )
    assert client.get(f'/api/products/{item["id"]}').json() == item
    assert client.get("/api/movements").json()["items"] == []
    assert client.get("/api/analysis/jobs").json()["items"][0]["stale"] is False
    client.post("/api/products", json={"sku": "NEW", "name": "QA nouveau"})
    assert client.get("/api/analysis/jobs").json()["items"][0]["stale"] is True


def test_analysis_no_fabricated_zero_for_missing_weeks(client):
    _, job = import_weeks(client, [20, 80] * 12, missing=8)
    result = job["result"]["products"][0]
    assert result["prediction"] is None and "manquent" in result["detail"]


def test_analysis_baseline_not_beaten_hides_prediction(client):
    _, job = import_weeks(client, [20] * 20)
    result = job["result"]["products"][0]
    assert result["prediction"] is None and "ne fait pas mieux" in result["detail"]


def test_analysis_short_history_and_recover_interrupted(client):
    _, job = import_weeks(client, [20] * 3)
    assert "16 semaines" in job["result"]["products"][0]["detail"]
    with sqlite3.connect(client.app.state.db_path) as db:
        db.execute(
            "UPDATE analysis_jobs SET status='RUNNING',updated_at='2020-01-01T00:00:00+00:00'"
        )
    assert (
        client.get("/api/analysis/jobs").json()["items"][0]["status"] == "INTERRUPTED"
    )
    assert client.post("/api/analysis/jobs").json()["id"] != job["id"]
