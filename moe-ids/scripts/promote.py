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
    p.add_argument("--run-id", required=True)
    p.add_argument("--to", choices=["staging", "production"], required=True)
    p.add_argument("--mlflow-tracking-uri", default=None,
                   help="Override MLflow URI (defaults to settings.mlflow_tracking_uri)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    uri = args.mlflow_tracking_uri or settings.mlflow_tracking_uri

    try:
        mlc.configure(uri, settings.mlflow_experiment_name)
        metrics = mlc.get_run_metrics(args.run_id)
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
        print(f"\nRun: {args.run_id}")
        print("To promote anyway, lower thresholds in .env or Settings.")
        sys.exit(1)

    # All checks passed — register + transition
    try:
        mv = mlc.register_model(args.run_id)
        mlc.set_stage("unified_moe", mv.version, args.to, archive_existing=True)
        print(f"✓ Model version {mv.version} promoted to '{args.to}'")
        print(f"  F1={f1:.4f}  Recall={recall:.4f}  PR-AUC={pr_auc:.4f}")
        print(f"  Run ID: {args.run_id}")
    except Exception as e:
        print(f"ERROR during model registration/transition: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
