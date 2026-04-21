"""
End-to-end MoE training pipeline.
Reproduces Moe.ipynb logic from the command line.

Usage:
    python scripts/train.py \\
        --data-5g ../MoE/Global_CLEANED.csv \\
        --data-6g ../MoE/AIoT_6G_CLEANED.csv \\
        --artefacts-dir artefacts \\
        --seed 42
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script from the moe-ids/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

from mlops import mlflow_client as mlc
from moe_ids.artefacts import Artefacts, save_all
from moe_ids.calibration import fit_mse_sigmoid, fit_platt
from moe_ids.experts import train_protocol_autoencoder, train_slice_expert
from moe_ids.gate import N_EXPERTS, build_gate_model
from moe_ids.injection import inject_unified_anomalies
from moe_ids.projection import project_5g, project_6g

# ── CLI ───────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the Unified MoE IDS")
    p.add_argument("--data-5g", default="../MoE/Global_CLEANED.csv")
    p.add_argument("--data-6g", default="../MoE/AIoT_6G_CLEANED.csv")
    p.add_argument("--artefacts-dir", default="artefacts")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--version", default="v1")
    p.add_argument("--ae-epochs", type=int, default=80)
    p.add_argument("--gate-epochs", type=int, default=80)
    p.add_argument("--xgb-n-estimators", type=int, default=200)
    p.add_argument("--test-size", type=float, default=0.20)
    p.add_argument("--anomaly-fraction", type=float, default=0.15)
    p.add_argument("--mlflow-tracking-uri", default="http://localhost:5000")
    p.add_argument("--experiment", default="unified_moe")
    p.add_argument("--no-mlflow", action="store_true", help="Skip MLflow logging (offline mode)")
    return p.parse_args()


# ── Helpers ───────────────────────────────────────────────────────────────

def _metrics(y_true: np.ndarray, proba: np.ndarray, name: str) -> dict:
    pred = (proba >= 0.5).astype(int)
    n_classes = len(np.unique(y_true))
    return {
        "name": name,
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "auc_roc": float(roc_auc_score(y_true, proba)) if n_classes > 1 else float("nan"),
        "pr_auc": float(average_precision_score(y_true, proba)) if n_classes > 1 else float("nan"),
    }


def _print_metrics(m: dict) -> None:
    print(
        f"  {m['name']:20s}  F1={m['f1']:.4f}  Rec={m['recall']:.4f}"
        f"  Prec={m['precision']:.4f}  AUC={m['auc_roc']:.4f}  PR-AUC={m['pr_auc']:.4f}"
    )


# ── 5G pipeline ───────────────────────────────────────────────────────────

def _load_5g(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Label"] = df["Label"].astype(int)
    return df


def _split_by_slice(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Split Global_CLEANED into per-slice subsets.
    slice_2:mMTC and slice_3:URLLC are binary indicators;
    eMBB = rows where both are 0.
    """
    slices = {}
    if "slice_2:mMTC" in df.columns and "slice_3:URLLC" in df.columns:
        slices["mMTC"] = df[df["slice_2:mMTC"] == 1].copy()
        slices["URLLC"] = df[df["slice_3:URLLC"] == 1].copy()
        slices["eMBB"] = df[(df["slice_2:mMTC"] == 0) & (df["slice_3:URLLC"] == 0)].copy()
    else:
        # Fallback: treat all data as eMBB when slice indicators are absent
        slices["eMBB"] = df.copy()
        slices["mMTC"] = df.copy()
        slices["URLLC"] = df.copy()
    return slices


def train_5g(
    df5: pd.DataFrame,
    test_size: float,
    seed: int,
    n_estimators: int,
) -> tuple[dict, dict, dict, dict, np.ndarray, np.ndarray]:
    """
    Train all three 5G slice experts + calibrators.
    Returns (experts, calibrators, test_splits, metrics, X_all_proj, y_all).
    """
    slices = _split_by_slice(df5)

    slice_experts: dict = {}
    slice_calibrators: dict = {}
    slice_test: dict = {}
    all_metrics: dict = {}

    X_all_list, y_all_list = [], []

    for name, sub in slices.items():
        if len(sub) < 10:
            print(f"  [WARN] Slice {name} has only {len(sub)} rows — skipping")
            continue

        proj = project_5g(sub)
        y = sub["Label"].values.astype(int)

        X_tr, X_te, y_tr, y_te = train_test_split(
            proj.values, y, test_size=test_size, random_state=seed, stratify=y if y.sum() > 0 else None
        )
        X_tr2, X_val, y_tr2, y_val = train_test_split(
            X_tr, y_tr, test_size=0.15, random_state=seed, stratify=y_tr if y_tr.sum() > 0 else None
        )

        clf = train_slice_expert(X_tr2, y_tr2, name, seed=seed, n_estimators=n_estimators)
        slice_experts[name] = clf

        # Calibration on val set
        raw_val = clf.predict_proba(X_val)[:, 1]
        cal = fit_platt(raw_val, y_val)
        slice_calibrators[name] = cal

        # Test metrics
        raw_te = clf.predict_proba(X_te)[:, 1]
        from moe_ids.calibration import calibrate
        cal_te = calibrate(cal, raw_te)
        all_metrics[name] = _metrics(y_te, cal_te, f"5G/{name}")
        slice_test[name] = (X_te, y_te)

        X_all_list.append(proj.values)
        y_all_list.append(y)

    X_all = np.vstack(X_all_list).astype(np.float32)
    y_all = np.concatenate(y_all_list).astype(int)

    return slice_experts, slice_calibrators, slice_test, all_metrics, X_all, y_all


# ── 6G pipeline ───────────────────────────────────────────────────────────

def _load_6g(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # 6G dataset is all-benign; binarise label string → 0
    df["Label"] = (df["Label"].str.lower() != "benign").astype(int)
    return df


def _split_by_proto(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split 6G data into TCP/UDP subsets using the Proto_TCP OHE column."""
    if "Proto_TCP" in df.columns:
        return {
            "TCP": df[df["Proto_TCP"] == 1].copy(),
            "UDP": df[df["Proto_TCP"] == 0].copy(),
        }
    # Fallback: train both experts on the full dataset
    return {"TCP": df.copy(), "UDP": df.copy()}


def train_6g(
    df6: pd.DataFrame,
    test_size: float,
    seed: int,
    ae_epochs: int,
    anomaly_fraction: float,
) -> tuple[dict, dict, dict, dict, np.ndarray, np.ndarray]:
    """
    Train TCP and UDP autoencoders on benign-only data.
    Synthetic anomalies are injected ONLY into the validation and test sets.
    Returns (experts, calibrators, test_splits, metrics, X_all_proj, y_all).
    """
    protos = _split_by_proto(df6)

    proto_experts: dict = {}
    proto_calibrators: dict = {}
    proto_test: dict = {}
    all_metrics: dict = {}

    X_all_list, y_all_list = [], []

    for name, sub in protos.items():
        if len(sub) < 10:
            print(f"  [WARN] Proto {name} has only {len(sub)} rows — skipping")
            continue

        proj = project_6g(sub)
        y = sub["Label"].values.astype(int)  # all 0 (benign) at this point

        # Split: 80% train (benign only), 10% val + anomalies, 10% test + anomalies
        X_tr, X_tmp, y_tr, y_tmp = train_test_split(
            proj.values, y, test_size=test_size * 2, random_state=seed
        )
        X_val, X_te, y_val, y_te = train_test_split(
            X_tmp, y_tmp, test_size=0.5, random_state=seed
        )

        # Inject anomalies into val and test — NOT into train
        X_val_aug, y_val_aug = inject_unified_anomalies(
            X_val.astype(np.float32), y_val, anomaly_fraction=anomaly_fraction, seed=seed
        )
        X_te_aug, y_te_aug = inject_unified_anomalies(
            X_te.astype(np.float32), y_te, anomaly_fraction=anomaly_fraction, seed=seed + 1
        )

        ae = train_protocol_autoencoder(
            X_tr.astype(np.float32), name=name, epochs=ae_epochs
        )
        proto_experts[name] = ae

        # Calibration: MSE sigmoid on val augmented set
        recon_val = ae.predict(X_val_aug.astype(np.float32), verbose=0)
        mse_val = np.mean((X_val_aug - recon_val) ** 2, axis=1)
        cal = fit_mse_sigmoid(mse_val, y_val_aug)
        proto_calibrators[name] = cal

        # Test metrics
        recon_te = ae.predict(X_te_aug.astype(np.float32), verbose=0)
        mse_te = np.mean((X_te_aug - recon_te) ** 2, axis=1)
        from moe_ids.calibration import calibrate
        cal_te = calibrate(cal, mse_te)
        all_metrics[name] = _metrics(y_te_aug, cal_te, f"6G/{name}")
        proto_test[name] = (X_te_aug, y_te_aug)

        X_all_list.append(proj.values)
        y_all_list.append(y)

    X_all = np.vstack(X_all_list).astype(np.float32)
    y_all = np.concatenate(y_all_list).astype(int)

    return proto_experts, proto_calibrators, proto_test, all_metrics, X_all, y_all


# ── Gate pipeline ─────────────────────────────────────────────────────────

def train_gate(
    X_combined: np.ndarray,
    y_combined: np.ndarray,
    scaler: StandardScaler,
    slice_experts: dict,
    slice_calibrators: dict,
    proto_experts: dict,
    proto_calibrators: dict,
    seed: int,
    gate_epochs: int,
    test_size: float,
    anomaly_fraction: float,
) -> tuple:
    """Train the gating network on combined 5G+6G data."""
    from moe_ids.calibration import calibrate

    # Scale the combined features
    X_scaled = scaler.transform(X_combined.astype(np.float32))

    # Inject anomalies into combined data for gate training
    X_aug, y_aug = inject_unified_anomalies(
        X_scaled.astype(np.float32), y_combined.copy(), anomaly_fraction=anomaly_fraction, seed=seed
    )

    X_tr, X_te, y_tr, y_te = train_test_split(
        X_aug, y_aug, test_size=test_size, random_state=seed,
        stratify=y_aug if y_aug.sum() > 0 else None
    )
    X_tr2, X_val, y_tr2, y_val = train_test_split(
        X_tr, y_tr, test_size=0.15, random_state=seed,
        stratify=y_tr if y_tr.sum() > 0 else None
    )

    def _all_expert_scores(X: np.ndarray) -> np.ndarray:
        scores = np.zeros((len(X), N_EXPERTS), dtype=np.float32)
        for i, name in enumerate(("eMBB", "mMTC", "URLLC")):
            clf = slice_experts.get(name)
            if clf is None:
                continue
            raw = clf.predict_proba(X)[:, 1]
            cal = slice_calibrators.get(name)
            scores[:, i] = calibrate(cal, raw) if cal else raw.astype(np.float32)
        for j, name in enumerate(("TCP", "UDP"), start=3):
            ae = proto_experts.get(name)
            if ae is None:
                continue
            recon = ae.predict(X, verbose=0)
            mse = np.mean((X - recon) ** 2, axis=1)
            cal = proto_calibrators.get(name)
            scores[:, j] = calibrate(cal, mse) if cal else (
                ((mse - mse.min()) / (mse.max() - mse.min() + 1e-9)).astype(np.float32)
            )
        return scores

    S_tr = _all_expert_scores(X_tr2)
    S_val = _all_expert_scores(X_val)
    S_te = _all_expert_scores(X_te)

    gate = build_gate_model(X_tr2.shape[1])
    gate.fit(
        [X_tr2, S_tr], y_tr2,
        validation_data=([X_val, S_val], y_val),
        epochs=gate_epochs,
        batch_size=128,
        verbose=0,
        callbacks=[
            EarlyStopping(patience=10, restore_best_weights=True, monitor="val_loss"),
            ReduceLROnPlateau(patience=5, factor=0.5, min_lr=1e-5, monitor="val_loss"),
        ],
    )

    # Gate test metrics
    proba_te = gate.predict([X_te, S_te], verbose=0).ravel()
    gate_metrics = _metrics(y_te, proba_te, "MoE Gate (global)")

    return gate, gate_metrics


# ── Main ──────────────────────────────────────────────────────────────────

def _git_commit() -> str:
    """Return the current git commit SHA (short), or 'unknown'."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _run_training(args: argparse.Namespace) -> dict:
    """Core training logic — called inside or outside an MLflow run context."""
    np.random.seed(args.seed)
    tf.random.set_seed(args.seed)

    print(f"\n=== Training Unified MoE IDS  (seed={args.seed}) ===\n")

    # ── 5G ──
    print("[1/4] Loading and projecting 5G data...")
    df5 = _load_5g(args.data_5g)
    print(f"  {len(df5):,} rows | Label distribution: {dict(pd.Series(df5['Label']).value_counts())}")

    print("[2/4] Training 5G slice experts...")
    (
        slice_experts, slice_calibrators, _slice_test, metrics_5g,
        X_5g_proj, y_5g,
    ) = train_5g(df5, args.test_size, args.seed, args.xgb_n_estimators)

    print("\n  Per-expert baseline (calibrated, test set):")
    for m in metrics_5g.values():
        _print_metrics(m)

    # ── 6G ──
    print("\n[2/4] Loading and projecting 6G data...")
    df6 = _load_6g(args.data_6g)
    print(f"  {len(df6):,} rows (all benign — anomalies injected at val/test only)")

    print("[3/4] Training 6G protocol autoencoders...")
    (
        proto_experts, proto_calibrators, _proto_test, metrics_6g,
        X_6g_proj, y_6g,
    ) = train_6g(df6, args.test_size, args.seed, args.ae_epochs, args.anomaly_fraction)

    print("\n  Per-expert baseline (calibrated, augmented test set):")
    for m in metrics_6g.values():
        _print_metrics(m)

    # ── Combined scaler + gate ──
    print("\n[4/4] Fitting unified scaler and training gate network...")
    X_combined = np.vstack([X_5g_proj, X_6g_proj]).astype(np.float32)
    y_combined = np.concatenate([y_5g, y_6g]).astype(int)

    scaler = StandardScaler()
    scaler.fit(X_combined)

    gate, gate_metrics = train_gate(
        X_combined, y_combined, scaler,
        slice_experts, slice_calibrators,
        proto_experts, proto_calibrators,
        seed=args.seed,
        gate_epochs=args.gate_epochs,
        test_size=args.test_size,
        anomaly_fraction=args.anomaly_fraction,
    )

    print("\n  Global MoE metrics (combined test set):")
    _print_metrics(gate_metrics)

    # ── Save artefacts ──
    artefacts = Artefacts(
        version=args.version,
        unified_scaler=scaler,
        slice_experts=slice_experts,
        proto_experts=proto_experts,
        slice_calibrators=slice_calibrators,
        proto_calibrators=proto_calibrators,
        gate_model=gate,
        manifest={"seed": args.seed, "expert_names": list(slice_experts) + list(proto_experts)},
    )
    out_dir = Path(args.artefacts_dir)
    save_all(artefacts, out_dir)

    # ── Save baseline stats for drift detection ──
    import json as _json
    baseline = {
        "version": args.version,
        "seed": args.seed,
        "moe_f1": gate_metrics["f1"],
        "moe_recall": gate_metrics["recall"],
        "moe_pr_auc": gate_metrics["pr_auc"],
        "attack_rate_train": float(y_combined.mean()),
        "n_train_rows": int(len(y_combined)),
    }
    with open(out_dir / "baseline_stats.json", "w") as _f:
        _json.dump(baseline, _f, indent=2)

    print(f"\n✓ All artefacts saved to '{out_dir}/'")

    return {**metrics_5g, **metrics_6g, "MoE": gate_metrics}


def main() -> None:
    args = parse_args()

    if args.no_mlflow:
        _run_training(args)
        return

    # ── MLflow-instrumented path ──────────────────────────────────────────
    try:
        mlc.configure(args.mlflow_tracking_uri, args.experiment)
    except Exception as e:
        print(f"[WARN] Could not connect to MLflow at {args.mlflow_tracking_uri}: {e}")
        print("[WARN] Falling back to offline training (no MLflow logging).")
        _run_training(args)
        return

    commit = _git_commit()
    params = {
        "seed": args.seed,
        "version": args.version,
        "xgb_n_estimators": args.xgb_n_estimators,
        "ae_epochs": args.ae_epochs,
        "gate_epochs": args.gate_epochs,
        "test_size": args.test_size,
        "anomaly_fraction": args.anomaly_fraction,
        "git_commit": commit,
        "data_5g": args.data_5g,
        "data_6g": args.data_6g,
    }

    with mlc.start_run(
        run_name=f"moe-{args.version}-{commit}",
        tags={"git_commit": commit, "model_version": args.version},
    ) as run:
        mlc.log_params(params)
        all_metrics = _run_training(args)

        # Log per-expert and global metrics
        flat_metrics: dict[str, float] = {}
        for key, m in all_metrics.items():
            prefix = key.replace("/", "_").replace(" ", "_").lower()
            flat_metrics[f"{prefix}_f1"] = m["f1"]
            flat_metrics[f"{prefix}_recall"] = m["recall"]
            flat_metrics[f"{prefix}_precision"] = m["precision"]
            flat_metrics[f"{prefix}_auc_roc"] = m["auc_roc"]
            flat_metrics[f"{prefix}_pr_auc"] = m["pr_auc"]

        # Top-level gate metrics used by promote.py
        gate = all_metrics["MoE"]
        flat_metrics["moe_f1"] = gate["f1"]
        flat_metrics["moe_recall"] = gate["recall"]
        flat_metrics["moe_pr_auc"] = gate["pr_auc"]
        flat_metrics["moe_auc_roc"] = gate["auc_roc"]

        mlc.log_metrics(flat_metrics)
        mlc.log_artefacts(Path(args.artefacts_dir))

        # Register model in the Model Registry
        try:
            mv = mlc.register_model(run.info.run_id)
            print(f"\n✓ Registered as 'unified_moe' version {mv.version} in MLflow")
            print(f"  Run ID : {run.info.run_id}")
            print(f"  UI     : {args.mlflow_tracking_uri}/#/runs/{run.info.run_id}")
        except Exception as e:
            print(f"[WARN] Model registration failed (MLflow registry may not be configured): {e}")


if __name__ == "__main__":
    main()
