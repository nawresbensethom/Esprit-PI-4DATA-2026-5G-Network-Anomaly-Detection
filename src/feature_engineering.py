"""
feature_engineering.py
======================
Feature engineering pipeline for both 6G and 5G datasets.

6G  : Steps N4 (Protocol OHE), N7 (correlation drop), N8 (outlier cap), N9 (log transforms)
5G  : Steps 5 (correlation drop), 6 (outlier cap), 7 (log transforms), 8 (OHE encoding)
      + calls schema-alignment (Step 8b) and export (Step 9) from preprocessing.py

Usage
-----
    from preprocessing       import preprocess_5g
    from feature_engineering import engineer_6g, engineer_5g

    # 6G
    import preprocessing as p
    df = p.preprocess_6g('AIoT-Sol Dataset(6G).csv')   # already includes N4..N10

    # 5G — call preprocessing first, then engineer
    df_clean, shapes = preprocess_5g(base_dir='data/')
    df_clean         = engineer_5g(df_clean, shapes_before=shapes)
"""

import warnings
import pandas as pd
import numpy as np
from scipy.stats import skew, boxcox

warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────────────────
# 6G  helpers (N4 / N7 / N8 / N9)
# ─────────────────────────────────────────────────────────────────────────────

def n4_protocol_ohe(df: pd.DataFrame) -> pd.DataFrame:
    """N4 – Map Protocol int → string then OHE."""
    print('=' * 70)
    print('CLEANING N4 : PROTOCOL ENCODING (ONE-HOT)')
    print('=' * 70)

    if 'Protocol' not in df.columns:
        print('  – Protocol column not found, skipping.')
        return df

    proto_map_str = {6: 'TCP', 17: 'UDP', 0: 'Other'}
    df['Protocol_label'] = df['Protocol'].map(
        lambda x: proto_map_str.get(x, f'Proto_{int(x)}')
    )

    before_shape = df.shape
    ohe = pd.get_dummies(df['Protocol_label'], prefix='Proto', drop_first=False, dtype=int)
    df  = pd.concat([df, ohe], axis=1)
    df.drop(columns=['Protocol', 'Protocol_label'], inplace=True)

    print(f'  Before: {before_shape}  →  After: {df.shape}')
    print(f'  OHE columns added: {ohe.columns.tolist()}')
    return df


def n7_drop_correlated_features(df: pd.DataFrame, threshold: float = 0.90) -> pd.DataFrame:
    """N7 – Remove features with pairwise |r| > threshold (protected pairs kept)."""
    print('=' * 70)
    print(f'CLEANING N7 : DROP REDUNDANT FEATURES (r > {threshold})')
    print('=' * 70)

    # Directional pairs that carry IDS signal — never auto-drop either member
    PROTECTED_PAIRS = [
        ('Total Fwd Packets',      'Total Backward Packets'),
        ('Fwd Packet Length Mean', 'Bwd Packet Length Mean'),
        ('Fwd Header Length',      'Bwd Header Length'),
        ('Fwd IAT Total',          'Bwd IAT Total'),
    ]
    protected_cols = set(c for pair in PROTECTED_PAIRS for c in pair)

    feat_only = [c for c in df.columns if c != 'Label']
    corr_mat  = df[feat_only].corr().abs()
    upper     = corr_mat.where(np.triu(np.ones(corr_mat.shape), k=1).astype(bool))

    cols_to_drop = []
    for col in upper.columns:
        if col in protected_cols:
            continue
        if any(upper[col] > threshold):
            partner = upper[col][upper[col] > threshold].index[0]
            if partner not in protected_cols:
                cols_to_drop.append(col)

    before = df.shape
    df.drop(columns=cols_to_drop, inplace=True)
    print(f'  Dropped {len(cols_to_drop)} redundant features.')
    print(f'  Shape: {before} → {df.shape}')
    return df


def n8_outlier_capping(df: pd.DataFrame) -> pd.DataFrame:
    """N8 – Percentile capping (P1–P99) on continuous features."""
    print('=' * 70)
    print('CLEANING N8 : OUTLIER CAPPING (PERCENTILE 1%–99%)')
    print('=' * 70)

    # Exclude flag counts (extreme values ARE the attack signal)
    FLAG_COUNT_COLS = [c for c in df.columns if 'Flag Count' in c]
    OHE_COLS        = [c for c in df.columns if c.startswith(('Proto_', 'Port_'))]
    INDICATOR_COLS  = [c for c in df.columns if c.endswith('_was_missing')]
    EXCLUDE         = set(FLAG_COUNT_COLS + OHE_COLS + INDICATOR_COLS + ['Label'])

    num_cols = [c for c in df.select_dtypes(include=np.number).columns if c not in EXCLUDE]

    report = []
    for col in num_cols:
        p01  = df[col].quantile(0.01)
        p99  = df[col].quantile(0.99)
        n    = ((df[col] < p01) | (df[col] > p99)).sum()
        mean_before = df[col].mean()
        df[col]     = df[col].clip(p01, p99)
        mean_after  = df[col].mean()
        report.append({'Feature': col, 'N_capped': n,
                       'P01': p01, 'P99': p99,
                       'Mean before': mean_before, 'Mean after': mean_after})

    rdf = pd.DataFrame(report)
    rdf_nonzero = rdf[rdf['N_capped'] > 0].sort_values('N_capped', ascending=False)
    print(f'\n  Features with capped values: {len(rdf_nonzero)} / {len(num_cols)}')
    print(rdf_nonzero.to_string(index=False))
    return df


def n9_log_transform(df: pd.DataFrame) -> pd.DataFrame:
    """N9 – Semantics-aware log transform (log1p + Box-Cox fallback)."""
    print('=' * 70)
    print('CLEANING N9 : LOG TRANSFORMATIONS (semantics-aware)')
    print('=' * 70)

    SKEW_THRESHOLD = 1.0
    FLAG_COUNT_COLS = [c for c in df.columns if 'Flag Count' in c]
    OHE_COLS        = [c for c in df.columns if c.startswith(('Proto_', 'Port_'))]
    INDICATOR_COLS  = [c for c in df.columns if c.endswith('_was_missing')]
    EXCLUDE         = set(FLAG_COUNT_COLS + OHE_COLS + INDICATOR_COLS + ['Label'])

    # Continuous flow metrics candidates
    group_a = [
        'Flow Duration', 'Flow Bytes/s', 'Flow Packets/s',
        'Total Fwd Packets', 'Total Backward Packets',
        'Fwd Packet Length Mean', 'Bwd Packet Length Mean',
        'Fwd Packet Length Max', 'Bwd Packet Length Max',
        'Fwd Packet Length Min', 'Bwd Packet Length Min',
        'Fwd IAT Total', 'Bwd IAT Total', 'Flow IAT Mean',
        'Active Mean', 'Active Max', 'Active Min',
        'Idle Mean', 'Idle Max', 'Idle Min',
        'Fwd Header Length', 'Bwd Header Length',
    ]
    group_a = [c for c in group_a if c in df.columns and c not in EXCLUDE]

    skew_report = []
    for col in group_a:
        data        = df[col].dropna()
        skew_before = skew(data)
        col_log     = f'{col}_log' if col.replace(' ', '_') + '_log' not in df.columns else col + '_log2'

        if abs(skew_before) > SKEW_THRESHOLD:
            df[col] = np.log1p(np.abs(df[col]))
            skew_log1p = skew(df[col].dropna())

            if abs(skew_log1p) > SKEW_THRESHOLD and (df[col] > 0).all():
                try:
                    df[col], _ = boxcox(df[col] + 1e-9)
                    skew_final = skew(df[col].dropna())
                    method     = 'log1p + BoxCox'
                except Exception:
                    skew_final = skew_log1p
                    method     = 'log1p'
            else:
                skew_final = skew_log1p
                method     = 'log1p'
        else:
            skew_final = skew_before
            method     = 'none'

        skew_report.append({'Feature': col, 'Skew before': round(skew_before, 3),
                            'Skew final': round(skew_final, 3), 'Method': method})

    rdf = pd.DataFrame(skew_report)
    print(rdf.to_string(index=False))
    return df


def engineer_6g(df: pd.DataFrame) -> pd.DataFrame:
    """Run all 6G feature-engineering steps (N4, N7, N8, N9).

    Typically called after preprocessing.n1–n6.
    N10 (scaling) lives in preprocessing.n10_scale_features.
    """
    df = n4_protocol_ohe(df)
    df = n7_drop_correlated_features(df)
    df = n8_outlier_capping(df)
    df = n9_log_transform(df)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5G  helpers (Steps 5 / 6 / 7 / 8)
# ─────────────────────────────────────────────────────────────────────────────

def step5_drop_correlated_5g(df_clean: dict, threshold: float = 0.85) -> dict:
    """Step 5 – Drop highly correlated features from all 5G datasets."""
    print('=' * 65)
    print(f'STEP 5 : DROP HIGHLY CORRELATED FEATURES (r > {threshold})')
    print('=' * 65)

    # Domain-specific removal decisions (exact linear / near-exact combinations)
    corr_groups = {
        'Load / Rate'         : {'keep': 'Load',     'remove': ['DstLoad', 'DstRate']},
        'SrcLoad / SrcRate'   : {'keep': 'SrcLoad',  'remove': ['SrcRate']},
        'Dur / RunTime'       : {'keep': 'Dur',       'remove': ['RunTime', 'Sum']},
        'TotPkts derived'     : {'keep': 'TotPkts',  'remove': ['SrcPkts', 'DstPkts']},
        'TotBytes derived'    : {'keep': 'TotBytes',  'remove': ['DstBytes']},
        'Loss / pLoss'        : {'keep': 'pLoss',     'remove': ['SrcLoss', 'DstLoss']},
        'pDup'                : {'keep': None,        'remove': ['pDup']},
    }

    cols_to_drop_domain = []
    for group, info in corr_groups.items():
        cols_to_drop_domain.extend(info['remove'])
    cols_to_drop_domain = list(set(cols_to_drop_domain))

    for name, df in df_clean.items():
        present = [c for c in cols_to_drop_domain if c in df.columns]
        df_clean[name] = df.drop(columns=present)
        print(f'  {name}: dropped {len(present)} cols → shape {df_clean[name].shape}')

    return df_clean


def _percentile_cap(series: pd.Series, lower_pct: float = 0.01, upper_pct: float = 0.99):
    lo = series.quantile(lower_pct)
    hi = series.quantile(upper_pct)
    n  = ((series < lo) | (series > hi)).sum()
    return series.clip(lo, hi), lo, hi, n


def step6_outlier_capping_5g(df_clean: dict) -> dict:
    """Step 6 – Winsorise continuous 5G features (P1–P99)."""
    print('=' * 65)
    print('STEP 6 : OUTLIER CAPPING — PERCENTILE 1%–99%')
    print('=' * 65)

    cols_to_cap = [
        'TotPkts', 'TotBytes', 'Loss', 'Load', 'SrcLoad', 'Rate',
        'SrcPkts', 'SrcBytes', 'sMeanPktSz', 'dMeanPktSz',
        'Offset', 'pLoss', 'TcpRtt', 'SynAck', 'AckDat', 'DstWin', 'SrcWin',
    ]

    for name, df in df_clean.items():
        n_capped_total = 0
        for col in cols_to_cap:
            if col not in df.columns:
                continue
            series = pd.to_numeric(df[col], errors='coerce')
            if series.isna().all():
                continue
            series_capped, lo, hi, n = _percentile_cap(series)
            df[col] = series_capped
            n_capped_total += n
        print(f'  {name}: total capped values = {n_capped_total}')
        df_clean[name] = df

    return df_clean


def step7_log_transform_5g(df_clean: dict) -> dict:
    """Step 7 – Semantics-aware log transformations for 5G features."""
    print('=' * 65)
    print('STEP 7 : LOG TRANSFORMATIONS (semantics-aware)')
    print('=' * 65)

    COLS_FULL_TRANSFORM = [
        'Load', 'SrcLoad', 'Rate', 'SynAck', 'TcpRtt', 'AckDat',
        'SrcBytes', 'Loss', 'SrcPkts', 'sMeanPktSz', 'dMeanPktSz',
        'TotBytes', 'pLoss', 'Offset', 'TotPkts',
        'Mean', 'Min', 'Max',
    ]
    COLS_LOG1P_ONLY = ['SrcWin', 'DstWin']
    SKEW_THRESHOLD  = 1.0

    for name, df in df_clean.items():
        print(f'\n--- {name} ---')
        skew_report = []

        for col in COLS_FULL_TRANSFORM:
            if col not in df.columns:
                continue
            data = pd.to_numeric(df[col], errors='coerce').dropna()
            if len(data) < 2 or data.std() == 0:
                continue
            skew_before = skew(data)
            df[col]     = np.log1p(df[col].clip(lower=0))
            skew_log1p  = skew(df[col].dropna())
            method      = 'log1p'

            if abs(skew_log1p) > SKEW_THRESHOLD and (df[col].dropna() > 0).all():
                try:
                    df[col], _ = boxcox(df[col] + 1e-9)
                    skew_final = skew(df[col].dropna())
                    method     = 'log1p + BoxCox'
                except Exception:
                    skew_final = skew_log1p
            else:
                skew_final = skew_log1p

            skew_report.append({'col': col,
                                 'skew_before': round(skew_before, 3),
                                 'skew_final':  round(skew_final, 3),
                                 'method':      method})

        for col in COLS_LOG1P_ONLY:
            if col in df.columns:
                df[col] = np.log1p(df[col].clip(lower=0))
                skew_report.append({'col': col, 'skew_before': '?',
                                     'skew_final': '?', 'method': 'log1p'})

        print(pd.DataFrame(skew_report).to_string(index=False))
        df_clean[name] = df

    return df_clean


def step8_categorical_encoding_5g(df_clean: dict) -> dict:
    """Step 8 – OHE for low-cardinality categorical columns."""
    print('=' * 65)
    print('STEP 8 : CATEGORICAL ENCODING')
    print('=' * 65)

    cat_cols_ohe = ['Proto', 'State', 'Cause', 'dDSb']

    for name, df in df_clean.items():
        print(f'\n--- {name} ---')
        before     = df.shape
        to_drop    = []

        for col in cat_cols_ohe:
            if col not in df.columns:
                continue
            ohe = pd.get_dummies(df[col], prefix=col, drop_first=True, dtype=int)
            df  = pd.concat([df, ohe], axis=1)
            to_drop.append(col)
            print(f'  ✓ OHE {col:<10} → {ohe.columns.tolist()}')

        # Encode 'sDSb' with ordinal encoding (ordered DSCP codepoints)
        if 'sDSb' in df.columns:
            df['sDSb'] = df['sDSb'].astype('category').cat.codes
            print(f'  ✓ sDSb → ordinal int codes')

        # predicted retained only in Global (already handled in step2)
        df.drop(columns=to_drop, inplace=True)
        df_clean[name] = df
        print(f'  Shape: {before} → {df.shape}')

    return df_clean


def engineer_5g(df_clean: dict, shapes_before: dict = None, export_dir: str = '.') -> dict:
    """Run all 5G feature-engineering steps (5 → 8 → 8b → 9).

    Parameters
    ----------
    df_clean      : dict of DataFrames from preprocessing.preprocess_5g
    shapes_before : original shapes for the final report
    export_dir    : directory for exported CSVs

    Returns
    -------
    df_clean : fully engineered dict of DataFrames
    """
    from preprocessing import step8b_schema_alignment, step9_report_and_export

    df_clean = step5_drop_correlated_5g(df_clean)
    df_clean = step6_outlier_capping_5g(df_clean)
    df_clean = step7_log_transform_5g(df_clean)
    df_clean = step8_categorical_encoding_5g(df_clean)
    df_clean = step8b_schema_alignment(df_clean)
    if shapes_before is not None:
        step9_report_and_export(df_clean, shapes_before, base_dir=export_dir)
    return df_clean
