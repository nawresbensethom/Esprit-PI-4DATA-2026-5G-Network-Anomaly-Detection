"""
Thin MLflow wrapper used by scripts/train.py and scripts/promote.py.
All MLflow interactions go through this module — keeps the training script
free of mlflow-specific boilerplate and makes the client easy to stub in tests.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

try:
    import mlflow
    import mlflow.sklearn
    import mlflow.tensorflow
    from mlflow.tracking import MlflowClient as _MlflowClient

    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


def _require_mlflow() -> None:
    if not _MLFLOW_AVAILABLE:
        raise ImportError(
            "mlflow is not installed. Run: pip install mlflow psycopg2-binary"
        )


def configure(tracking_uri: str, experiment_name: str) -> None:
    """Set the tracking URI and create the experiment if it doesn't exist."""
    _require_mlflow()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)


@contextmanager
def start_run(
    run_name: str | None = None,
    tags: dict[str, str] | None = None,
) -> Generator[Any, None, None]:
    """Context manager that starts an MLflow run and yields the run object."""
    _require_mlflow()
    with mlflow.start_run(run_name=run_name, tags=tags or {}) as run:
        yield run


def log_params(params: dict[str, Any]) -> None:
    _require_mlflow()
    # MLflow requires string values for params
    mlflow.log_params({k: str(v) for k, v in params.items()})


def log_metrics(metrics: dict[str, float], step: int | None = None) -> None:
    _require_mlflow()
    clean = {k: v for k, v in metrics.items() if v == v}  # drop NaN
    mlflow.log_metrics(clean, step=step)


def log_artefacts(directory: Path) -> None:
    """Upload the entire artefacts directory to MLflow."""
    _require_mlflow()
    mlflow.log_artifacts(str(directory), artifact_path="artefacts")


def log_figure(fig: Any, filename: str) -> None:
    """Log a matplotlib figure."""
    _require_mlflow()
    mlflow.log_figure(fig, filename)


def register_model(run_id: str, model_name: str = "unified_moe") -> Any:
    """Register the model artefacts from a run in the Model Registry."""
    _require_mlflow()
    client = _MlflowClient()
    run = client.get_run(run_id)
    artifact_uri = run.info.artifact_uri + "/artefacts"
    return mlflow.register_model(model_uri=artifact_uri, name=model_name)


def set_stage(
    model_name: str,
    version: str | int,
    stage: str,
    archive_existing: bool = True,
) -> None:
    _require_mlflow()
    client = _MlflowClient()
    client.transition_model_version_stage(
        name=model_name,
        version=str(version),
        stage=stage,
        archive_existing_versions=archive_existing,
    )


def get_run_metrics(run_id: str) -> dict[str, float]:
    _require_mlflow()
    client = _MlflowClient()
    return dict(client.get_run(run_id).data.metrics)


def current_run_id() -> str | None:
    _require_mlflow()
    run = mlflow.active_run()
    return run.info.run_id if run else None
