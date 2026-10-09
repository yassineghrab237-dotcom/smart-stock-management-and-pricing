from fastapi import APIRouter, Depends, Request
from libs.common.database import connect, db_path
from libs.common.security import current_user
from services.alerts_service.app.services.alert_service import stock_alerts
from services.stock_service.app.repositories.stock_repo import MOVEMENT_SELECT

router = APIRouter(tags=["Alertes et tableau de bord"])


@router.get("/alerts")
def alerts(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        return {"items": stock_alerts(db)}


@router.get("/dashboard")
def dashboard(request: Request, user=Depends(current_user)):
    with connect(db_path(request)) as db:
        counts = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(current_stock),0) FROM products"
        ).fetchone()
        alerts = stock_alerts(db)
        return {
            "product_count": counts[0],
            "total_units": counts[1],
            "low_stock_count": sum(a["type"] == "LOW_STOCK" for a in alerts),
            "overstock_count": sum(a["type"] == "OVERSTOCK" for a in alerts),
            "recent_movements": [
                dict(r)
                for r in db.execute(MOVEMENT_SELECT + " ORDER BY m.id DESC LIMIT 10")
            ],
        }
