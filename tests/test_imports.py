"""Imports HTTP sur une base isolée : aperçu, atomicité, droits et reprise."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest
from fastapi.testclient import TestClient
from services.api_gateway.app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "imports.sqlite3")
    with TestClient(app) as http:
        assert (
            http.post(
                "/api/auth/setup",
                json={
                    "name": "QA Import",
                    "email": "import@example.test",
                    "password": "ImportTest123!",
                },
            ).status_code
            == 201
        )
        yield http


def source(text, kind="catalogue", **extra):
    return {"kind": kind, "csv_text": text, "filename": "recette.csv", **extra}


def analyze(client, body):
    response = client.post("/api/imports/preview", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def commit(client, body, preview=None):
    preview = preview or analyze(client, body)
    return client.post(
        "/api/imports/commit", json={**body, "preview_token": preview["preview_token"]}
    )


def test_catalogue_preview_no_write_commit_retry_and_restart(client):
    body = source(
        "\ufeffsku;name;current_price;threshold_min\nQA-A;Produit A;12.3456;2",
        delimiter=";",
    )
    result = analyze(client, body)
    assert result["valid"] and result["rows"][0]["data"]["current_price"] == "12.3456"
    assert client.get("/api/products").json()["items"] == []
    first = commit(client, body, result)
    assert first.status_code == 200
    repeated = commit(client, {**body, "filename": "renomme.csv"}, result)
    assert repeated.json()["already_imported"]
    assert repeated.json()["id"] == first.json()["id"]
    assert len(client.get("/api/products").json()["items"]) == 1
    other = TestClient(create_app(client.app.state.db_path))
    other.post(
        "/api/auth/login",
        json={"email": "import@example.test", "password": "ImportTest123!"},
    )
    assert other.get("/api/products").json()["items"][0]["current_stock"] == 0
    assert other.get("/api/imports").json()["items"][0]["row_count"] == 1
    other.close()


@pytest.mark.parametrize(
    "text",
    [
        "sku,name\nQA-A,A\nQA-A,B",
        "sku,name,current_price\nQA-A,A,NaN",
        "sku,name,current_price,min_price\nQA-A,A,1,2",
        "sku,name,threshold_min\nQA-A,A,1.5",
        "sku,name\nQA-A,A,extra",
    ],
)
def test_invalid_catalogue_is_atomic(client, text):
    body = source(text)
    result = analyze(client, body)
    assert not result["valid"]
    assert commit(client, body, result).status_code == 422
    assert client.get("/api/products").json()["items"] == []
    assert client.get("/api/imports").json()["items"] == []


def test_sales_exact_sku_history_and_no_stock_or_price_change(client):
    item = client.post(
        "/api/products", json={"sku": "QA-A", "name": "A", "current_price": "20"}
    ).json()
    body = source(
        "reference,sku,sold_on,quantity,unit_price\nSALE-1,QA-A,2025-01-02,3,12.3456",
        "sales",
    )
    result = analyze(client, body)
    assert result["rows"][0]["data"]["product_id"] == item["id"]
    assert client.get("/api/imports/sales").json()["items"] == []
    assert commit(client, body, result).status_code == 200
    assert commit(client, body, result).json()["already_imported"]
    sale = client.get("/api/imports/sales").json()["items"][0]
    assert sale["quantity"] == 3 and sale["unit_price"] == "12.3456"
    assert client.get(f'/api/products/{item["id"]}').json() == item
    assert client.get("/api/movements").json()["items"] == []
    duplicate = source(body["csv_text"] + "\n", "sales")
    assert not analyze(client, duplicate)["valid"]


@pytest.mark.parametrize(
    "row",
    [
        "SALE-1,UNKNOWN,2025-01-02,3,12",
        "SALE-1,QA-A,2099-01-02,3,12",
        "SALE-1,QA-A,2025-02-30,3,12",
        "SALE-1,QA-A,2025-01-02,0,12",
        "SALE-1,QA-A,2025-01-02,2147483648,12",
        "SALE-1,QA-A,2025-01-02,3,Infinity",
    ],
)
def test_sales_invalid_no_partial_write(client, row):
    client.post("/api/products", json={"sku": "QA-A", "name": "A"})
    body = source(
        "reference,sku,sold_on,quantity,unit_price\nGOOD,QA-A,2025-01-01,1,12\n" + row,
        "sales",
    )
    result = analyze(client, body)
    assert not result["valid"]
    assert commit(client, body, result).status_code == 422
    assert client.get("/api/imports/sales").json()["items"] == []


def test_stale_preview_and_changed_file_refused(client):
    item = client.post("/api/products", json={"sku": "QA-A", "name": "A"}).json()
    body = source(
        "reference,sku,sold_on,quantity,unit_price\nSALE,QA-A,2025-01-01,1,12", "sales"
    )
    result = analyze(client, body)
    client.patch(
        f'/api/products/{item["id"]}',
        json={"name": "Renommé", "expected_version": item["version"]},
    )
    assert commit(client, body, result).status_code == 409
    assert (
        commit(
            client,
            {**body, "csv_text": body["csv_text"].replace(",1,12", ",2,12")},
            result,
        ).status_code
        == 409
    )
    assert commit(client, body).status_code == 200


@pytest.mark.parametrize(
    "text",
    [
        "sku,sku,name\nA,A,A",
        "sku,name,stock\nA,A,100",
        "sku,name\n",
        'sku,name\nA,"unclosed',
        "sku,name\n" + "\n".join(f"QA-{i},A" for i in range(1001)),
    ],
)
def test_bad_structure_and_limits(client, text):
    assert client.post("/api/imports/preview", json=source(text)).status_code == 422


def test_permissions_and_origin(client):
    for role in ("MANAGER", "VIEWER"):
        client.post(
            "/api/auth/users",
            json={
                "name": "QA " + role,
                "email": role.lower() + "@example.test",
                "password": "ImportTest123!",
                "role": role,
            },
        )
    body = source("sku,name\nQA-A,A")
    assert (
        client.post(
            "/api/imports/preview",
            json=body,
            headers={"origin": "https://external.test"},
        ).status_code
        == 403
    )
    client.post("/api/auth/logout")
    assert client.post("/api/imports/preview", json=body).status_code == 401
    client.post(
        "/api/auth/login",
        json={"email": "viewer@example.test", "password": "ImportTest123!"},
    )
    assert client.get("/api/imports").status_code == 200
    assert client.post("/api/imports/preview", json=body).status_code == 403
    assert (
        client.post(
            "/api/imports/commit", json={**body, "preview_token": "0" * 64}
        ).status_code
        == 403
    )
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"email": "manager@example.test", "password": "ImportTest123!"},
    )
    assert commit(client, body).status_code == 200


def test_concurrent_commit_once(client):
    body = source("sku,name\nQA-A,A")
    result = analyze(client, body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: commit(client, body, result), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert {r.json()["already_imported"] for r in responses} == {False, True}
    with sqlite3.connect(client.app.state.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM csv_imports").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
