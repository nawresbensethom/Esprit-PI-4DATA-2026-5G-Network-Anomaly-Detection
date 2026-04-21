"""
MoEPredictor — the single public inference orchestrator.
Ties together: schema detection → projection → scaling → expert scoring
→ calibration → gating → final probability → threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from moe_ids.artefacts import Artefacts, load_all
from moe_ids.calibration import calibrate
from moe_ids.gate import N_EXPERTS
from moe_ids.projection import project_5g, project_6g
from moe_ids.schemas import SchemaError, detect_schema


@dataclass
class PredictionResult:
    predictions: np.ndarray      # (n,) int
    probabilities: np.ndarray    # (n,) float32
    gate_weights: np.ndarray     # (n, 5) float32
    expert_scores: np.ndarray    # (n, 5) float32
    schema: str
    model_version: str


class MoEPredictor:
    def __init__(self, artefacts: Artefacts) -> None:
        self._a = artefacts
        self._threshold: float = 0.5
        # Sub-model that outputs only gate weights (same graph, different output)
        self._gate_weights_model = self._build_weights_extractor()

    @classmethod
    def from_artefacts(cls, artefacts_dir: Path) -> "MoEPredictor":
        return cls(load_all(artefacts_dir))

    def set_threshold(self, threshold: float) -> None:
        self._threshold = threshold

    # ── Internal helpers ──────────────────────────────────────────────────

    def _build_weights_extractor(self):
        """Return a sub-model that outputs gate weights instead of final probability."""
        import tensorflow as tf
        gate = self._a.gate_model
        weights_layer = gate.get_layer("gate_weights")
        return tf.keras.Model(
            inputs=gate.input[0],  # only the feature input
            outputs=weights_layer.output,
            name="gate_weights_extractor",
        )

    def _score_slice(self, name: str, X: np.ndarray) -> np.ndarray:
        clf = self._a.slice_experts.get(name)
        if clf is None:
            return np.zeros(len(X), dtype=np.float32)
        raw = clf.predict_proba(X)[:, 1]
        cal = self._a.slice_calibrators.get(name)
        return calibrate(cal, raw) if cal is not None else raw.astype(np.float32)

    def _score_proto(self, name: str, X: np.ndarray) -> np.ndarray:
        ae = self._a.proto_experts.get(name)
        if ae is None:
            return np.zeros(len(X), dtype=np.float32)
        recon = ae.predict(X, verbose=0)
        mse = np.mean((X - recon) ** 2, axis=1)
        cal = self._a.proto_calibrators.get(name)
        if cal is not None:
            return calibrate(cal, mse)
        # Fallback: min-max normalise
        lo, hi = mse.min(), mse.max()
        return ((mse - lo) / (hi - lo + 1e-9)).astype(np.float32)

    def _compute_expert_scores(self, X: np.ndarray) -> np.ndarray:
        scores = np.zeros((len(X), N_EXPERTS), dtype=np.float32)
        scores[:, 0] = self._score_slice("eMBB", X)
        scores[:, 1] = self._score_slice("mMTC", X)
        scores[:, 2] = self._score_slice("URLLC", X)
        scores[:, 3] = self._score_proto("TCP", X)
        scores[:, 4] = self._score_proto("UDP", X)
        return scores

    # ── Public API ────────────────────────────────────────────────────────

    def predict(
        self,
        df_raw: pd.DataFrame,
        threshold: float | None = None,
    ) -> PredictionResult:
        """
        Full inference pipeline: project → scale → expert score → gate → threshold.
        """
        schema = detect_schema(df_raw)
        if schema == "unknown":
            raise SchemaError(
                f"Cannot predict: unrecognised schema. "
                f"Detected columns (first 10): {list(df_raw.columns[:10])}"
            )

        if schema == "argus":
            projected = project_5g(df_raw)
        else:
            projected = project_6g(df_raw)

        X = self._a.unified_scaler.transform(projected.values.astype(np.float32))
        expert_scores = self._compute_expert_scores(X)

        proba = self._a.gate_model.predict(
            [X, expert_scores], verbose=0
        ).ravel().astype(np.float32)

        gate_weights = self._gate_weights_model.predict(X, verbose=0).astype(np.float32)

        thr = threshold if threshold is not None else self._threshold
        predictions = (proba >= thr).astype(int)

        return PredictionResult(
            predictions=predictions,
            probabilities=proba,
            gate_weights=gate_weights,
            expert_scores=expert_scores,
            schema=schema,
            model_version=self._a.version,
        )
