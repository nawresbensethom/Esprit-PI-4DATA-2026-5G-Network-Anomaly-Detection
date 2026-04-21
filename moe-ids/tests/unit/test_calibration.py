import numpy as np
from sklearn.linear_model import LogisticRegression

from moe_ids.calibration import calibrate, fit_mse_sigmoid, fit_platt


def _synthetic(n: int = 200, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.RandomState(seed)
    y = (rng.rand(n) > 0.6).astype(int)
    raw = y * 0.6 + rng.rand(n) * 0.4
    return raw, y


def test_fit_platt_returns_lr() -> None:
    raw, y = _synthetic()
    cal = fit_platt(raw, y)
    assert isinstance(cal, LogisticRegression)


def test_fit_mse_sigmoid_returns_lr() -> None:
    raw, y = _synthetic()
    cal = fit_mse_sigmoid(raw, y)
    assert isinstance(cal, LogisticRegression)


def test_calibrate_output_shape() -> None:
    raw, y = _synthetic()
    cal = fit_platt(raw, y)
    out = calibrate(cal, raw)
    assert out.shape == (len(raw),)


def test_calibrate_output_range() -> None:
    raw, y = _synthetic()
    cal = fit_platt(raw, y)
    out = calibrate(cal, raw)
    assert (out >= 0).all() and (out <= 1).all()
