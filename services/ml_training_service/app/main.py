from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from libs.common.http_security import same_origin_request
from .api.routes.health import router as health_router
from .api.routes.train import router as train_router
from .api.routes.train_demand import router as train_demand_ml_router
from .api.routes.train_price import router as train_price_router
from .api.routes.train_anomaly import router as train_anomaly_router
from .api.routes.train_promo import router as train_promo_router


app = FastAPI(title="ml-training-service")
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)


@app.middleware("http")
async def local_access_only(request, call_next):
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse(
            status_code=403, content={"detail": "Service ML réservé à un accès local."}
        )
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not same_origin_request(
        request
    ):
        return JSONResponse(
            status_code=403, content={"detail": "Origine de requête non autorisée."}
        )
    return await call_next(request)


@app.exception_handler(FileNotFoundError)
async def missing_training_data(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": "Données d'entraînement absentes; aucun modèle généré."},
    )


@app.exception_handler(ValueError)
async def invalid_training_data(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Données invalides ou historique insuffisant pour entraîner."
        },
    )


app.include_router(health_router)
app.include_router(train_router)
app.include_router(train_demand_ml_router)
app.include_router(train_price_router)
app.include_router(train_anomaly_router)
app.include_router(train_promo_router)
