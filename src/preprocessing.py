"""
preprocessing.py
================
Data loading, cleaning and export pipeline for both 6G and 5G datasets.

6G  (AIoT-Sol)  : Steps N1–N6, N10 + export → AIoT_6G_CLEANED.csv
5G  (5G-NIDD)   : Steps 1–4, 8b, 9 + export → {Global/eMBB/mMTC/URLLC}_CLEANED.csv

Usage
-----
    from preprocessing import preprocess_6g, preprocess_5g
    df_6g            = preprocess_6g('AIoT-Sol Dataset(6G).csv')
    cleaned_5g       = preprocess_5g(['Global.csv', 'eMBB.csv', 'mMTC.csv', 'URLLC.csv'])
"""

import os
import warnings
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.float_format', '{:.4f}'.format)


# ─────────────────────────────────────────────────────────────────────────────
# 6G  ── AIoT-Sol Dataset
# ─────────────────────────────────────────────────────────────────────────────

def load_6g(filepath: str) -> pd.DataFrame:
    """Load raw 6G CSV and return a working copy."""
    print('=' * 70)
    print('STEP 1 : DATASET LOADING')
    print('=' * 70)

    df_raw = pd.read_csv(filepath)
    df     = df_raw.copy()

    print(f'\n  Shape        : {df.shape[0]:,} rows × {df.shape[1]} columns')
    print(f'  Memory       : {df.memory_usage(deep=True).sum()/1e6:.2f} MB')
    print(f'  Types        : {dict(df.dtypes.value_counts())}')
    print(f'  Numeric cols : {df.select_dtypes(include=np.number).shape[1]}')
    print(f'  Object cols  : {df.select_dtypes(include="object").shape[1]}')
    return df


def n1_remove_nan_labels(df: pd.DataFrame) -> pd.DataFrame:
    """N1 – Remove rows where Label is NaN."""
    print('=' * 70)
    print('CLEANING N1 : INITIALISATION & NaN LABEL ROW REMOVAL')
    print('=' * 70)

    df_clean   = df.copy()
    shape_init = df_clean.shape
    n_nan_label = df_clean['Label'].isna().sum()
    df_clean    = df_clean.dropna(subset=['Label'])

    print(f'\n  Initial shape              : {shape_init}')
    print(f'  NaN Label rows removed     : {n_nan_label}')
    print(f'  Shape after removal        : {df_clean.shape}')
    print(f'  Unique labels              : {df_clean["Label"].unique().tolist()}')
    return df_clean


def n2_drop_identifiers_encode_port(df: pd.DataFrame) -> pd.DataFrame:
    """N2 – Drop network identifier columns; OHE Destination Port."""
    print('=' * 70)
    print('CLEANING N2 : DROP NETWORK IDENTIFIER COLUMNS')
    print('=' * 70)

    id_cols_config = {
        'Flow ID'        : 'flow identifier (index)',
        'Source IP'      : 'source IP address (anonymised/hashed)',
        'Destination IP' : 'destination IP address',
        'Timestamp'      : 'capture timestamp',
        'External IP'    : 'external IP (100% = 0.0 in this dataset)',
        'Source Port'    : 'ephemeral source port (random, not predictive)',
    }

    # Destination Port OHE before dropping the raw column
    if 'Destination Port' in df.columns:
        top_ports  = [80, 443, 22, 53, 21, 25, 3389, 8080]
        port_series = df['Destination Port']
        for p in top_ports:
            col_name = f'Port_{p}'
            df[col_name] = (port_series == p).astype(int)
        df['Port_other'] = (~port_series.isin(top_ports)).astype(int)
        id_cols_config['Destination Port'] = 'replaced by OHE Port_* columns'
        print('  ✓ Destination Port encoded as OHE columns')

    cols_to_drop = [c for c in id_cols_config if c in df.columns]
    df.drop(columns=cols_to_drop, inplace=True)
    for col, reason in id_cols_config.items():
        status = '✓ dropped' if col in cols_to_drop else '– not present'
        print(f'  {status}: {col}  ({reason})')

    print(f'\n  Shape after N2: {df.shape}')
    return df


def n3_drop_constant_columns(df: pd.DataFrame) -> pd.DataFrame:
    """N3 – Drop zero-variance (constant) columns."""
    print('=' * 70)
    print('CLEANING N3 : DROP CONSTANT COLUMNS')
    print('=' * 70)

    num_cols   = df.select_dtypes(include=np.number).columns.tolist()
    before     = df.shape
    zero_var   = [c for c in num_cols if df[c].std() == 0]

    print(f'\n  Constant columns (std=0): {len(zero_var)}')
    for c in zero_var:
        print(f'    ✗ {c:<40} val={df[c].unique()[0]}')

    df.drop(columns=zero_var, inplace=True)
    print(f'\n  Shape: {before} → {df.shape}')
    return df


def n5_impute_missing(df: pd.DataFrame) -> pd.DataFrame:
    """N5 – Impute missing values (informative missingness + median fallback)."""
    print('=' * 70)
    print('CLEANING N5 : NUMERICAL MISSING VALUE IMPUTATION')
    print('=' * 70)

    RATE_DERIVED_COLS = ['Flow Bytes/s', 'Flow Packets/s']

    print('\n  [A] Informative missingness indicators (derived features):')
    for col in RATE_DERIVED_COLS:
        if col in df.columns:
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)
            indicator_col = f'{col}_was_missing'
            df[indicator_col] = df[col].isna().astype(int)
            df[col] = df[col].fillna(0.0)
            n_missing = df[indicator_col].sum()
            print(f'    {col}: {n_missing} NaN → 0.0  |  indicator: {indicator_col}')

    print('\n  [B] Remaining numerical columns — median imputation:')
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    imputed  = []
    for col in num_cols:
        n_miss = df[col].isna().sum()
        if n_miss > 0:
            median_val = df[col].median()
            df[col].fillna(median_val, inplace=True)
            imputed.append(col)
            print(f'    {col}: {n_miss} NaN → median {median_val:.4f}')

    total_missing_after = df.isnull().sum().sum()
    print(f'\n  Total missing after imputation: {total_missing_after}')
    return df


def n6_remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """N6 – Detect and remove exact duplicate rows."""
    print('=' * 70)
    print('CLEANING N6 : DUPLICATE DETECTION & REMOVAL')
    print('=' * 70)

    n_before     = len(df)
    n_duplicates = df.duplicated().sum()

    print(f'\n  Exact duplicates found: {n_duplicates} ({n_duplicates/n_before*100:.2f}%)')

    if n_duplicates > 0:
        df = df.drop_duplicates()
        print(f'  ✓ {n_duplicates} duplicates removed')
        print(f'  Shape: ({n_before}, {df.shape[1]}) → {df.shape}')
    else:
        print('  ✓ No duplicates detected')

    df.reset_index(drop=True, inplace=True)
    return df


def n10_scale_features(df: pd.DataFrame) -> tuple:
    """N10 – StandardScaler on continuous features; returns (df_final, scaler, feature_cols)."""
    print('=' * 70)
    print('CLEANING N10 : FEATURE SCALING (STANDARDSCALER)')
    print('=' * 70)

    X = df.drop(columns=['Label'])
    y = df['Label'].copy()

    # Columns excluded from scaling
    ohe_cols         = [c for c in X.columns if c.startswith(('Proto_', 'Port_'))]
    indicator_cols   = [c for c in X.columns if c.endswith('_was_missing')]
    flag_count_cols  = [c for c in X.columns if 'Flag Count' in c]
    exclude_scaling  = set(ohe_cols + indicator_cols + flag_count_cols)

    cols_to_scale = [c for c in X.columns if c not in exclude_scaling]
    print(f'\n  Columns to scale        : {len(cols_to_scale)}')
    print(f'  Columns excluded        : {len(exclude_scaling)}')

    scaler = StandardScaler()
    X[cols_to_scale] = scaler.fit_transform(X[cols_to_scale])

    # Verification
    means  = X[cols_to_scale].mean()
    stds   = X[cols_to_scale].std()
    print(f'\n  Post-scaling mean  (should ≈ 0) : min={means.min():.6f}, max={means.max():.6f}')
    print(f'  Post-scaling std   (should ≈ 1) : min={stds.min():.4f},  max={stds.max():.4f}')

    df_final = pd.concat([X, y.rename('Label')], axis=1)
    return df_final, scaler, cols_to_scale


def export_6g(df_final: pd.DataFrame, output_file: str = 'AIoT_6G_CLEANED.csv') -> None:
    """Export the cleaned 6G dataset to CSV."""
    print('=' * 70)
    print('EXPORT CLEANED DATASET')
    print('=' * 70)

    df_final.to_csv(output_file, index=False)
    size_mb = os.path.getsize(output_file) / 1e6

    print(f'\n  ✓ File exported: {output_file}')
    print(f'  Shape          : {df_final.shape}')
    print(f'  File size      : {size_mb:.2f} MB')
    print('\n' + '=' * 70)
    print('✓ EDA + CLEANING PIPELINE COMPLETED SUCCESSFULLY')
    print('=' * 70)


def preprocess_6g(filepath: str, output_file: str = 'AIoT_6G_CLEANED.csv') -> pd.DataFrame:
    """Full 6G preprocessing pipeline (N1–N6 + N10).

    Parameters
    ----------
    filepath    : path to raw 'AIoT-Sol Dataset(6G).csv'
    output_file : path for the exported cleaned CSV

    Returns
    -------
    df_final : cleaned & scaled DataFrame
    """
    df = load_6g(filepath)
    df = n1_remove_nan_labels(df)
    df = n2_drop_identifiers_encode_port(df)
    df = n3_drop_constant_columns(df)
    df = n5_impute_missing(df)
    df = n6_remove_duplicates(df)
    df_final, _, _ = n10_scale_features(df)
    export_6g(df_final, output_file)
    return df_final


# ─────────────────────────────────────────────────────────────────────────────
# 5G  ── 5G-NIDD Dataset (Global, eMBB, mMTC, URLLC)
# ─────────────────────────────────────────────────────────────────────────────

DATASET_NAMES_5G = ['Global', 'eMBB', 'mMTC', 'URLLC']


def load_5g(dataset_names: list = None, base_dir: str = '.') -> dict:
    """Step 1 – Load all four 5G CSV files."""
    print('=' * 65)
    print('STEP 1 : LOADING & SAFETY COPIES')
    print('=' * 65)

    if dataset_names is None:
        dataset_names = DATASET_NAMES_5G

    df_original   = {}
    df_clean      = {}
    shapes_before = {}

    for name in dataset_names:
        filename = os.path.join(base_dir, name + '.csv')
        if os.path.exists(filename):
            df_original[name]   = pd.read_csv(filename)
            df_clean[name]      = df_original[name].copy()
            shapes_before[name] = df_original[name].shape
            print(f'  ✓ {name:8s} | Shape: {shapes_before[name]}')
        else:
            print(f'  ✗ {name:8s} not found at {filename}')

    print(f'\n  Total datasets loaded : {len(df_clean)}')
    return df_clean, shapes_before


def step2_drop_useless_columns(df_clean: dict) -> dict:
    """Step 2 – Drop non-informative columns."""
    print('=' * 65)
    print('STEP 2 : DROP USELESS COLUMNS')
    print('=' * 65)

    cols_always_drop = {
        'sVid'    : '97-100% missing across datasets',
        'dVid'    : '99-100% missing across datasets',
        'SrcGap'  : '100% zero — zero variance',
        'DstGap'  : '100% zero — zero variance',
        'X'       : 'row index — no predictive value',
        'UniqueID': 'Argus flow identifier — no predictive value',
        'Seq'     : 'flow sequence number — temporal ordering only',
    }
    cols_drop_slice_only = {
        'predicted': 'slice label — redundant in single-slice datasets',
    }

    for name, df in df_clean.items():
        cols_to_drop = [c for c in cols_always_drop if c in df.columns]
        if name != 'Global' and 'predicted' in df.columns:
            cols_to_drop.append('predicted')
        df_clean[name] = df.drop(columns=cols_to_drop)
        print(f'  {name}: dropped {len(cols_to_drop)} cols → shape {df_clean[name].shape}')

    return df_clean


def step3_missing_values(df_clean: dict) -> dict:
    """Step 3 – Handle missing values (informative indicators + median imputation)."""
    print('=' * 65)
    print('STEP 3 : MISSING VALUE TREATMENT')
    print('=' * 65)

    HIGH_MISSING_THRESHOLD     = 0.75
    informative_missing_cols   = ['dTos', 'dTtl', 'dHops', 'DstTCPBase', 'SrcTCPBase']
    cols_median_impute         = ['dTos', 'dTtl', 'dHops', 'DstWin', 'SrcWin', 'sTos', 'sTtl', 'sHops']
    tcp_base_cols              = ['DstTCPBase', 'SrcTCPBase']

    for name, df in df_clean.items():
        print(f'\n--- {name} ---')
        dropped_high_missing = []

        # Drop columns with >75% missing
        for col in df.columns:
            if df[col].isnull().mean() > HIGH_MISSING_THRESHOLD:
                dropped_high_missing.append(col)
        if dropped_high_missing:
            df.drop(columns=dropped_high_missing, inplace=True)
            print(f'  Dropped (>{HIGH_MISSING_THRESHOLD*100:.0f}% missing): {dropped_high_missing}')

        # Informative missingness indicators
        for col in informative_missing_cols:
            if col in df.columns and df[col].isnull().any():
                df[f'{col}_was_missing'] = df[col].isnull().astype(int)

        # TCP base: impute with 0
        for col in tcp_base_cols:
            if col in df.columns:
                df[col].fillna(0, inplace=True)

        # Median imputation for standard numerical cols
        for col in cols_median_impute:
            if col in df.columns and df[col].isnull().any():
                median_val = df.loc[df[col].notna(), col].median()
                df[col].fillna(median_val, inplace=True)

        n_remaining = df.isnull().sum().sum()
        print(f'  Remaining NaN : {n_remaining}')
        df_clean[name] = df

    return df_clean


def step4_handle_question_marks(df_clean: dict) -> dict:
    """Step 4 – Replace '?' sentinel in categorical columns."""
    print('=' * 65)
    print("STEP 4 : HANDLE '?' IN CATEGORICAL COLUMNS")
    print('=' * 65)

    for name, df in df_clean.items():
        print(f'\n--- {name} ---')

        if 'sDSb' in df.columns:
            n = (df['sDSb'] == '?').sum()
            if n > 0:
                mode_val = df.loc[df['sDSb'] != '?', 'sDSb'].mode()[0]
                df.loc[df['sDSb'] == '?', 'sDSb'] = mode_val
                print(f'  ✓ sDSb : {n} "?" → mode "{mode_val}"')
            else:
                print('  ✓ sDSb : no "?" values')

        if 'dDSb' in df.columns:
            n = (df['dDSb'] == '?').sum()
            if n > 0:
                df.loc[df['dDSb'] == '?', 'dDSb'] = 'unknown'
                print(f'  ✓ dDSb : {n} "?" → "unknown" (explicit category)')
            else:
                print('  ✓ dDSb : no "?" values')

        df_clean[name] = df

    return df_clean


def step8b_schema_alignment(df_clean: dict) -> dict:
    """Step 8b – Reindex all datasets on Global schema after OHE."""
    print('=' * 65)
    print('STEP 8b : SCHEMA ALIGNMENT — REINDEX ON GLOBAL REFERENCE')
    print('=' * 65)
    print()
    print('  Problem: OHE generates different columns per dataset')
    print('           (e.g. eMBB is 100% TCP → no Proto_udp column).')
    print('  Solution: reindex all datasets on Global schema.')
    print('  Missing cols → filled with 0, extra cols → dropped.')
    print()

    reference_cols = df_clean['Global'].columns.tolist()
    print(f'  Reference columns (Global): {len(reference_cols)}')
    print()

    for name in df_clean:
        before_cols = set(df_clean[name].columns)
        df_clean[name] = df_clean[name].reindex(
            columns=reference_cols, fill_value=0
        )
        missing = set(reference_cols) - before_cols
        extra   = before_cols - set(reference_cols)
        print(f'  {name}: +{len(missing)} added, -{len(extra)} dropped → {df_clean[name].shape}')

    return df_clean


def step9_report_and_export(df_clean: dict, shapes_before: dict, base_dir: str = '.') -> None:
    """Step 9 – Final cleaning report + export."""
    print('=' * 65)
    print('STEP 9 : FINAL CLEANING REPORT')
    print('=' * 65)

    print('\n[1] BEFORE / AFTER SUMMARY')
    print(f'  {"Dataset":<10} {"Rows":>8} {"Cols_before":>11} {"Cols_after":>11} {"Delta":>7}')
    print('  ' + '-' * 50)
    for name, df in df_clean.items():
        b     = shapes_before.get(name, (df.shape[0], '?'))
        a     = df.shape
        delta = a[1] - (b[1] if isinstance(b[1], int) else 0)
        sign  = '+' if delta > 0 else ''
        print(f'  {name:<10} {a[0]:>8,} {str(b[1]):>11} {a[1]:>11} {sign+str(delta):>7}')

    print('\n[2] MISSING VALUES REMAINING')
    for name, df in df_clean.items():
        n = df.isnull().sum().sum()
        print(f'  {"✓" if n == 0 else "⚠"} {name:<10} : {n} missing cells')

    print('\n[3] LABEL DISTRIBUTION (FINAL)')
    for name, df in df_clean.items():
        lc = df['Label'].value_counts()
        print(f'  {name}: {dict(lc)}')

    # Export
    print('\n' + '=' * 65)
    print('EXPORT')
    print('=' * 65)
    for name, df in df_clean.items():
        fname = os.path.join(base_dir, f'{name}_CLEANED.csv')
        df.to_csv(fname, index=False)
        size_mb = os.path.getsize(fname) / 1e6
        print(f'  ✓ {fname:<30} | {df.shape} | {size_mb:.2f} MB')

    print('\n✓ PIPELINE COMPLETE')


def preprocess_5g(base_dir: str = '.', dataset_names: list = None) -> dict:
    """Full 5G preprocessing pipeline (Steps 1–4, 8b, 9).

    Note: Steps 5 (corr drop), 6 (outlier cap), 7 (log transform), 8 (OHE)
          are handled in feature_engineering.py.

    Parameters
    ----------
    base_dir      : directory containing the raw CSV files
    dataset_names : list of dataset names (default: Global/eMBB/mMTC/URLLC)

    Returns
    -------
    df_clean : dict mapping dataset name → cleaned DataFrame
    """
    if dataset_names is None:
        dataset_names = DATASET_NAMES_5G

    df_clean, shapes_before = load_5g(dataset_names, base_dir)
    df_clean = step2_drop_useless_columns(df_clean)
    df_clean = step3_missing_values(df_clean)
    df_clean = step4_handle_question_marks(df_clean)
    # Steps 5-8 run in feature_engineering.py
    # step8b and step9 are called from feature_engineering after OHE
    return df_clean, shapes_before
