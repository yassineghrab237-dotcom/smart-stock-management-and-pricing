from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from libs.common.database import connect, db_path
from libs.common.security import current_user
from services.stock_service.app.services.insights import report, TUNIS

router = APIRouter(prefix="/insights", tags=["Rentabilité et assortiment"])


@router.get("/sales")
def sales(
    request: Request,
    start: date | None = None,
    end: date | None = None,
    customer_id: int | None = Query(default=None, ge=1, le=9223372036854775807),
    user=Depends(current_user),
):
    today = datetime.now(TUNIS).date()
    end = end or today
    start = start or end - timedelta(days=89)
    if start > end or end > today or (end - start).days > 3660:
        raise HTTPException(
            422, "Choisissez une période passée ou actuelle de dix ans au maximum."
        )
    with connect(db_path(request)) as db:
        db.execute("BEGIN")
        return report(db, start, end, customer_id)
