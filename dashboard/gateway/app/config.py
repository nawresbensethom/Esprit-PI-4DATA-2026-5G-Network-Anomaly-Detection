from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://auth-svc:8001"
    UPLOAD_SERVICE_URL: str = "http://upload-svc:8002"
    REPORT_SERVICE_URL: str = "http://report-svc:8004"
    INFERENCE_SERVICE_URL: str = "http://inference-svc:8003"
    JWT_SECRET: str = "supersecretkey"
    JWT_ALGORITHM: str = "HS256"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
