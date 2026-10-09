"""Parcours HTTP réels sur SQLite temporaire, sans mocks de persistance."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from services.api_gateway.app.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=tmp_path / "isolated.sqlite3")


@pytest.fixture
def client(app):
    with TestClient(app) as http:
        response = http.post(
            "/api/auth/setup",
            json={
                "name": "Gestionnaire test",
                "email": "admin@example.test",
                "password": "LocalTest321!",
            },
        )
        assert response.status_code in (200, 201), response.text
        yield http


def product(client, **overrides):
    payload = {
        "name": "Produit de recette",
        "sku": "QA-001",
        "threshold_min": 5,
        "threshold_max": 110,
        "current_price": "12.3400",
        "min_price": "8.00",
    }
    payload.update(overrides)
    response = client.post("/api/products", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()


def movement(client, item, kind, quantity, key=None):
    return client.post(
        "/api/movements",
        json={
            "product_id": item["id"],
            "type": kind,
            "quantity": quantity,
            "reason": "Opération de recette isolée",
            "expected_version": item["version"],
            "idempotency_key": key or str(uuid.uuid4()),
        },
    )


def current(client, item):
    response = client.get(f'/api/products/{item["id"]}')
    assert response.status_code == 200
    return response.json()


def test_product_persists_across_app_restart(client, app):
    created = product(client)
    restarted = create_app(db_path=app.state.db_path)
    with TestClient(restarted) as other:
        other.post(
            "/api/auth/login",
            json={"email": "admin@example.test", "password": "LocalTest321!"},
        )
        read = other.get(f'/api/products/{created["id"]}')
        assert read.status_code == 200
        assert read.json()["name"] == created["name"]
        assert read.json()["current_stock"] == 0


def test_stock_100_minus_15_plus_20_and_history(client):
    item = product(client)
    for kind, amount in (("IN", 100), ("OUT", 15), ("IN", 20)):
        response = movement(client, item, kind, amount)
        assert response.status_code in (200, 201), response.text
        item = current(client, item)
    assert item["current_stock"] == 105
    rows = client.get(f'/api/movements?product_id={item["id"]}').json()["items"]
    assert len(rows) == 3
    assert sorted((m["stock_before"], m["stock_after"]) for m in rows) == [
        (0, 100),
        (85, 105),
        (100, 85),
    ]
    assert all(m["actor_name"] == "Gestionnaire test" and m["reason"] for m in rows)


def test_idempotent_retry_does_not_duplicate_and_rejects_reused_key(client):
    item = product(client)
    key = str(uuid.uuid4())
    first = movement(client, item, "IN", 100, key)
    second = movement(client, item, "IN", 100, key)
    assert first.status_code in (200, 201), first.text
    assert second.status_code in (200, 201), second.text
    assert first.json() == second.json()
    assert current(client, item)["current_stock"] == 100
    assert len(client.get("/api/movements").json()["items"]) == 1
    reused = movement(client, item, "IN", 99, key)
    assert reused.status_code == 409
    assert current(client, item)["current_stock"] == 100


def test_concurrent_conflict_then_explicit_retry_no_lost_stock(client):
    item = product(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: movement(client, item, "IN", 10), range(2)))
    assert sorted(r.status_code for r in results) in ([200, 409], [201, 409])
    fresh = current(client, item)
    assert fresh["current_stock"] == 10
    assert movement(client, fresh, "IN", 10).status_code in (200, 201)
    assert current(client, item)["current_stock"] == 20
    assert len(client.get("/api/movements").json()["items"]) == 2


@pytest.mark.parametrize(
    "kind,amount",
    [
        ("OUT", 1),
        ("IN", 0),
        ("IN", -1),
        ("OUT", -1),
        ("ADJUSTMENT", -1),
        ("IN", 1.5),
        ("IN", True),
    ],
)
def test_invalid_operation_writes_nothing(client, kind, amount):
    item = product(client)
    response = movement(client, item, kind, amount)
    assert response.status_code in (400, 409, 422), response.text
    assert current(client, item)["current_stock"] == 0
    assert client.get("/api/movements").json()["items"] == []


def test_adjustment_is_traced_target_stock(client):
    item = product(client)
    assert movement(client, item, "IN", 100).status_code in (200, 201)
    item = current(client, item)
    result = movement(client, item, "ADJUSTMENT", 93)
    assert result.status_code in (200, 201), result.text
    assert result.json()["stock_before"] == 100
    assert result.json()["stock_after"] == 93
    assert current(client, item)["current_stock"] == 93


def test_threshold_alerts_trigger_and_resolve(client):
    item = product(client)
    assert any(
        a["type"] == "LOW_STOCK" for a in client.get("/api/alerts").json()["items"]
    )
    assert movement(client, item, "IN", 120).status_code in (200, 201)
    item = current(client, item)
    alerts = client.get("/api/alerts").json()["items"]
    assert len(alerts) == 1 and alerts[0]["type"] == "OVERSTOCK"
    assert movement(client, item, "OUT", 15).status_code in (200, 201)
    assert client.get("/api/alerts").json()["items"] == []


def test_unauthorized_access_and_viewer_server_permissions(client, app):
    item = product(client)
    response = client.post(
        "/api/auth/users",
        json={
            "name": "Lecture test",
            "email": "reader@example.test",
            "password": "ReadTest321!",
            "role": "VIEWER",
        },
    )
    assert response.status_code in (200, 201), response.text
    with TestClient(app) as other:
        assert other.get("/api/products").status_code == 401
        assert (
            other.post(
                "/api/auth/login",
                json={"email": "reader@example.test", "password": "ReadTest321!"},
            ).status_code
            == 200
        )
        assert other.get("/api/products").status_code == 200
        assert movement(other, item, "IN", 10).status_code == 403
        assert (
            other.post(
                "/api/products", json={"name": "Interdit", "sku": "NO"}
            ).status_code
            == 403
        )
        assert (
            other.patch(
                f'/api/products/{item["id"]}/price',
                json={
                    "price": "10",
                    "reason": "Interdit",
                    "expected_version": item["version"],
                    "idempotency_key": str(uuid.uuid4()),
                },
            ).status_code
            == 403
        )
        assert other.get("/api/auth/users").status_code == 403
        assert other.post("/api/auth/logout").status_code == 200
        assert other.get("/api/auth/me").status_code == 401


def test_csrf_and_single_admin_setup(client):
    assert (
        client.post(
            "/api/auth/setup",
            json={
                "name": "Autre",
                "email": "second@example.test",
                "password": "SecondTest321!",
            },
        ).status_code
        == 409
    )
    result = client.post(
        "/api/products",
        headers={"Origin": "https://malicious.example"},
        json={"name": "Interdit", "sku": "X"},
    )
    assert result.status_code == 403
    assert client.get("/api/products").json()["items"] == []


def test_login_rate_limit_and_password_not_stored_plain(client, app):
    with TestClient(app) as other:
        for _ in range(5):
            assert (
                other.post(
                    "/api/auth/login",
                    json={"email": "admin@example.test", "password": "WrongTest321!"},
                ).status_code
                == 401
            )
        assert (
            other.post(
                "/api/auth/login",
                json={"email": "admin@example.test", "password": "LocalTest321!"},
            ).status_code
            == 429
        )
    with sqlite3.connect(app.state.db_path) as db:
        value = db.execute("SELECT password_hash FROM users").fetchone()[0]
        assert "LocalTest321!" not in value


def test_price_precision_history_minimum_and_idempotence(client):
    item = product(client)
    key = str(uuid.uuid4())
    payload = {
        "price": "12.3456",
        "reason": "Revue tarifaire locale",
        "expected_version": item["version"],
        "idempotency_key": key,
    }
    first = client.patch(f'/api/products/{item["id"]}/price', json=payload)
    assert first.status_code == 200, first.text
    assert (
        client.patch(f'/api/products/{item["id"]}/price', json=payload).json()
        == first.json()
    )
    item = current(client, item)
    assert item["current_price"] == "12.3456"
    prices = client.get(f'/api/products/{item["id"]}/prices').json()["items"]
    assert (
        len(prices) == 1
        and prices[0]["old_price"] == "12.3400"
        and prices[0]["new_price"] == "12.3456"
    )
    payload.update(
        price="7.0000",
        expected_version=item["version"],
        idempotency_key=str(uuid.uuid4()),
    )
    assert client.patch(
        f'/api/products/{item["id"]}/price', json=payload
    ).status_code in (400, 422)
    assert current(client, item)["current_price"] == "12.3456"


def test_product_validation_duplicate_sku_and_stale_update(client):
    item = product(client)
    assert (
        client.post(
            "/api/products", json={"sku": item["sku"], "name": "Duplicata"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/products",
            json={"sku": "BAD", "name": "", "threshold_min": 10, "threshold_max": 5},
        ).status_code
        == 422
    )
    assert movement(client, item, "IN", 10).status_code in (200, 201)
    assert (
        client.patch(
            f'/api/products/{item["id"]}',
            json={"name": "Périmé", "expected_version": item["version"]},
        ).status_code
        == 409
    )


def test_dashboard_and_ml_unavailability_are_honest(client):
    item = product(client)
    dashboard = client.get("/api/dashboard").json()
    assert (
        dashboard["product_count"] == 1
        and dashboard["total_units"] == 0
        and dashboard["low_stock_count"] == 1
    )
    response = client.get(f'/api/pricing/recommendations/{item["id"]}')
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "unavailable" and result["detail"]


def test_expired_session_refused(client, app):
    with sqlite3.connect(app.state.db_path) as db:
        db.execute("UPDATE sessions SET expires_at=0")
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/products").status_code == 401


def test_dns_rebinding_host_refused(client):
    response = client.post(
        "/api/products",
        headers={"Host": "attacker.example", "Origin": "http://attacker.example"},
        json={"name": "Interdit", "sku": "REBIND"},
    )
    assert response.status_code == 400
    assert client.get("/api/products").json()["items"] == []


def test_oversized_identifiers_are_validation_errors(client):
    item = product(client)
    huge = 9223372036854775808
    for path in (
        f"/api/products/{huge}",
        f"/api/products/{huge}/prices",
        f"/api/movements?product_id={huge}",
        f"/api/pricing/recommendations/{huge}",
    ):
        assert client.get(path).status_code == 422
    item["id"] = huge
    assert movement(client, item, "IN", 1).status_code == 422
    assert client.get("/api/movements").json()["items"] == []


@pytest.mark.parametrize(
    "password", ["abcdefghijklmnop", "ABCDEFGHIJKLMN", "12345678901234", "Short1"]
)
def test_user_password_policy(client, password):
    response = client.post(
        "/api/auth/users",
        json={
            "name": "Invalide",
            "email": "invalid@example.test",
            "password": password,
            "role": "VIEWER",
        },
    )
    assert response.status_code == 422


def test_concurrent_setup_creates_one_admin(app):
    def attempt(index):
        with TestClient(app) as http:
            return http.post(
                "/api/auth/setup",
                json={
                    "name": "Recette",
                    "email": f"setup{index}@example.test",
                    "password": "SetupTest321!",
                },
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    with sqlite3.connect(app.state.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_concurrent_same_key_commits_once(client):
    item = product(client)
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: movement(client, item, "IN", 10, key), range(2))
        )
    assert all(r.status_code in (200, 201) for r in responses)
    assert responses[0].json() == responses[1].json()
    assert current(client, item)["current_stock"] == 10
    assert len(client.get("/api/movements").json()["items"]) == 1


def test_stock_limit_and_missing_reason_no_partial_write(client):
    item = product(client)
    assert movement(client, item, "IN", 2147483647).status_code in (200, 201)
    item = current(client, item)
    assert movement(client, item, "IN", 1).status_code == 422
    invalid = client.post(
        "/api/movements",
        json={
            "product_id": item["id"],
            "type": "OUT",
            "quantity": 1,
            "reason": "   ",
            "expected_version": item["version"],
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert invalid.status_code == 422
    assert current(client, item)["current_stock"] == 2147483647
    assert len(client.get("/api/movements").json()["items"]) == 1


@pytest.mark.parametrize(
    "price", ["NaN", "Infinity", "12.34567", "-1", "1000000000000"]
)
def test_invalid_price_leaves_no_history(client, price):
    item = product(client)
    response = client.patch(
        f'/api/products/{item["id"]}/price',
        json={
            "price": price,
            "expected_version": item["version"],
            "reason": "Invalide",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422
    assert current(client, item)["current_price"] == "12.3400"
    assert client.get(f'/api/products/{item["id"]}/prices').json()["items"] == []


def test_manager_can_operate_but_cannot_manage_users(client, app):
    response = client.post(
        "/api/auth/users",
        json={
            "name": "Gestionnaire secondaire",
            "email": "manager@example.test",
            "password": "ManagerTest321!",
            "role": "MANAGER",
        },
    )
    assert response.status_code == 201
    with TestClient(app) as manager:
        assert (
            manager.post(
                "/api/auth/login",
                json={"email": "manager@example.test", "password": "ManagerTest321!"},
            ).status_code
            == 200
        )
        item = product(manager)
        assert movement(manager, item, "IN", 10).status_code == 201
        assert (
            manager.post(
                "/api/auth/users",
                json={
                    "name": "Interdit",
                    "email": "no@example.test",
                    "password": "ManagerTest321!",
                    "role": "ADMIN",
                },
            ).status_code
            == 403
        )


def test_large_price_exact_string_roundtrip(client):
    item = product(client, current_price="999999999999.9999")
    assert current(client, item)["current_price"] == "999999999999.9999"
