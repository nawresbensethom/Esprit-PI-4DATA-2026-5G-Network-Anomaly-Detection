"""
Load a saved model and compute evaluation metrics on test data.

Usage:
    python scripts/evaluate.py \\
        --artefacts-dir artefacts \\
        --data-5g ../MoE/Global_CLEANED.csv \\
        --data-6g ../MoE/AIoT_6G_CLEANED.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report

from moe_ids.injection import inject_unified_anomalies
from moe_ids.moe import MoEPredictor
from moe_ids.projection import project_6g


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--artefacts-dir", default="artefacts")
    p.add_argument("--data-5g", default="../MoE/Global_CLEANED.csv")
    p.add_argument("--data-6g", default="../MoE/AIoT_6G_CLEANED.csv")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    predictor = MoEPredictor.from_artefacts(Path(args.artefacts_dir))
    print(f"Model version: {predictor._a.version}")

    # 5G evaluation
    df5 = pd.read_csv(args.data_5g)
    df5["Label"] = df5["Label"].astype(int)
    result5 = predictor.predict(df5)
    print("\n5G predictions:")
    print(classification_report(df5["Label"].values, result5.predictions))

    # 6G evaluation (inject anomalies for test)
    df6 = pd.read_csv(args.data_6g)
    df6["Label"] = (df6["Label"].str.lower() != "benign").astype(int)
    proj6 = project_6g(df6)
    X6_scaled = predictor._a.unified_scaler.transform(proj6.values.astype(np.float32))
    X6_aug, y6_aug = inject_unified_anomalies(
        X6_scaled, df6["Label"].values, anomaly_fraction=0.15, seed=args.seed
    )
    # Reconstruct dataframe in unified space (already scaled) for direct predict bypass
    result6 = predictor.predict(df6)
    print("\n6G predictions (benign-only source, no injected anomalies in CSV):")
    print(classification_report(df6["Label"].values, result6.predictions))


if __name__ == "__main__":
    main()
