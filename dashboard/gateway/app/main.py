from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import auth_proxy, inference_proxy, monitoring_proxy, training_proxy

app = FastAPI(title="api-gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_proxy.router)
app.include_router(inference_proxy.router)
app.include_router(training_proxy.router)
app.include_router(monitoring_proxy.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}
