"""Platt scaling and AE MSE sigmoid calibration."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def fit_platt(raw_proba: np.ndarray, y_true: np.ndarray) -> LogisticRegression:
    """Fit a Platt scaler (LogisticRegression on raw classifier probabilities)."""
    X = raw_proba.reshape(-1, 1)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X, y_true)
    return lr


def fit_mse_sigmoid(mse: np.ndarray, y_true: np.ndarray) -> LogisticRegression:
    """Fit a sigmoid calibrator mapping AE reconstruction MSE to P(attack)."""
    X = mse.reshape(-1, 1)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X, y_true)
    return lr


def calibrate(calibrator: LogisticRegression, raw_values: np.ndarray) -> np.ndarray:
    """Apply a fitted calibrator; returns P(attack) as a 1-D float32 array."""
    return calibrator.predict_proba(raw_values.reshape(-1, 1))[:, 1].astype(np.float32)
