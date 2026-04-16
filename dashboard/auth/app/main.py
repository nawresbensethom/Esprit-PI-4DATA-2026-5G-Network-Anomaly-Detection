from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import SessionLocal, init_db
from app.routes import auth, users
from app.services.auth_service import ensure_default_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as db:
        await ensure_default_admin(db)
    yield


app = FastAPI(title="auth-svc", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-svc"}