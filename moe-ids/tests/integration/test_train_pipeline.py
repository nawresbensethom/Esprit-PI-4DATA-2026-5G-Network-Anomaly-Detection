"""
Integration test: runs the full training pipeline on tiny fixture CSVs
and asserts all nine artefacts are saved and loadable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
ROOT = Path(__file__).parent.parent.parent

EXPECTED_ARTEFACTS = [
    "unified_scaler.pkl",
    "slice_expert_eMBB.pkl",
    "slice_expert_mMTC.pkl",
    "slice_expert_URLLC.pkl",
    "slice_calibrator_eMBB.pkl",
    "slice_calibrator_mMTC.pkl",
    "slice_calibrator_URLLC.pkl",
    "proto_expert_TCP.keras",
    "proto_expert_UDP.keras",
    "proto_calibrator_TCP.pkl",
    "proto_calibrator_UDP.pkl",
    "gate_model.keras",
    "manifest.pkl",
    "baseline_stats.json",
]


@pytest.fixture(scope="module")
def trained_artefacts_dir(tmp_path_factory):
    """Run training on fixture CSVs; return the artefacts directory."""
    out_dir = tmp_path_factory.mktemp("artefacts")

    # Generate minimal training CSVs (100 rows from real data with synthetic labels)
    import numpy as np
    import pandas as pd

    df5 = pd.read_csv(FIXTURES / "sample_5g_10rows.csv")
    # Replicate to get 100 rows with balanced labels independent of slice membership
    df5 = pd.concat([df5] * 10, ignore_index=True)
    rng = np.random.RandomState(0)
    df5["Label"] = rng.choice([0, 1], size=100, p=[0.5, 0.5])
    # Slice indicators: each row belongs to exactly one slice
    df5["slice_2:mMTC"] = np.tile([0, 0, 0, 1, 0, 0, 0, 1, 0, 0], 10)
    df5["slice_3:URLLC"] = np.tile([0, 0, 1, 0, 0, 0, 1, 0, 0, 0], 10)
    csv5 = out_dir / "train_5g.csv"
    df5.to_csv(csv5, index=False)

    df6 = pd.read_csv(FIXTURES / "sample_6g_10rows.csv")
    df6 = pd.concat([df6] * 10, ignore_index=True)
    df6["Label"] = "Benign"
    # Ensure both TCP and UDP rows exist so both proto experts are trained
    df6.loc[df6.index % 2 == 0, "Proto_TCP"] = 0
    csv6 = out_dir / "train_6g.csv"
    df6.to_csv(csv6, index=False)

    art_dir = out_dir / "artefacts"

    import os

    env = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "train.py"),
            "--data-5g",
            str(csv5),
            "--data-6g",
            str(csv6),
            "--artefacts-dir",
            str(art_dir),
            "--seed",
            "42",
            "--ae-epochs",
            "3",
            "--gate-epochs",
            "3",
            "--xgb-n-estimators",
            "10",
            "--no-mlflow",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    assert result.returncode == 0, f"train.py failed:\n{result.stderr}"
    return art_dir


def test_all_artefacts_exist(trained_artefacts_dir: Path) -> None:
    for name in EXPECTED_ARTEFACTS:
        path = trained_artefacts_dir / name
        assert path.exists(), f"Missing artefact: {name}"


def test_artefacts_loadable(trained_artefacts_dir: Path) -> None:
    from moe_ids.moe import MoEPredictor

    predictor = MoEPredictor.from_artefacts(trained_artefacts_dir)
    assert predictor._a.version is not None


def test_loaded_predictor_can_predict(trained_artefacts_dir: Path) -> None:
    import pandas as pd

    from moe_ids.moe import MoEPredictor

    predictor = MoEPredictor.from_artefacts(trained_artefacts_dir)
    df5 = pd.read_csv(FIXTURES / "sample_5g_10rows.csv")
    result = predictor.predict(df5)
    assert len(result.predictions) == len(df5)
    assert set(result.predictions).issubset({0, 1})
