from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from services.api_gateway.app.main import create_app

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "market.sqlite3")) as http:
        http.post("/api/auth/setup", json={"name":"QA", "email":"qa@example.test", "password":"LocalTest321!"})
        http.post("/api/products", json={"name":"PC QA", "sku":"QA", "current_price":"100"})
        yield http

def body(**changes):
    value=dict(product_id=1, retailer="Tunisianet", source_url="https://www.tunisianet.com.tn/pc-qa.html",
      manufacturer_ref="M123",variant="16 Go, 512 Go, neuf, garantie 1 an",price="100.1234",currency="TND",
      tax_basis="TTC",delivery="5",availability="IN_STOCK",confirmed=True,note="Recette fictive",
      observed_at=datetime.now(timezone.utc).isoformat(),idempotency_key=str(uuid4()))
    value.update(changes)
    return value

def rows(c):
    return c.get("/api/market/products/1").json()["items"]

def test_comparison_retry_and_preservation(client):
    before=client.get("/api/products/1").json()
    a=body(); first=client.post("/api/market/observations",json=a)
    assert first.status_code==201,first.text
    assert client.post("/api/market/observations",json=a).json()==first.json()
    assert client.post("/api/market/observations",json={**a,"price":"90"}).status_code==409
    assert len(rows(client))==1
    b=body(retailer="Mytek", source_url="https://mytek.tn/pc.html", price="110.1234",delivery="0")
    assert client.post("/api/market/observations",json=b).status_code==201
    assert sorted(r["delta_to_lowest"] for r in rows(client))==["0.0000","5.0000"]
    assert client.get("/api/products/1").json()==before

@pytest.mark.parametrize("changes",[
 {"source_url":"https://mytek.tn.evil.test/x"}, {"source_url":"http://www.tunisianet.com.tn/x"},
 {"price":"NaN"},{"price":"-1"},{"price":"1.12345"},{"manufacturer_ref":"   "},
 {"observed_at":"2039-01-01T00:00:00+00:00"},{"observed_at":"2025-01-01"},
 {"source_url":"https://user@www.tunisianet.com.tn/x"},
])
def test_invalid(client,changes):
    assert client.post("/api/market/observations",json=body(**changes)).status_code==422
    assert not rows(client)

@pytest.mark.parametrize("changes",[
 {"confirmed":False},{"availability":"UNKNOWN"},{"availability":"OUT_OF_STOCK"},
 {"delivery":None},{"tax_basis":"UNKNOWN"},{"currency":"EUR"},{"variant":"8 Go"},
 {"observed_at":(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()},
])
def test_noncomparable(client,changes):
    client.post("/api/market/observations",json=body())
    client.post("/api/market/observations",json=body(retailer="Mytek",source_url="https://mytek.tn/x",**changes))
    assert all(r["delta_to_lowest"] is None for r in rows(client))

def test_latest_supersedes_and_viewer_denied(client):
    client.post("/api/market/observations",json=body())
    client.post("/api/market/observations",json=body(availability="OUT_OF_STOCK"))
    result=rows(client)
    assert len(result)==2
    assert result[0]["current"] and not result[0]["eligible"] and not result[1]["current"]
    client.post("/api/auth/users",json={"name":"Lecteur", "email":"viewer@example.test", "password":"LocalTest321!", "role":"VIEWER"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login",json={"email":"viewer@example.test", "password":"LocalTest321!"})
    assert client.get("/api/market/products/1").status_code==200
    assert client.post("/api/market/observations",json=body()).status_code==403
    client.post("/api/auth/logout")
    assert client.get("/api/market/products/1").status_code==401


def test_restart_and_bounded_id(client):
    from libs.common.database import initialize
    client.post("/api/market/observations",json=body())
    initialize(client.app.state.db_path)
    assert len(rows(client))==1
    assert client.get("/api/market/products/99999999999999999999999").status_code==422
    assert client.get("/api/market/products/0").status_code==422
