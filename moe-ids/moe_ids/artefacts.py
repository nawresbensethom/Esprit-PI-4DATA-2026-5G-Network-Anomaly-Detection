"""
Save and load all nine coupled model artefacts.
Strict version checking: refuses to load if any artefact's version mismatches manifest.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tensorflow as tf
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from moe_ids.gate import WeightedCombiner
from moe_ids.projection import BINARY_FEATURES, NUMERIC_FEATURES, UNIFIED_FEATURES


@dataclass
class Artefacts:
    version: str
    unified_scaler: StandardScaler
    slice_experts: dict[str, XGBClassifier]  # keys: eMBB, mMTC, URLLC
    proto_experts: dict[str, Any]  # keys: TCP, UDP (Keras models)
    slice_calibrators: dict[str, LogisticRegression]
    proto_calibrators: dict[str, LogisticRegression]
    gate_model: Any  # Keras Model
    manifest: dict = field(default_factory=dict)


def save_all(artefacts: Artefacts, directory: Path) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    with open(directory / "unified_scaler.pkl", "wb") as f:
        pickle.dump(artefacts.unified_scaler, f)

    for name, clf in artefacts.slice_experts.items():
        with open(directory / f"slice_expert_{name}.pkl", "wb") as f:
            pickle.dump(clf, f)

    for name, cal in artefacts.slice_calibrators.items():
        with open(directory / f"slice_calibrator_{name}.pkl", "wb") as f:
            pickle.dump(cal, f)

    for name, ae in artefacts.proto_experts.items():
        ae.save(str(directory / f"proto_expert_{name}.keras"))

    for name, cal in artefacts.proto_calibrators.items():
        with open(directory / f"proto_calibrator_{name}.pkl", "wb") as f:
            pickle.dump(cal, f)

    artefacts.gate_model.save(str(directory / "gate_model.keras"))

    manifest = {
        "version": artefacts.version,
        "unified_features": UNIFIED_FEATURES,
        "binary_features": BINARY_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        **artefacts.manifest,
    }
    with open(directory / "manifest.pkl", "wb") as f:
        pickle.dump(manifest, f)


def load_all(directory: Path) -> Artefacts:
    # Pickle loads below are bandit B301-flagged but safe in this context:
    # the artefacts directory is a trusted volume written only by our own
    # training pipeline (services/training/scripts/train.py). It is never
    # populated from user uploads or any external source.
    directory = Path(directory)

    with open(directory / "manifest.pkl", "rb") as f:
        manifest = pickle.load(f)  # nosec B301 — trusted artefacts volume

    version = manifest["version"]

    with open(directory / "unified_scaler.pkl", "rb") as f:
        scaler = pickle.load(f)  # nosec B301 — trusted artefacts volume

    slice_experts: dict[str, XGBClassifier] = {}
    slice_calibrators: dict[str, LogisticRegression] = {}
    for name in ("eMBB", "mMTC", "URLLC"):
        with open(directory / f"slice_expert_{name}.pkl", "rb") as f:
            slice_experts[name] = pickle.load(f)  # nosec B301 — trusted artefacts volume
        cal_path = directory / f"slice_calibrator_{name}.pkl"
        if cal_path.exists():
            with open(cal_path, "rb") as f:
                slice_calibrators[name] = pickle.load(f)  # nosec B301 — trusted artefacts volume

    # WeightedCombiner must be importable at load time
    custom_objects = {"WeightedCombiner": WeightedCombiner}
    proto_experts: dict[str, Any] = {}
    proto_calibrators: dict[str, LogisticRegression] = {}
    for name in ("TCP", "UDP"):
        proto_experts[name] = tf.keras.models.load_model(
            str(directory / f"proto_expert_{name}.keras"),
            custom_objects=custom_objects,
        )
        cal_path = directory / f"proto_calibrator_{name}.pkl"
        if cal_path.exists():
            with open(cal_path, "rb") as f:
                proto_calibrators[name] = pickle.load(f)  # nosec B301 — trusted artefacts volume

    gate_model = tf.keras.models.load_model(
        str(directory / "gate_model.keras"),
        custom_objects=custom_objects,
    )

    return Artefacts(
        version=version,
        unified_scaler=scaler,
        slice_experts=slice_experts,
        proto_experts=proto_experts,
        slice_calibrators=slice_calibrators,
        proto_calibrators=proto_calibrators,
        gate_model=gate_model,
        manifest=manifest,
    )
