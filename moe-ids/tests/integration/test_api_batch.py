"""
Integration tests for POST /predict/batch.
Uses httpx.AsyncClient against the ASGI app with a real (stub) predictor.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ── App fixture with a stub predictor ────────────────────────────────────


@pytest.fixture(scope="module")
def stub_predictor():
    """Build a tiny MoEPredictor without needing saved artefacts on disk."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier

    from moe_ids.artefacts import Artefacts
    from moe_ids.experts import build_autoencoder
    from moe_ids.gate import N_EXPERTS, build_gate_model
    from moe_ids.moe import MoEPredictor
    from moe_ids.projection import UNIFIED_FEATURES

    rng = np.random.RandomState(0)
    n, d = 60, len(UNIFIED_FEATURES)
    X = rng.rand(n, d).astype(np.float32)
    y = (rng.rand(n) > 0.5).astype(int)

    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X).astype(np.float32)

    slice_experts, slice_calibrators = {}, {}
    for name in ("eMBB", "mMTC", "URLLC"):
        clf = XGBClassifier(
            n_estimators=5, max_depth=2, use_label_encoder=False, eval_metric="logloss"
        )
        clf.fit(X_sc, y)
        raw = clf.predict_proba(X_sc)[:, 1]
        cal = LogisticRegression(max_iter=100).fit(raw.reshape(-1, 1), y)
        slice_experts[name] = clf
        slice_calibrators[name] = cal

    proto_experts, proto_calibrators = {}, {}
    for name in ("TCP", "UDP"):
        ae = build_autoencoder(d, bottleneck=4)
        ae.fit(X_sc, X_sc, epochs=2, verbose=0)
        recon = ae.predict(X_sc, verbose=0)
        mse = np.mean((X_sc - recon) ** 2, axis=1)
        cal = LogisticRegression(max_iter=100).fit(mse.reshape(-1, 1), y)
        proto_experts[name] = ae
        proto_calibrators[name] = cal

    gate = build_gate_model(d)
    S = rng.rand(n, N_EXPERTS).astype(np.float32)
    gate.fit([X_sc, S], y, epochs=2, verbose=0)

    return MoEPredictor(
        Artefacts(
            version="test",
            unified_scaler=scaler,
            slice_experts=slice_experts,
            proto_experts=proto_experts,
            slice_calibrators=slice_calibrators,
            proto_calibrators=proto_calibrators,
            gate_model=gate,
        )
    )


@pytest.fixture(scope="module")
def client(stub_predictor):
    """TestClient with the stub predictor injected."""
    import services.common.predictor as deps
    from services.inference.main import create_app

    app = create_app()

    # Override the lifespan model-load by patching the singleton directly
    with patch.object(deps, "_predictor", stub_predictor):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ── Helpers ───────────────────────────────────────────────────────────────


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


# ── Tests ─────────────────────────────────────────────────────────────────


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_version(client: TestClient) -> None:
    r = client.get("/version")
    assert r.status_code == 200
    assert "model_version" in r.json()


def test_batch_valid_5g(client: TestClient, stub_predictor) -> None:
    df = pd.read_csv(FIXTURES / "sample_5g_10rows.csv")
    r = client.post("/predict/batch", files={"file": ("test.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] == "argus"
    assert body["n_rows"] == len(df)
    assert len(body["predictions"]) == len(df)
    assert len(body["probabilities"]) == len(df)
    assert set(body["predictions"]).issubset({0, 1})
    assert len(body["expert_order"]) == 5


def test_batch_valid_6g(client: TestClient) -> None:
    df = pd.read_csv(FIXTURES / "sample_6g_10rows.csv")
    r = client.post("/predict/batch", files={"file": ("test.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] == "cic"
    assert body["n_rows"] == len(df)


def test_batch_unknown_schema(client: TestClient) -> None:
    df = pd.DataFrame({"col_a": [1, 2], "col_b": [3, 4]})
    r = client.post("/predict/batch", files={"file": ("test.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 400
    assert "unrecognised schema" in str(r.json())


def test_batch_malformed_csv(client: TestClient) -> None:
    bad_bytes = b"this is not a valid csv\x00\x01\x02\xff\xfe"
    r = client.post("/predict/batch", files={"file": ("test.csv", bad_bytes, "text/csv")})
    # pandas may parse some garbage; we expect either 400 (parse error) or 400 (unknown schema)
    assert r.status_code == 400


def test_batch_empty_csv(client: TestClient) -> None:
    r = client.post("/predict/batch", files={"file": ("test.csv", b"col_a,col_b\n", "text/csv")})
    assert r.status_code == 400


def test_batch_missing_file_field(client: TestClient) -> None:
    r = client.post("/predict/batch")
    assert r.status_code == 422


def test_batch_oversized_file(client: TestClient) -> None:
    # Fake a large content-length header
    big = b"a,b\n" + b"1,2\n" * 10
    r = client.post(
        "/predict/batch",
        files={"file": ("test.csv", big, "text/csv")},
        headers={"content-length": str(200 * 1024 * 1024)},  # claim 200 MB
    )
    assert r.status_code == 413


def test_batch_response_has_summary(client: TestClient) -> None:
    df = pd.read_csv(FIXTURES / "sample_5g_10rows.csv")
    r = client.post("/predict/batch", files={"file": ("test.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    summary = r.json()["summary"]
    assert "n_attack_predicted" in summary
    assert "mean_probability" in summary


def test_batch_probabilities_in_range(client: TestClient) -> None:
    df = pd.read_csv(FIXTURES / "sample_5g_10rows.csv")
    r = client.post("/predict/batch", files={"file": ("test.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    for p in r.json()["probabilities"]:
        assert 0.0 <= p <= 1.0
