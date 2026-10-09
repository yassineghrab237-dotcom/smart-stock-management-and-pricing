import json
from fastapi import HTTPException

MOVEMENT_SELECT = "SELECT m.id,m.product_id,p.name product_name,p.sku,m.type,m.quantity,m.reason,m.stock_before,m.stock_after,m.created_at,u.name actor_name FROM movements m JOIN products p ON p.id=m.product_id JOIN users u ON u.id=m.actor_id"


def product(db, product_id):
    row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Produit introuvable.")
    return dict(row)


def check_version(item, expected):
    if item["version"] != expected:
        raise HTTPException(
            409, "Le produit a été modifié. Actualisez avant de réessayer."
        )


def existing_request(db, key, actor_id, payload):
    row = db.execute("SELECT * FROM idempotency WHERE key=?", (key,)).fetchone()
    fingerprint = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if row:
        if row["actor_id"] != actor_id or row["payload"] != fingerprint:
            raise HTTPException(
                409,
                "Cette clé d'idempotence a déjà été utilisée pour une autre opération.",
            )
        return json.loads(row["response"]), fingerprint
    return None, fingerprint


def remember(db, key, actor_id, fingerprint, result):
    db.execute(
        "INSERT INTO idempotency VALUES (?,?,?,?)",
        (key, actor_id, fingerprint, json.dumps(result)),
    )
