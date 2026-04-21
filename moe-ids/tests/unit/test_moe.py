"""
End-to-end MoEPredictor roundtrip test using a tiny in-memory model.
Does NOT require saved artefacts — builds minimal stubs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from moe_ids.artefacts import Artefacts
from moe_ids.gate import N_EXPERTS, build_gate_model
from moe_ids.moe import MoEPredictor
from moe_ids.projection import UNIFIED_FEATURES


def _stub_artefacts() -> Artefacts:
    from xgboost import XGBClassifier

    n, d = 50, len(UNIFIED_FEATURES)
    rng = np.random.RandomState(0)
    X = rng.rand(n, d).astype(np.float32)
    y = (rng.rand(n) > 0.5).astype(int)

    scaler = StandardScaler()
    scaler.fit(X)
    X_sc = scaler.transform(X).astype(np.float32)

    slice_experts, slice_calibrators = {}, {}
    for name in ("eMBB", "mMTC", "URLLC"):
        clf = XGBClassifier(n_estimators=5, max_depth=2, use_label_encoder=False, eval_metric="logloss")
        clf.fit(X_sc, y)
        raw = clf.predict_proba(X_sc)[:, 1]
        cal = LogisticRegression(max_iter=100).fit(raw.reshape(-1, 1), y)
        slice_experts[name] = clf
        slice_calibrators[name] = cal

    from moe_ids.experts import build_autoencoder
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
    S = np.random.rand(n, N_EXPERTS).astype(np.float32)
    gate.fit([X_sc, S], y, epochs=2, verbose=0)

    return Artefacts(
        version="test",
        unified_scaler=scaler,
        slice_experts=slice_experts,
        proto_experts=proto_experts,
        slice_calibrators=slice_calibrators,
        proto_calibrators=proto_calibrators,
        gate_model=gate,
    )


@pytest.fixture(scope="module")
def predictor() -> MoEPredictor:
    return MoEPredictor(_stub_artefacts())


def test_predict_5g_returns_result(predictor: MoEPredictor, df_5g: pd.DataFrame) -> None:
    result = predictor.predict(df_5g)
    assert result.schema == "argus"
    assert len(result.predictions) == len(df_5g)
    assert len(result.probabilities) == len(df_5g)


def test_predict_6g_returns_result(predictor: MoEPredictor, df_6g: pd.DataFrame) -> None:
    result = predictor.predict(df_6g)
    assert result.schema == "cic"
    assert len(result.predictions) == len(df_6g)


def test_predictions_are_binary(predictor: MoEPredictor, df_5g: pd.DataFrame) -> None:
    result = predictor.predict(df_5g)
    assert set(result.predictions).issubset({0, 1})


def test_probabilities_in_01(predictor: MoEPredictor, df_5g: pd.DataFrame) -> None:
    result = predictor.predict(df_5g)
    assert (result.probabilities >= 0).all() and (result.probabilities <= 1).all()


def test_gate_weights_shape(predictor: MoEPredictor, df_5g: pd.DataFrame) -> None:
    result = predictor.predict(df_5g)
    assert result.gate_weights.shape == (len(df_5g), N_EXPERTS)


def test_model_version_propagated(predictor: MoEPredictor, df_5g: pd.DataFrame) -> None:
    result = predictor.predict(df_5g)
    assert result.model_version == "test"
