from fastapi import FastAPI

app = FastAPI(title="inference-svc", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inference-svc"}