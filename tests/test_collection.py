import json
import socket
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from libs.common.database import connect, initialize
from services.api_gateway.app.main import create_app
from services.stock_service.app.services.collection.network import (
    CollectionError,
    safe_url,
    PublicHTTPS,
)
from services.stock_service.app.services.collection.parser import extract
from services.stock_service.app.services.collection.robots import rules
from services.stock_service.app.services.collection.worker import run_one, claim

URL = "https://www.mytek.tn/pc-qa.html"
PRODUCT = {
    "@type": "Product",
    "name": "PC QA",
    "mpn": "MPN-1",
    "sku": "merchant-99",
    "brand": {"name": "QA"},
    "offers": {
        "@type": "Offer",
        "price": "100.500",
        "priceCurrency": "TND",
        "availability": "https://schema.org/InStock",
    },
}


def page(product=PRODUCT):
    return (
        '<script type="application/ld+json">' + json.dumps(product) + "</script>"
    ).encode()


def key(**values):
    return dict(idempotency_key=str(uuid4()), **values)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "collection.sqlite3")) as c:
        c.post(
            "/api/auth/setup",
            json={
                "name": "QA",
                "email": "qa@example.test",
                "password": "LocalTest321!",
            },
        )
        c.post(
            "/api/products", json={"name": "PC QA", "sku": "QA", "current_price": "150"}
        )
        yield c


def setup(c):
    identity = c.post(
        "/api/collection/products/1/identity",
        json=key(
            brand="QA",
            manufacturer_ref="MPN-1",
            variant="16 Go / 512 Go, neuf, garantie 1 an",
            expected_version=0,
            reason="Vérification fabricant",
        ),
    )
    assert identity.status_code == 200, identity.text
    r = c.post(
        "/api/collection/products/1/watches",
        json=key(retailer="Mytek", source_url=URL, interval_hours=24),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def fake_fetch(retailer, url, before_request=None, max_bytes=None):
    if before_request:
        before_request(url)
    return url, (
        b"User-agent: *\nDisallow: /*?\n" if url.endswith("/robots.txt") else page()
    )


def state(c):
    return c.get("/api/collection/products/1").json()


def test_collect_review_replay_and_restart(client):
    setup(client)
    before = client.get("/api/products/1").json()
    path = client.app.state.db_path
    assert run_one(path, fetcher=fake_fetch, throttle=False)
    initialize(path)
    s = state(client)
    j = s["jobs"][0]
    assert j["status"] == "SUCCEEDED" and j["result"]["manufacturer_ref"] == "MPN-1"
    assert (
        j["result"]["merchant_sku"] == "merchant-99"
        and j["result"]["tax_basis"] == "UNKNOWN"
    )
    assert len(j["result"]["content_sha256"]) == 64
    assert client.get("/api/market/products/1").json()["items"] == []
    b = key(
        accept=True,
        note="Variante et garantie vérifiées sur la fiche.",
        tax_basis="TTC",
        delivery="7",
    )
    r = client.post(f"/api/collection/jobs/{j['id']}/review", json=b)
    assert r.status_code == 200, r.text
    assert (
        client.post(f"/api/collection/jobs/{j['id']}/review", json=b).json() == r.json()
    )
    assert len(client.get("/api/market/products/1").json()["items"]) == 1
    assert client.get("/api/products/1").json() == before
    assert not run_one(path, fetcher=fake_fetch, throttle=False)


def test_robots_denied_no_product_request(client):
    setup(client)
    calls = []

    def blocked(retailer, url, **kwargs):
        calls.append(url)
        return url, b"User-agent: *\nDisallow: /"

    run_one(client.app.state.db_path, fetcher=blocked, throttle=False)
    assert len(calls) == 1 and state(client)["jobs"][0]["status"] == "BLOCKED"
    assert not client.get("/api/market/products/1").json()["items"]


def test_failure_pause_and_stale_recovery(client):
    watch = setup(client)
    path = client.app.state.db_path

    def broken(*args, **kwargs):
        raise CollectionError("HTTP 403")

    run_one(path, fetcher=broken, throttle=False)
    assert state(client)["jobs"][0]["status"] == "FAILED"
    assert (
        client.post(f"/api/collection/watches/{watch}/run", json=key()).status_code
        == 409
    )
    with connect(path, write=True) as db:
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.execute(
            "UPDATE collection_jobs SET status='RUNNING',started_at=?,created_at=?",
            (old, old),
        )
        db.execute("UPDATE collection_watches SET next_due=?", (old,))
    job = claim(path)
    assert job and state(client)["jobs"][1]["status"] == "INTERRUPTED"
    assert claim(path) is None
    assert (
        client.post(
            f"/api/collection/watches/{watch}/state",
            json=key(enabled=False, expected_version=1),
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/collection/watches/{watch}/run", json=key()).status_code
        == 409
    )


def test_changed_identity_and_mismatched_mpn_cannot_publish(client):
    setup(client)
    path = client.app.state.db_path

    def mismatch(retailer, url, **kwargs):
        return url, (
            b"User-agent: *"
            if url.endswith("/robots.txt")
            else page({**PRODUCT, "mpn": "OTHER"})
        )

    run_one(path, fetcher=mismatch, throttle=False)
    j = state(client)["jobs"][0]
    assert (
        client.post(
            f"/api/collection/jobs/{j['id']}/review",
            json=key(accept=True, note="Contrôle"),
        ).status_code
        == 409
    )
    client.post(
        "/api/collection/products/1/identity",
        json=key(
            brand="QA",
            manufacturer_ref="OTHER",
            variant="16 Go",
            expected_version=1,
            reason="Correction",
        ),
    )
    assert (
        client.post(
            f"/api/collection/jobs/{j['id']}/review",
            json=key(accept=True, note="Contrôle"),
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/collection/jobs/{j['id']}/review",
            json=key(accept=False, note="Mauvaise fiche"),
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://mytek.tn/x",
        "https://mytek.tn.evil.test/x",
        "https://mytek.tn@127.0.0.1/x",
        "https://mytek.tn:444/x",
        "https://mytek.tn/x?q=1",
        "https://mytek.tn/",
        "https://mytek.tn/\\evil",
    ],
)
def test_bad_url(url):
    with pytest.raises(ValueError):
        safe_url("Mytek", url)


def test_network_private_dns_denied(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    with pytest.raises(CollectionError):
        PublicHTTPS("mytek.tn").connect()


def test_robots_specific_wildcard_encoded():
    robots = "User-agent: *\nDisallow: /*?\nDisallow: /private\nAllow: /private/public$\nCrawl-delay: 12"
    assert rules(robots, URL) == (True, 12)
    assert not rules(robots, URL + "?x=1")[0]
    assert rules(robots, "https://mytek.tn/private/public")[0]
    assert not rules(robots, "https://mytek.tn/private/public/extra")[0]
    assert not rules("User-agent: *\nDisallow: /caf%C3%A9", "https://mytek.tn/café")[0]
    assert rules(
        "User-agent: *\nDisallow: /\nUser-agent: PreciosMonitor\nAllow: /", URL
    )[0]


def test_parse_ambiguity_no_invented_fields():
    r = extract(page(), URL)
    assert r["price"] == "100.5000" and r["gtin"] == ""
    with pytest.raises(CollectionError):
        extract(
            page(
                [
                    {**PRODUCT, "url": "https://mytek.tn/a"},
                    {**PRODUCT, "url": "https://mytek.tn/b"},
                ]
            ),
            URL,
        )
    with pytest.raises(CollectionError):
        extract(
            page(
                {
                    **PRODUCT,
                    "offers": {
                        "@type": "AggregateOffer",
                        "lowPrice": "2",
                        "priceCurrency": "TND",
                    },
                }
            ),
            URL,
        )
    with pytest.raises(CollectionError):
        extract(
            page(
                {
                    **PRODUCT,
                    "offers": [
                        {**PRODUCT["offers"]},
                        {**PRODUCT["offers"], "price": "22"},
                    ],
                }
            ),
            URL,
        )
    with pytest.raises(CollectionError):
        extract(b"<html>CAPTCHA</html>", URL)


def test_roles_gtin_and_idempotency(client):
    b = key(
        brand="QA",
        manufacturer_ref="MPN",
        variant="Neuf",
        expected_version=0,
        reason="QA",
        gtin="12345678",
    )
    assert client.post("/api/collection/products/1/identity", json=b).status_code == 422
    setup(client)
    b = key(enabled=False, expected_version=1)
    first = client.post("/api/collection/watches/1/state", json=b)
    assert client.post("/api/collection/watches/1/state", json=b).json() == first.json()
    client.post(
        "/api/auth/users",
        json={
            "name": "Viewer",
            "email": "view@example.test",
            "password": "LocalTest321!",
            "role": "VIEWER",
        },
    )
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"email": "view@example.test", "password": "LocalTest321!"},
    )
    assert client.get("/api/collection/products/1").status_code == 200
    assert (
        client.post(
            "/api/collection/watches/1/state",
            json=key(enabled=True, expected_version=2),
        ).status_code
        == 403
    )


def test_unknown_availability_can_be_verified_without_changing_price(client):
    setup(client)

    def missing_stock(retailer, url, **kwargs):
        offer = {**PRODUCT["offers"]}
        offer.pop("availability")
        return url, (
            b"User-agent: *"
            if url.endswith("/robots.txt")
            else page({**PRODUCT, "offers": offer})
        )

    run_one(client.app.state.db_path, fetcher=missing_stock, throttle=False)
    job = state(client)["jobs"][0]
    assert job["result"]["availability"] == "UNKNOWN"
    result = client.post(
        f"/api/collection/jobs/{job['id']}/review",
        json=key(
            accept=True,
            note="Stock et variante vérifiés sur la page.",
            availability="IN_STOCK",
        ),
    )
    assert result.status_code == 200, result.text
    observation = client.get("/api/market/products/1").json()["items"][0]
    assert (
        observation["availability"] == "IN_STOCK" and observation["price"] == "100.5000"
    )
    assert state(client)["jobs"][0]["result"]["availability"] == "UNKNOWN"
