import numpy as np

from moe_ids.injection import inject_unified_anomalies
from moe_ids.projection import UNIFIED_FEATURES


def _make_benign(n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.RandomState(0)
    X = rng.rand(n, len(UNIFIED_FEATURES)).astype(np.float32)
    y = np.zeros(n, dtype=int)
    return X, y


def test_output_shape() -> None:
    X, y = _make_benign(200)
    X_out, y_out = inject_unified_anomalies(X, y)
    assert X_out.shape == X.shape
    assert y_out.shape == y.shape


def test_anomaly_fraction() -> None:
    X, y = _make_benign(200)
    X_out, y_out = inject_unified_anomalies(X, y, anomaly_fraction=0.20)
    injected = y_out.sum()
    # Allow ±5 rows tolerance
    assert abs(injected - 40) <= 5


def test_original_unchanged() -> None:
    X, y = _make_benign(100)
    X_orig = X.copy()
    y_orig = y.copy()
    inject_unified_anomalies(X, y)
    np.testing.assert_array_equal(X, X_orig)
    np.testing.assert_array_equal(y, y_orig)


def test_deterministic_with_same_seed() -> None:
    X, y = _make_benign(100)
    _, y1 = inject_unified_anomalies(X, y, seed=7)
    _, y2 = inject_unified_anomalies(X, y, seed=7)
    np.testing.assert_array_equal(y1, y2)


def test_zero_fraction_noop() -> None:
    X, y = _make_benign(50)
    X_out, y_out = inject_unified_anomalies(X, y, anomaly_fraction=0.0)
    np.testing.assert_array_equal(y_out, y)
