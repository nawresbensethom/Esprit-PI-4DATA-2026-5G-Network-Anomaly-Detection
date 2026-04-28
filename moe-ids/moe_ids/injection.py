"""
Structured anomaly injection for the 6G one-class training pipeline.
Logic ported verbatim from Moe.ipynb — no changes.
"""

from __future__ import annotations

import numpy as np

from moe_ids.projection import UNIFIED_FEATURES

ATTACK_PROFILES: dict[str, dict] = {
    "SYN Flood": {
        "features": ["u_syn", "u_pkt_rate", "u_duration"],
        "multiplier": 8.0,
    },
    "Port Scan": {
        "features": ["u_rst", "u_duration", "u_pkt_ratio"],
        "multiplier": 6.0,
    },
    "DDoS Volume": {
        "features": ["u_byte_rate", "u_pkt_rate", "u_fwd_pkts"],
        "multiplier": 10.0,
    },
    "Data Exfiltration": {
        "features": ["u_bwd_mean_size", "u_byte_rate"],
        "multiplier": 5.0,
    },
}


def inject_unified_anomalies(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str] | None = None,
    anomaly_fraction: float = 0.15,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Perturb a random `anomaly_fraction` of rows with attack-type-specific Gaussian noise.
    X : (n, d) float32 array in the unified scaled space.
    y : (n,)  integer array of labels (0 = benign).
    Returns (X_out, y_out) — modified copies, originals unchanged.
    """
    if feature_names is None:
        feature_names = UNIFIED_FEATURES

    rng = np.random.RandomState(seed)
    X_out = X.copy()
    y_out = y.copy()
    n_anom = int(anomaly_fraction * len(X))
    if n_anom == 0:
        return X_out, y_out

    idx_to_attack = rng.choice(len(X), n_anom, replace=False)
    profile_names = list(ATTACK_PROFILES.keys())

    for row_idx in idx_to_attack:
        prof = ATTACK_PROFILES[profile_names[rng.randint(len(profile_names))]]
        feat_idx = [feature_names.index(f) for f in prof["features"] if f in feature_names]
        if not feat_idx:
            continue
        noise = rng.normal(0.0, prof["multiplier"], len(feat_idx)).astype(np.float32)
        X_out[row_idx, feat_idx] += noise
        y_out[row_idx] = 1

    return X_out, y_out
