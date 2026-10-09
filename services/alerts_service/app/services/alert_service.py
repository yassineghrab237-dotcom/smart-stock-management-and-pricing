def stock_alerts(db):
    alerts = []
    for row in db.execute(
        "SELECT id,name,sku,current_stock,threshold_min,threshold_max FROM products ORDER BY name,id"
    ):
        if row["current_stock"] < row["threshold_min"]:
            alerts.append(
                {
                    "id": f"low:{row['id']}",
                    "product_id": row["id"],
                    "product_name": row["name"],
                    "sku": row["sku"],
                    "type": "LOW_STOCK",
                    "severity": "critical" if row["current_stock"] == 0 else "warning",
                    "message": "Stock inférieur au seuil minimum.",
                    "current_stock": row["current_stock"],
                    "threshold": row["threshold_min"],
                }
            )
        if (
            row["threshold_max"] is not None
            and row["current_stock"] > row["threshold_max"]
        ):
            alerts.append(
                {
                    "id": f"over:{row['id']}",
                    "product_id": row["id"],
                    "product_name": row["name"],
                    "sku": row["sku"],
                    "type": "OVERSTOCK",
                    "severity": "warning",
                    "message": "Stock supérieur au seuil maximum.",
                    "current_stock": row["current_stock"],
                    "threshold": row["threshold_max"],
                }
            )
    return alerts
