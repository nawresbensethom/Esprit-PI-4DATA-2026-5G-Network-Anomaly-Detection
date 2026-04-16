from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://dashboard:dashboard123@postgres:5432/dashboard"
    JWT_SECRET: str = "supersecretkey"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    JWT_REFRESH_EXPIRY_DAYS: int = 7

    DEFAULT_ADMIN_EMAIL: str = "admin@esprit.tn"
    DEFAULT_ADMIN_PASSWORD: str = "Admin123!"
    DEFAULT_ADMIN_NAME: str = "Default Admin"

    class Config:
        env_file = ".env"


settings = Settings()
