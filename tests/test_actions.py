from uuid import uuid4
from tests.test_commerce import client
from libs.common.database import connect


def test_decision_replay_changed_condition_and_history(client):
    with connect(client.app.state.db_path, write=True) as db:
        db.execute("UPDATE products SET threshold_min=20 WHERE id=1")
    action = client.get("/api/actions").json()["items"][0]
    body = dict(
        action_key=action["key"],
        expected_event_id=0,
        status="ACKNOWLEDGED",
        reason="Commande en préparation",
        idempotency_key=str(uuid4()),
    )
    first = client.post("/api/actions/decisions", json=body)
    assert first.status_code == 200, first.text
    assert client.post("/api/actions/decisions", json=body).json() == first.json()
    assert (
        client.post(
            "/api/actions/decisions", json={**body, "idempotency_key": str(uuid4())}
        ).status_code
        == 409
    )
    assert client.get("/api/actions").json()["items"][0]["status"] == "ACKNOWLEDGED"
    with connect(client.app.state.db_path, write=True) as db:
        db.execute("UPDATE products SET threshold_min=5 WHERE id=1")
    r = client.get("/api/actions").json()
    assert not r["items"] and len(r["events"]) == 1
    assert (
        client.post(
            "/api/actions/decisions",
            json={
                **body,
                "expected_event_id": first.json()["id"],
                "idempotency_key": str(uuid4()),
            },
        ).status_code
        == 409
    )


def test_task_deadline_and_viewer(client):
    c = client.post(
        "/api/crm/contacts", json=dict(name="QA", idempotency_key=str(uuid4()))
    ).json()
    r = client.post(
        f"/api/crm/contacts/{c['id']}/tasks",
        json=dict(title="Appeler", due_on="2020-01-01", idempotency_key=str(uuid4())),
    )
    assert r.status_code == 201, r.text
    a = next(
        a for a in client.get("/api/actions").json()["items"] if a["kind"] == "CRM_TASK"
    )
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
    assert client.get("/api/actions").status_code == 200
    assert (
        client.post(
            "/api/actions/decisions",
            json=dict(
                action_key=a["key"],
                expected_event_id=0,
                status="IN_PROGRESS",
                reason="QA",
                idempotency_key=str(uuid4()),
            ),
        ).status_code
        == 403
    )
