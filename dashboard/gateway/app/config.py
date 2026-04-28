from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://auth-svc:8001"
    UPLOAD_SERVICE_URL: str = "http://upload-svc:8002"
    REPORT_SERVICE_URL: str = "http://report-svc:8004"
    INFERENCE_SERVICE_URL: str = "http://inference-svc:8003"
    TRAINING_SERVICE_URL: str = "http://moe-training-svc:8010"
    MONITORING_SERVICE_URL: str = "http://moe-monitoring-svc:8011"
    INTERNAL_API_KEY: str = "changeme"
    JWT_SECRET: str = "supersecretkey"
    JWT_ALGORITHM: str = "HS256"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
