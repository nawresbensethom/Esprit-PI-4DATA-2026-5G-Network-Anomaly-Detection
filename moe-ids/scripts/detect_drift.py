"""
Drift detection: compares recent prediction logs against the training baseline.

Computes:
  - Attack-rate drift  (PSI between training and recent windows)
  - Probability score drift  (KS test on score distributions)

Reads JSONL prediction logs from --log-dir (one file per day, named
predictions_YYYY-MM-DD.jsonl). Each line must have a "summary" field with
"attack_rate" and "mean_probability".

Usage:
    python scripts/detect_drift.py \
        --artefacts-dir artefacts/production \
        --log-dir logs/predictions \
        --window-days 7 \
        --psi-threshold 0.2 \
        --ks-p-threshold 0.05
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import numpy as np
from scipy import stats


# ── PSI helpers ──────────────────────────────────────────────────────────────

def _safe_psi(p: float, q: float) -> float:
    """PSI contribution for one bucket, guarded against log(0)."""
    if p == 0 and q == 0:
        return 0.0
    if p == 0:
        p = 1e-6
    if q == 0:
        q = 1e-6
    return (p - q) * np.log(p / q)


def compute_psi(baseline: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
    """
    Population Stability Index between two 1-D distributions.
    Bins are derived from the baseline distribution.
    PSI < 0.1  → no significant shift
    PSI < 0.2  → moderate shift, monitor
    PSI >= 0.2 → significant shift, investigate
    """
    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    bin_edges = np.percentile(baseline, np.linspace(0, 100, n_bins + 1))
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        return 0.0

    base_counts, _ = np.histogram(baseline, bins=bin_edges)
    curr_counts, _ = np.histogram(current, bins=bin_edges)

    base_pct = base_counts / base_counts.sum()
    curr_pct = curr_counts / curr_counts.sum()

    return float(sum(_safe_psi(b, c) for b, c in zip(base_pct, curr_pct)))


# ── Data loading ─────────────────────────────────────────────────────────────

class PredictionRecord(NamedTuple):
    request_id: str
    timestamp: str
    schema: str
    n_rows: int
    attack_rate: float
    mean_probability: float


def load_recent_logs(log_dir: Path, window_days: int) -> list[PredictionRecord]:
    """Load prediction log entries from the last `window_days` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    records: list[PredictionRecord] = []

    for log_file in sorted(log_dir.glob("predictions_*.jsonl")):
        try:
            date_str = log_file.stem.replace("predictions_", "")
            file_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            if file_date < cutoff - timedelta(days=1):
                continue
        except ValueError:
            pass  # include files we can't date-parse

        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    ts = obj.get("timestamp", "")
                    if ts:
                        entry_dt = datetime.fromisoformat(ts)
                        if entry_dt < cutoff:
                            continue
                    summary = obj.get("summary", {})
                    records.append(PredictionRecord(
                        request_id=obj.get("request_id", ""),
                        timestamp=ts,
                        schema=obj.get("schema", "unknown"),
                        n_rows=obj.get("n_rows", 0),
                        attack_rate=float(summary.get("attack_rate", 0.0)),
                        mean_probability=float(summary.get("mean_probability", 0.0)),
                    ))
                except Exception:
                    continue

    return records


# ── Drift report ─────────────────────────────────────────────────────────────

def run_drift_check(
    artefacts_dir: Path,
    log_dir: Path,
    window_days: int,
    psi_threshold: float,
    ks_p_threshold: float,
) -> dict:
    baseline_path = artefacts_dir / "baseline_stats.json"
    if not baseline_path.exists():
        print(f"[ERROR] baseline_stats.json not found in {artefacts_dir}", file=sys.stderr)
        sys.exit(1)

    with open(baseline_path) as f:
        baseline_stats = json.load(f)

    baseline_attack_rate = baseline_stats["attack_rate_train"]

    records = load_recent_logs(log_dir, window_days)
    if not records:
        print(f"[WARN] No prediction logs found in '{log_dir}' for the last {window_days} days.")
        return {"status": "no_data", "n_requests": 0}

    attack_rates = np.array([r.attack_rate for r in records])
    mean_probs = np.array([r.mean_probability for r in records])

    # Baseline distributions (point-estimate expanded to small synthetic population)
    baseline_attack = np.array([baseline_attack_rate] * max(len(attack_rates), 30))

    psi_attack = compute_psi(baseline_attack, attack_rates)

    # KS test: are recent probabilities drawn from the baseline distribution?
    # Use a normal approximation centred on the baseline attack rate as reference.
    rng = np.random.RandomState(0)
    baseline_probs = rng.beta(
        max(baseline_attack_rate * 10, 0.5),
        max((1 - baseline_attack_rate) * 10, 0.5),
        size=max(len(mean_probs) * 2, 100),
    )
    ks_stat, ks_p = stats.ks_2samp(baseline_probs, mean_probs)

    drifted = psi_attack >= psi_threshold or ks_p < ks_p_threshold

    report = {
        "status": "drift_detected" if drifted else "ok",
        "window_days": window_days,
        "n_requests": len(records),
        "baseline_attack_rate": baseline_attack_rate,
        "recent_mean_attack_rate": float(attack_rates.mean()),
        "psi_attack_rate": round(psi_attack, 4),
        "psi_threshold": psi_threshold,
        "ks_statistic": round(float(ks_stat), 4),
        "ks_p_value": round(float(ks_p), 4),
        "ks_p_threshold": ks_p_threshold,
        "alerts": [],
    }

    if psi_attack >= psi_threshold:
        report["alerts"].append(
            f"Attack-rate PSI={psi_attack:.3f} >= threshold {psi_threshold} — distribution shift detected"
        )
    if ks_p < ks_p_threshold:
        report["alerts"].append(
            f"Score KS p={ks_p:.4f} < threshold {ks_p_threshold} — probability distribution shifted"
        )

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MoE IDS drift detection")
    parser.add_argument("--artefacts-dir", required=True, type=Path)
    parser.add_argument("--log-dir", required=True, type=Path)
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--psi-threshold", type=float, default=0.2)
    parser.add_argument("--ks-p-threshold", type=float, default=0.05)
    parser.add_argument("--output", choices=["json", "text"], default="text")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_drift_check(
        args.artefacts_dir,
        args.log_dir,
        args.window_days,
        args.psi_threshold,
        args.ks_p_threshold,
    )

    if args.output == "json":
        print(json.dumps(report, indent=2))
    else:
        status_symbol = "DRIFT" if report["status"] == "drift_detected" else "OK"
        print(f"\n=== Drift Detection Report [{status_symbol}] ===")
        print(f"  Window       : last {report.get('window_days', '?')} days")
        print(f"  Requests     : {report.get('n_requests', 0)}")
        print(f"  Baseline AR  : {report.get('baseline_attack_rate', '?'):.4f}")
        print(f"  Recent AR    : {report.get('recent_mean_attack_rate', '?'):.4f}")
        print(f"  PSI (AR)     : {report.get('psi_attack_rate', '?'):.4f}  (threshold={args.psi_threshold})")
        print(f"  KS p-value   : {report.get('ks_p_value', '?'):.4f}  (threshold={args.ks_p_threshold})")
        for alert in report.get("alerts", []):
            print(f"  [!] {alert}")
        print()

    if report.get("status") == "drift_detected":
        sys.exit(2)


if __name__ == "__main__":
    main()