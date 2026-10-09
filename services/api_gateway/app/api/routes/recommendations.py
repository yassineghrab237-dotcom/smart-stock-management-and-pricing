from typing import Annotated
from fastapi import APIRouter, Depends, Request, Path
from libs.ml_bridge import recommendation as ml_recommendation
from libs.common.database import connect, db_path
from libs.common.security import current_user
from services.stock_service.app.repositories.stock_repo import product

router = APIRouter(prefix="/pricing/recommendations", tags=["Recommandations"])


@router.get("/{product_id}")
def recommendation(
    product_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    request: Request,
    user=Depends(current_user),
):
    with connect(db_path(request)) as db:
        stock_product = product(db, product_id)
    return ml_recommendation(dict(stock_product))
