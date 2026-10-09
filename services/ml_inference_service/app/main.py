from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .api.routes.health import router as health_router
from .api.routes.predict_demand import router as demand_router
from .api.routes.recommend_price import router as price_router
from .api.routes.recommend_restock import router as restock_router
from .api.routes.detect_anomalies import router as anomaly_router
from .api.routes.predict_stock_risk import router as stock_risk_router
from .api.routes.recommend_promo import router as promo_router

app = FastAPI(title="ml-inference-service")
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)


@app.middleware("http")
async def local_access_only(request, call_next):
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse(
            status_code=403, content={"detail": "Service ML réservé à un accès local."}
        )
    return await call_next(request)


@app.exception_handler(FileNotFoundError)
async def unavailable_data(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Données ou modèles locaux absents; calcul indisponible."},
    )


@app.exception_handler(ValueError)
async def unusable_model(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Modèle non enregistré localement ou données invalides."},
    )


app.include_router(health_router)
app.include_router(demand_router)
app.include_router(price_router)
app.include_router(restock_router)
app.include_router(anomaly_router)
app.include_router(stock_risk_router)
app.include_router(promo_router)
