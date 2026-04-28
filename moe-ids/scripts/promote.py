"""
Promote an MLflow run to staging or production.
Validates metric thresholds before promoting — a failing model is blocked.

Usage:
    python scripts/promote.py --run-id <RUN_ID> --to staging
    python scripts/promote.py --run-id <RUN_ID> --to production
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mlops import mlflow_client as mlc
from moe_ids.config import settings


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--run-id", help="Promote a specific MLflow run ID")
    grp.add_argument(
        "--latest",
        action="store_true",
        help="Auto-pick the most recent run from the experiment",
    )
    p.add_argument("--to", choices=["staging", "production"], required=True)
    p.add_argument("--experiment", default=None,
                   help="Override experiment name (defaults to settings.mlflow_experiment_name)")
    p.add_argument("--mlflow-tracking-uri", default=None,
                   help="Override MLflow URI (defaults to settings.mlflow_tracking_uri)")
    p.add_argument("--reload-url", default=None,
                   help="If set, POST to this URL after promotion (e.g. inference /admin/reload)")
    p.add_argument("--reload-api-key", default=None,
                   help="X-Api-Key header value for the reload POST (defaults to env API_KEY)")
    return p.parse_args()


def _pick_latest_run_id(experiment_name: str) -> str:
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        raise RuntimeError(f"Experiment {experiment_name!r} not found")
    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        max_results=1,
        order_by=["attributes.start_time DESC"],
    )
    if not runs:
        raise RuntimeError(f"No runs found in experiment {experiment_name!r}")
    return runs[0].info.run_id


def _post_reload(url: str, api_key: str | None) -> None:
    try:
        import os

        import httpx

        headers = {"X-Api-Key": api_key or os.environ.get("API_KEY", "changeme")}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, headers=headers)
            if resp.is_success:
                print(f"  Reload OK ({resp.status_code}) at {url}")
            else:
                print(f"  Reload returned {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:
        print(f"  [WARN] Reload call failed: {exc}")


def main() -> None:
    args = parse_args()
    uri = args.mlflow_tracking_uri or settings.mlflow_tracking_uri
    experiment = args.experiment or settings.mlflow_experiment_name

    try:
        mlc.configure(uri, experiment)
        run_id = args.run_id or _pick_latest_run_id(experiment)
        if args.latest:
            print(f"Picked latest run from {experiment!r}: {run_id}")
        metrics = mlc.get_run_metrics(run_id)
    except Exception as e:
        print(f"ERROR: Cannot connect to MLflow at {uri}: {e}")
        sys.exit(1)

    # Metric keys logged by scripts/train.py
    f1 = metrics.get("moe_f1", 0.0)
    recall = metrics.get("moe_recall", 0.0)
    pr_auc = metrics.get("moe_pr_auc", 0.0)

    failures: list[str] = []
    if f1 < settings.min_f1:
        failures.append(f"F1 {f1:.4f} < required {settings.min_f1}")
    if recall < settings.min_recall:
        failures.append(f"Recall {recall:.4f} < required {settings.min_recall}")
    if pr_auc < settings.min_pr_auc:
        failures.append(f"PR-AUC {pr_auc:.4f} < required {settings.min_pr_auc}")

    if failures:
        print("PROMOTION BLOCKED — the following thresholds were not met:")
        for msg in failures:
            print(f"  ✗ {msg}")
        print(f"\nRun: {run_id}")
        print("To promote anyway, lower thresholds in .env or Settings.")
        sys.exit(1)

    # All checks passed — register + transition
    try:
        mv = mlc.register_model(run_id)
        mlc.set_stage("unified_moe", mv.version, args.to, archive_existing=True)
        print(f"✓ Model version {mv.version} promoted to '{args.to}'")
        print(f"  F1={f1:.4f}  Recall={recall:.4f}  PR-AUC={pr_auc:.4f}")
        print(f"  Run ID: {run_id}")
    except Exception as e:
        print(f"ERROR during model registration/transition: {e}")
        sys.exit(1)

    if args.reload_url and args.to == "production":
        print(f"\nTriggering hot-reload at {args.reload_url} ...")
        _post_reload(args.reload_url, args.reload_api_key)


if __name__ == "__main__":
    main()
