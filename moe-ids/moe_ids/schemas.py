from __future__ import annotations

from typing import Literal

import pandas as pd


class SchemaError(ValueError):
    pass


# Signature columns used to fingerprint each schema.
# Matching rule: at least 80% of these must be present.
ARGUS_SIGNATURE_COLUMNS: list[str] = [
    "Dur",
    "TotPkts_log",
    "SrcPkts_log",
    "Load_log",
    "Rate_log",
    "Proto_tcp",
    "Proto_udp",
    "State_FIN",
]

CIC_SIGNATURE_COLUMNS: list[str] = [
    "Flow Duration",
    "Total Fwd Packets",
    "Flow Bytes/s",
    "Fwd Packet Length Mean",
    "Bwd Packet Length Mean",
    "Flow Packets/s",
    "SYN Flag Count",
]


def detect_schema(df: pd.DataFrame) -> Literal["argus", "cic", "unknown"]:
    """Return 'argus', 'cic', or 'unknown' based on column overlap (≥80% threshold)."""
    cols = set(df.columns)

    argus_hit = sum(c in cols for c in ARGUS_SIGNATURE_COLUMNS) / len(ARGUS_SIGNATURE_COLUMNS)
    cic_hit = sum(c in cols for c in CIC_SIGNATURE_COLUMNS) / len(CIC_SIGNATURE_COLUMNS)

    if argus_hit >= 0.80 and argus_hit >= cic_hit:
        return "argus"
    if cic_hit >= 0.80:
        return "cic"
    return "unknown"


def validate_input(df: pd.DataFrame, schema: Literal["argus", "cic"]) -> None:
    """Raise SchemaError listing missing required columns for the detected schema."""
    required = ARGUS_SIGNATURE_COLUMNS if schema == "argus" else CIC_SIGNATURE_COLUMNS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SchemaError(
            f"Schema '{schema}' detected but {len(missing)} required column(s) are missing: "
            + ", ".join(missing)
        )
