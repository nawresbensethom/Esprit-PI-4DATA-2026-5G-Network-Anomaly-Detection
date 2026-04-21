from fastapi import FastAPI

from app.routes import predict

app = FastAPI(title="inference-svc", version="0.1.0")
app.include_router(predict.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inference-svc"}