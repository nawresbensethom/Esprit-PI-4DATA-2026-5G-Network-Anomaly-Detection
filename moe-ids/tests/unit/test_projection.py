"""
Critical snapshot tests for projection.py.
Any silent logic change in project_5g / project_6g will break these tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from moe_ids.projection import UNIFIED_FEATURES, project_5g, project_6g

FIXTURES = Path(__file__).parent.parent / "fixtures"
BINARY_COLS = ["u_syn", "u_fin", "u_rst", "u_psh", "u_is_tcp", "u_is_udp", "u_is_other"]
PROTO_COLS = ["u_is_tcp", "u_is_udp", "u_is_other"]


# ── Shape & schema ────────────────────────────────────────────────────────


def test_project_5g_shape(df_5g: pd.DataFrame) -> None:
    out = project_5g(df_5g)
    assert out.shape == (len(df_5g), 16)


def test_project_6g_shape(df_6g: pd.DataFrame) -> None:
    out = project_6g(df_6g)
    assert out.shape == (len(df_6g), 16)


def test_project_5g_column_order(df_5g: pd.DataFrame) -> None:
    out = project_5g(df_5g)
    assert list(out.columns) == UNIFIED_FEATURES


def test_project_6g_column_order(df_6g: pd.DataFrame) -> None:
    out = project_6g(df_6g)
    assert list(out.columns) == UNIFIED_FEATURES


# ── NaN / Inf ─────────────────────────────────────────────────────────────


def test_project_5g_no_nan(df_5g: pd.DataFrame) -> None:
    out = project_5g(df_5g)
    assert not out.isna().any().any(), "NaN values found in project_5g output"


def test_project_6g_no_nan(df_6g: pd.DataFrame) -> None:
    out = project_6g(df_6g)
    assert not out.isna().any().any(), "NaN values found in project_6g output"


def test_project_5g_no_inf(df_5g: pd.DataFrame) -> None:
    out = project_5g(df_5g)
    assert not np.isinf(out.values).any(), "Inf values found in project_5g output"


def test_project_6g_no_inf(df_6g: pd.DataFrame) -> None:
    out = project_6g(df_6g)
    assert not np.isinf(out.values).any(), "Inf values found in project_6g output"


# ── Binary columns ────────────────────────────────────────────────────────


def test_project_5g_binary_columns(df_5g: pd.DataFrame) -> None:
    out = project_5g(df_5g)
    for col in BINARY_COLS:
        vals = out[col].unique()
        assert set(vals).issubset({0, 1}), f"Column {col} contains non-binary values: {vals}"


def test_project_6g_binary_columns(df_6g: pd.DataFrame) -> None:
    out = project_6g(df_6g)
    for col in BINARY_COLS:
        vals = out[col].unique()
        assert set(vals).issubset({0, 1}), f"Column {col} contains non-binary values: {vals}"


# ── Protocol one-hot sums to exactly 1 ───────────────────────────────────


def test_project_5g_proto_onehot_sum(df_5g: pd.DataFrame) -> None:
    out = project_5g(df_5g)
    sums = out[PROTO_COLS].sum(axis=1)
    assert (sums == 1).all(), f"Protocol one-hot sums != 1: {sums.unique()}"


def test_project_6g_proto_onehot_sum(df_6g: pd.DataFrame) -> None:
    out = project_6g(df_6g)
    sums = out[PROTO_COLS].sum(axis=1)
    assert (sums == 1).all(), f"Protocol one-hot sums != 1: {sums.unique()}"


# ── Snapshot tests (catches silent projection drift) ─────────────────────


def _load_snapshot(name: str) -> dict:
    path = FIXTURES / f"snapshot_{name}.json"
    with open(path) as f:
        return json.load(f)


@pytest.mark.parametrize("row_idx", [0, 4, 9])
def test_project_5g_snapshot(df_5g: pd.DataFrame, row_idx: int) -> None:
    snap = _load_snapshot("5g")
    out = project_5g(df_5g)
    actual = out.iloc[row_idx].to_dict()
    expected = snap[str(row_idx)]
    for col, exp_val in expected.items():
        assert (
            abs(actual[col] - exp_val) < 1e-9
        ), f"Row {row_idx} col '{col}': got {actual[col]}, expected {exp_val}"


@pytest.mark.parametrize("row_idx", [0, 4, 9])
def test_project_6g_snapshot(df_6g: pd.DataFrame, row_idx: int) -> None:
    snap = _load_snapshot("6g")
    out = project_6g(df_6g)
    actual = out.iloc[row_idx].to_dict()
    expected = snap[str(row_idx)]
    for col, exp_val in expected.items():
        assert (
            abs(actual[col] - exp_val) < 1e-9
        ), f"Row {row_idx} col '{col}': got {actual[col]}, expected {exp_val}"
