"""
Unit tests for scripts/detect_drift.py drift detection logic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from detect_drift import compute_psi, load_recent_logs, run_drift_check


# ── PSI tests ────────────────────────────────────────────────────────────────

def test_psi_identical_distributions():
    rng = np.random.RandomState(0)
    x = rng.beta(2, 5, size=500)
    assert compute_psi(x, x) < 0.05


def test_psi_very_different_distributions():
    rng = np.random.RandomState(0)
    baseline = rng.beta(2, 8, size=500)   # skewed low
    current = rng.beta(8, 2, size=500)    # skewed high
    assert compute_psi(baseline, current) > 0.2


def test_psi_empty_arrays():
    assert compute_psi(np.array([]), np.array([])) == 0.0
    assert compute_psi(np.array([0.5]), np.array([])) == 0.0


def test_psi_near_identical_distributions():
    # Two samples from the same distribution — PSI should be small
    rng = np.random.RandomState(42)
    baseline = rng.beta(2, 5, size=1000)
    current = rng.beta(2, 5, size=1000)
    psi = compute_psi(baseline, current)
    assert 0.0 <= psi < 0.15


# ── Log loading tests ─────────────────────────────────────────────────────────

def _write_log(log_dir: Path, filename: str, records: list[dict]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / filename, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_load_recent_logs_returns_records(tmp_path):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    record = {
        "request_id": "abc",
        "timestamp": now.isoformat(),
        "schema": "argus",
        "n_rows": 10,
        "summary": {"attack_rate": 0.3, "mean_probability": 0.4},
    }
    _write_log(tmp_path, f"predictions_{now.strftime('%Y-%m-%d')}.jsonl", [record])
    records = load_recent_logs(tmp_path, window_days=7)
    assert len(records) == 1
    assert records[0].attack_rate == pytest.approx(0.3)


def test_load_recent_logs_empty_dir(tmp_path):
    records = load_recent_logs(tmp_path, window_days=7)
    assert records == []


def test_load_recent_logs_skips_malformed_lines(tmp_path):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    log_dir = tmp_path
    log_dir.mkdir(parents=True, exist_ok=True)
    fname = f"predictions_{now.strftime('%Y-%m-%d')}.jsonl"
    with open(log_dir / fname, "w") as f:
        f.write("not json at all\n")
        f.write(json.dumps({
            "request_id": "ok",
            "timestamp": now.isoformat(),
            "schema": "cic",
            "n_rows": 5,
            "summary": {"attack_rate": 0.1, "mean_probability": 0.2},
        }) + "\n")
    records = load_recent_logs(log_dir, window_days=7)
    assert len(records) == 1


# ── Full drift check tests ────────────────────────────────────────────────────

def _write_baseline(artefacts_dir: Path, attack_rate: float = 0.05) -> None:
    artefacts_dir.mkdir(parents=True, exist_ok=True)
    stats = {
        "version": "test",
        "seed": 42,
        "moe_f1": 0.91,
        "moe_recall": 0.95,
        "moe_pr_auc": 0.93,
        "attack_rate_train": attack_rate,
        "n_train_rows": 10000,
    }
    with open(artefacts_dir / "baseline_stats.json", "w") as f:
        json.dump(stats, f)


def test_no_drift_when_attack_rates_match(tmp_path):
    from datetime import datetime, timezone

    art_dir = tmp_path / "artefacts"
    log_dir = tmp_path / "logs"
    baseline_ar = 0.10
    _write_baseline(art_dir, attack_rate=baseline_ar)

    now = datetime.now(timezone.utc)
    # Vary attack_rate and mean_probability around the baseline so neither
    # PSI nor KS detects a shift
    rng = np.random.RandomState(7)
    attack_rates = np.clip(rng.normal(baseline_ar, 0.01, size=50), 0.0, 1.0)
    mean_probs = np.clip(rng.beta(1.0, 9.0, size=50), 1e-6, 1 - 1e-6)
    records = [
        {
            "request_id": str(i),
            "timestamp": now.isoformat(),
            "schema": "argus",
            "n_rows": 100,
            "summary": {"attack_rate": float(attack_rates[i]), "mean_probability": float(mean_probs[i])},
        }
        for i in range(50)
    ]
    _write_log(log_dir, f"predictions_{now.strftime('%Y-%m-%d')}.jsonl", records)

    report = run_drift_check(art_dir, log_dir, window_days=7, psi_threshold=0.2, ks_p_threshold=0.05)
    assert report["status"] == "ok"
    assert report["n_requests"] == 50


def test_drift_detected_when_attack_rate_spikes(tmp_path):
    from datetime import datetime, timezone

    art_dir = tmp_path / "artefacts"
    log_dir = tmp_path / "logs"
    _write_baseline(art_dir, attack_rate=0.05)

    now = datetime.now(timezone.utc)
    # All recent batches show 80% attack rate — massive shift
    records = [
        {
            "request_id": str(i),
            "timestamp": now.isoformat(),
            "schema": "argus",
            "n_rows": 100,
            "summary": {"attack_rate": 0.80, "mean_probability": 0.85},
        }
        for i in range(50)
    ]
    _write_log(log_dir, f"predictions_{now.strftime('%Y-%m-%d')}.jsonl", records)

    report = run_drift_check(art_dir, log_dir, window_days=7, psi_threshold=0.2, ks_p_threshold=0.05)
    assert report["status"] == "drift_detected"
    assert len(report["alerts"]) >= 1


def test_no_data_returns_no_data_status(tmp_path):
    art_dir = tmp_path / "artefacts"
    log_dir = tmp_path / "logs"
    _write_baseline(art_dir)
    log_dir.mkdir()

    report = run_drift_check(art_dir, log_dir, window_days=7, psi_threshold=0.2, ks_p_threshold=0.05)
    assert report["status"] == "no_data"