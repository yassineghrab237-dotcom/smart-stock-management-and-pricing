"""Crée uniquement une NOUVELLE base de recette ; aucune lecture de la base réelle."""

import json, os, secrets, sys, uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def create_demo():
    folder = ROOT / "runtime" / ("recette-" + uuid.uuid4().hex[:12])
    folder.mkdir()
    path = folder / "isolated.sqlite3"
    os.environ["SMART_STOCK_DB"] = str(path)
    os.environ["SMART_STOCK_COLLECTION"] = "0"
    from fastapi.testclient import TestClient
    from services.api_gateway.app.main import create_app

    password = "Recette9!" + secrets.token_urlsafe(14)
    with TestClient(create_app(path)) as c:

        def post(route, body):
            response = c.post(
                "/api" + route,
                json=(
                    {**body, "idempotency_key": str(uuid.uuid4())}
                    if route not in ("/auth/setup", "/products")
                    else body
                ),
            )
            if response.status_code not in (200, 201):
                raise RuntimeError(route + " : " + response.text)
            return response.json()

        post(
            "/auth/setup",
            dict(
                name="Administrateur recette",
                email="demo@precios.test",
                password=password,
            ),
        )
        supplier = post(
            "/crm/contacts",
            dict(
                name="Fournisseur démo informatique",
                kind="SUPPLIER",
                company="Entreprise fictive",
                lead_days=5,
            ),
        )
        customer = post(
            "/crm/contacts",
            dict(
                name="Client démo entreprise",
                kind="CUSTOMER",
                company="Société fictive",
            ),
        )
        products = []
        for sku, name, stock, low, high in [
            ("DEMO-PC", "PC portable démo 16 Go / 512 Go", 12, 4, 20),
            ("DEMO-SOURIS", "Souris démo sans fil", 25, 8, 40),
            ("DEMO-USB", "Câble USB-C démo", 3, 5, 30),
        ]:
            p = post(
                "/products",
                dict(sku=sku, name=name, threshold_min=low, threshold_max=high),
            )
            post(
                "/movements",
                dict(
                    product_id=p["id"],
                    type="IN",
                    quantity=stock,
                    reason="Stock initial fictif de recette",
                    expected_version=p["version"],
                ),
            )
            products.append(p)
        post(
            f"/crm/contacts/{customer['id']}/tasks",
            dict(title="Vérifier le devis démo", due_on=date.today().isoformat()),
        )
        for i in range(2):
            doc = post(
                "/commerce/documents",
                dict(
                    kind="SALE",
                    reference=f"DEMO-VENTE-{i+1}",
                    customer_id=customer["id"],
                    note="Panier fictif",
                    lines=[
                        dict(
                            product_id=products[0]["id"],
                            quantity=1,
                            unit_price_ttc="1190",
                            tax_rate="19",
                            unit_cost_ht="780",
                        ),
                        dict(
                            product_id=products[1]["id"],
                            quantity=1,
                            unit_price_ttc="35.7",
                            tax_rate="19",
                            unit_cost_ht="18",
                        ),
                    ],
                ),
            )
            versions = {
                str(p["id"]): c.get(f"/api/products/{p['id']}").json()["version"]
                for p in products[:2]
            }
            post(
                f"/commerce/documents/{doc['id']}/confirm",
                dict(expected_version=doc["version"], product_versions=versions),
            )
        quote = post(
            "/commerce/documents",
            dict(
                kind="QUOTE",
                reference="DEMO-DEVIS-001",
                customer_id=customer["id"],
                note="Devis fictif pour essai",
                lines=[
                    dict(
                        product_id=products[0]["id"],
                        quantity=2,
                        unit_price_ttc="1190",
                        tax_rate="19",
                        unit_cost_ht="780",
                    )
                ],
            ),
        )
        post(
            f"/crm/contacts/{customer['id']}/opportunities",
            dict(
                title="Équipement démo entreprise",
                stage="PROPOSAL",
                expected_ttc="2380",
                close_on=date.today().isoformat(),
                quote_id=quote["id"],
                reason="Opportunité fictive",
            ),
        )
        order = post(
            "/purchases/orders",
            dict(
                reference="DEMO-ACHAT-001",
                supplier_id=supplier["id"],
                expected_on=(date.today() - timedelta(days=1)).isoformat(),
                note="Commande fictive",
                lines=[
                    dict(product_id=products[1]["id"], quantity=10, unit_cost_ht="18")
                ],
            ),
        )
        post(
            f"/purchases/orders/{order['id']}/confirm",
            dict(expected_version=order["version"]),
        )
        post(
            f"/replenishment/policies/{products[2]['id']}",
            dict(
                supplier_id=supplier["id"],
                unit_cost_ht="4",
                lead_days=5,
                min_quantity=5,
                pack_size=5,
                enabled=True,
                expected_version=0,
                reason="Conditions fictives",
            ),
        )
        post(
            "/inventories",
            dict(
                title="Comptage démo du rayon", product_ids=[p["id"] for p in products]
            ),
        )
    access = f"RECETTE LOCALE — DONNÉES FICTIVES\nURL : http://127.0.0.1:8000\nCompte : demo@precios.test\nMot de passe : {password}\nBase : {path}\nAucune URL concurrente activée automatiquement.\n"
    (folder / "ACCES_RECETTE.txt").write_text(access, encoding="utf-8")
    # Pointer contains no password; new runs never overwrite an existing recipe database.
    (ROOT / "runtime" / "latest-recipe.json").write_text(
        json.dumps(
            dict(database=str(path), access_file=str(folder / "ACCES_RECETTE.txt")),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(str(folder / "ACCES_RECETTE.txt"))
    return path


if __name__ == "__main__":
    create_demo()
