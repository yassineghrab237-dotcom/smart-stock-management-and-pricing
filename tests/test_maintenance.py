from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tests.test_commerce import client, create, confirm
from libs.common.maintenance import backup, restore, verify, manifest_path
from libs.common.database import connect
from scripts.maintenance import recover_admin
from services.api_gateway.app.main import create_app


def test_backup_restore_preserves_commerce_and_source(client, tmp_path):
    d = create(client)
    confirm(client, d)
    src = Path(client.app.state.db_path)
    copy = tmp_path / "copies" / "backup.sqlite3"
    dest = tmp_path / "restored.sqlite3"
    result = backup(src, copy)
    assert result["tables"]["commercial_documents"] == 1
    assert verify(copy)["sha256"] == result["sha256"]
    restore(copy, dest)
    with TestClient(create_app(dest)) as restored:
        assert (
            restored.post(
                "/api/auth/login",
                json=dict(email="qa@example.test", password="LocalTest321!"),
            ).status_code
            == 200
        )
        assert restored.get("/api/products/1").json()["current_stock"] == 8
        assert (
            restored.get("/api/commerce/documents/1").json()["totals"]["total_ttc"]
            == "238.0000"
        )
    with pytest.raises(ValueError):
        restore(copy, src)
    assert client.get("/api/products/1").json()["current_stock"] == 8
    with copy.open("ab") as f:
        f.write(b"changed")
    with pytest.raises(ValueError):
        verify(copy)


def test_backup_api_admin_and_download(client):
    r = client.post("/api/maintenance/backups")
    assert r.status_code == 201, r.text
    name = r.json()["filename"]
    assert client.get("/api/maintenance/backups").json()["items"][0]["verified"]
    assert client.get(f"/api/maintenance/backups/{name}/database").content.startswith(
        b"SQLite format 3"
    )
    assert client.get(f"/api/maintenance/backups/{name}/manifest").status_code == 200
    assert (
        client.get("/api/maintenance/backups/unknown.sqlite3/database").status_code
        == 404
    )
    client.post(
        "/api/auth/users",
        json=dict(
            name="Manager",
            email="m@example.test",
            password="LocalTest321!",
            role="MANAGER",
        ),
    )
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login", json=dict(email="m@example.test", password="LocalTest321!")
    )
    assert client.post("/api/maintenance/backups").status_code == 403
    assert client.get("/api/maintenance/backups").status_code == 403
    assert client.get(f"/api/maintenance/backups/{name}/database").status_code == 403


def test_recovery_requires_consent_expires_sessions_and_keeps_data(client):
    db = client.app.state.db_path
    with pytest.raises(ValueError):
        recover_admin(db, "qa@example.test", "NewLocalTest456!", "Recette")
    with pytest.raises(ValueError) as error:
        recover_admin(db, "qa@example.test", "Secret4", "Recette", True)
    assert "Secret4" not in str(error.value)
    recover_admin(db, "qa@example.test", "NewLocalTest456!", "Recette", True)
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json=dict(email="qa@example.test", password="LocalTest321!"),
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json=dict(email="qa@example.test", password="NewLocalTest456!"),
        ).status_code
        == 200
    )
    assert len(client.get("/api/products").json()["items"]) == 2
    with connect(db) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM local_recovery_events").fetchone()[
                0
            ]
            == 1
        )


def test_malformed_sqlite_safe_error(tmp_path):
    from libs.common.maintenance import inspect_database
    import pytest

    path = tmp_path / "malformed.sqlite3"
    path.write_bytes(b"not a SQLite database")
    with pytest.raises(ValueError, match="SQLite"):
        inspect_database(path)
