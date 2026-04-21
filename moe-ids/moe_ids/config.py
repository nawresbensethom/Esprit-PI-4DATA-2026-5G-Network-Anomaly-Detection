from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Data paths ───────────────────────────────────────────────────────
    data_5g_path: Path = Path("../MoE/Global_CLEANED.csv")
    data_6g_path: Path = Path("../MoE/AIoT_6G_CLEANED.csv")

    # ── Artefact storage ─────────────────────────────────────────────────
    artefacts_dir: Path = Path("artefacts")
    model_version: str = "v1"

    # ── Training hyperparams ─────────────────────────────────────────────
    seed: int = 42
    xgb_n_estimators: int = 200
    xgb_max_depth: int = 5
    xgb_learning_rate: float = 0.1
    ae_epochs: int = 80
    ae_batch_size: int = 64
    ae_bottleneck: int = 6
    gate_epochs: int = 80
    gate_batch_size: int = 128
    test_size: float = 0.20
    val_size: float = 0.15
    anomaly_fraction: float = 0.15

    # ── Inference ─────────────────────────────────────────────────────────
    prediction_threshold: float = 0.5
    max_batch_file_mb: int = 100

    # ── MLflow ────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "unified_moe"

    # ── Promotion thresholds ─────────────────────────────────────────────
    min_f1: float = 0.90
    min_recall: float = 0.95
    min_pr_auc: float = 0.92

    # ── API ───────────────────────────────────────────────────────────────
    api_key: str = "changeme"
    webapp_origin: str = "http://localhost:3000"
    log_dir: Path = Path("logs/predictions")

    # ── Monitoring ────────────────────────────────────────────────────────
    # Set to a psycopg2-compatible DSN to enable PostgreSQL prediction logging.
    # Leave empty to use JSONL-only logging.
    monitoring_db_url: str = ""


settings = Settings()
