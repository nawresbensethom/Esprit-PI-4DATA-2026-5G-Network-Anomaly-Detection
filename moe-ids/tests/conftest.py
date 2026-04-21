from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def df_5g() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "sample_5g_10rows.csv")


@pytest.fixture
def df_6g() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "sample_6g_10rows.csv")
