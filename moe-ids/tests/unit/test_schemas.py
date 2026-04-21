import pandas as pd
import pytest

from moe_ids.schemas import (
    ARGUS_SIGNATURE_COLUMNS,
    SchemaError,
    detect_schema,
    validate_input,
)


def _df(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=cols)


def test_detect_argus_full(df_5g: pd.DataFrame) -> None:
    assert detect_schema(df_5g) == "argus"


def test_detect_cic_full(df_6g: pd.DataFrame) -> None:
    assert detect_schema(df_6g) == "cic"


def test_detect_argus_partial_80pct() -> None:
    # 7/8 = 87.5% of ARGUS_SIGNATURE_COLUMNS
    cols = ARGUS_SIGNATURE_COLUMNS[:-1] + ["some_other_col"]
    assert detect_schema(_df(cols)) == "argus"


def test_detect_unknown_below_threshold() -> None:
    # Only 2 matching columns — below 80%
    cols = ARGUS_SIGNATURE_COLUMNS[:2] + ["unrelated_a", "unrelated_b"]
    assert detect_schema(_df(cols)) == "unknown"


def test_detect_unknown_empty() -> None:
    assert detect_schema(_df(["a", "b", "c"])) == "unknown"


def test_validate_input_passes(df_5g: pd.DataFrame) -> None:
    validate_input(df_5g, "argus")  # should not raise


def test_validate_input_raises_on_missing() -> None:
    df = _df(["Dur"])
    with pytest.raises(SchemaError, match="missing"):
        validate_input(df, "argus")
