"""
Unified feature projection for 5G (Argus/CICIDS) and 6G (CICFlowMeter) data.
Zero logic changes from Moe.ipynb — only packaging.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed 16-feature unified schema — order must never change.
UNIFIED_FEATURES: list[str] = [
    "u_duration",
    "u_fwd_pkts",
    "u_bwd_pkts",
    "u_fwd_mean_size",
    "u_bwd_mean_size",
    "u_byte_rate",
    "u_pkt_rate",
    "u_pkt_ratio",
    "u_size_ratio",
    "u_syn",
    "u_fin",
    "u_rst",
    "u_psh",
    "u_is_tcp",
    "u_is_udp",
    "u_is_other",
]

BINARY_FEATURES: list[str] = [
    "u_syn",
    "u_fin",
    "u_rst",
    "u_psh",
    "u_is_tcp",
    "u_is_udp",
    "u_is_other",
]

NUMERIC_FEATURES: list[str] = [f for f in UNIFIED_FEATURES if f not in BINARY_FEATURES]


def first_available(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column in candidates that exists in df; None if none match."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def extract_5g_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive binary SYN/FIN/RST/PSH indicators from the cleaned 5G schema.
    State_* columns are OHE'd termination/control codes from ARGUS.
    SYN is not a direct ARGUS state — returns 0 when absent.
    """
    state_cols = [c for c in df.columns if c.startswith("State_")]
    out = pd.DataFrame(index=df.index)
    for flag_name, subs in [
        ("u_syn", ["SYN", "S_"]),
        ("u_fin", ["FIN", "F_"]),
        ("u_rst", ["RST", "R_"]),
        ("u_psh", ["PSH", "P_"]),
    ]:
        matched = [c for c in state_cols if any(s in c.upper() for s in subs)]
        if matched:
            out[flag_name] = (df[matched].sum(axis=1) > 0).astype(int)
        else:
            out[flag_name] = 0
    return out


def project_5g(df: pd.DataFrame) -> pd.DataFrame:
    """Map the cleaned 5G (Argus/CICIDS) dataframe onto the 16-feature unified schema."""
    out = pd.DataFrame(index=df.index)

    col_dur = first_available(df, ["Dur_log", "Dur"])
    col_fwd_pk = first_available(df, ["SrcPkts_log", "SrcPkts"])
    col_fwd_sz = first_available(df, ["sMeanPktSz_log", "sMeanPktSz"])
    col_bwd_sz = first_available(df, ["dMeanPktSz_log", "dMeanPktSz"])
    col_byte_rt = first_available(df, ["Load_log", "Load", "SrcLoad_log", "SrcLoad"])
    col_pkt_rt = first_available(df, ["Rate_log", "Rate", "SrcRate_log", "SrcRate"])
    col_bwd_pk = first_available(df, ["DstPkts_log", "DstPkts"])
    col_tot_pk = first_available(df, ["TotPkts_log", "TotPkts"])

    out["u_duration"] = df[col_dur].values if col_dur else 0.0
    out["u_fwd_pkts"] = df[col_fwd_pk].values if col_fwd_pk else 0.0
    out["u_fwd_mean_size"] = df[col_fwd_sz].values if col_fwd_sz else 0.0
    out["u_bwd_mean_size"] = df[col_bwd_sz].values if col_bwd_sz else 0.0
    out["u_byte_rate"] = df[col_byte_rt].values if col_byte_rt else 0.0
    out["u_pkt_rate"] = df[col_pkt_rt].values if col_pkt_rt else 0.0

    # u_bwd_pkts: prefer direct column; reconstruct from tot - fwd when missing
    if col_bwd_pk:
        out["u_bwd_pkts"] = df[col_bwd_pk].values
    elif col_tot_pk and col_fwd_pk:
        tot_lin = (
            np.expm1(df[col_tot_pk].values)
            if col_tot_pk.endswith("_log")
            else df[col_tot_pk].values
        )
        fwd_lin = (
            np.expm1(df[col_fwd_pk].values)
            if col_fwd_pk.endswith("_log")
            else df[col_fwd_pk].values
        )
        bwd_lin = np.clip(tot_lin - fwd_lin, a_min=0.0, a_max=None)
        out["u_bwd_pkts"] = np.log1p(bwd_lin)
    else:
        out["u_bwd_pkts"] = 0.0

    eps = 1e-6
    fwd_pk = out["u_fwd_pkts"].abs() + eps
    bwd_pk = out["u_bwd_pkts"].abs() + eps
    out["u_pkt_ratio"] = fwd_pk / (fwd_pk + bwd_pk)

    fwd_sz = out["u_fwd_mean_size"].abs() + eps
    bwd_sz = out["u_bwd_mean_size"].abs() + eps
    out["u_size_ratio"] = fwd_sz / (fwd_sz + bwd_sz)

    # TCP flags from State_* OHE columns
    flags = extract_5g_flags(df)
    out = pd.concat([out, flags], axis=1)

    # Protocol one-hot from Proto_* OHE columns
    proto_cols = [c for c in df.columns if c.lower().startswith("proto_")]
    out["u_is_tcp"] = 0
    out["u_is_udp"] = 0
    out["u_is_other"] = 0
    for c in proto_cols:
        if "tcp" in c.lower():
            out["u_is_tcp"] = out["u_is_tcp"] | (df[c] > 0).astype(int)
        elif "udp" in c.lower():
            out["u_is_udp"] = out["u_is_udp"] | (df[c] > 0).astype(int)
        else:
            out["u_is_other"] = out["u_is_other"] | (df[c] > 0).astype(int)

    none_set = out[["u_is_tcp", "u_is_udp", "u_is_other"]].sum(axis=1) == 0
    out.loc[none_set, "u_is_other"] = 1

    return out[UNIFIED_FEATURES]


def project_6g(df: pd.DataFrame) -> pd.DataFrame:
    """Map the cleaned 6G (CICFlowMeter) dataframe onto the 16-feature unified schema."""
    out = pd.DataFrame(index=df.index)

    col_dur = first_available(df, ["Flow Duration", "Flow_Duration"])
    col_fwd_pk = first_available(df, ["Total Fwd Packets", "Total_Fwd_Packets"])
    col_bwd_pk = first_available(df, ["Total Backward Packets", "Total_Backward_Packets"])
    col_fwd_sz = first_available(df, ["Fwd Packet Length Mean", "Fwd_Packet_Length_Mean"])
    col_bwd_sz = first_available(df, ["Bwd Packet Length Mean", "Bwd_Packet_Length_Mean"])
    col_byte_rt = first_available(df, ["Flow Bytes/s", "Flow_Bytes_s"])
    col_pkt_rt = first_available(df, ["Flow Packets/s", "Flow_Packets_s"])

    out["u_duration"] = df[col_dur].values if col_dur else 0.0
    out["u_fwd_pkts"] = df[col_fwd_pk].values if col_fwd_pk else 0.0
    out["u_bwd_pkts"] = df[col_bwd_pk].values if col_bwd_pk else 0.0
    out["u_fwd_mean_size"] = df[col_fwd_sz].values if col_fwd_sz else 0.0
    out["u_bwd_mean_size"] = df[col_bwd_sz].values if col_bwd_sz else 0.0
    out["u_byte_rate"] = df[col_byte_rt].values if col_byte_rt else 0.0
    out["u_pkt_rate"] = df[col_pkt_rt].values if col_pkt_rt else 0.0

    eps = 1e-6
    fwd_pk = out["u_fwd_pkts"].abs() + eps
    bwd_pk = out["u_bwd_pkts"].abs() + eps
    out["u_pkt_ratio"] = fwd_pk / (fwd_pk + bwd_pk)

    fwd_sz = out["u_fwd_mean_size"].abs() + eps
    bwd_sz = out["u_bwd_mean_size"].abs() + eps
    out["u_size_ratio"] = fwd_sz / (fwd_sz + bwd_sz)

    # TCP flags from CICFlowMeter flag-count columns
    col_syn = first_available(df, ["SYN Flag Count", "SYN_Flag_Count"])
    col_fin = first_available(df, ["FIN Flag Count", "FIN_Flag_Count"])
    col_rst = first_available(df, ["RST Flag Count", "RST_Flag_Count"])
    col_psh = first_available(df, ["PSH Flag Count", "PSH_Flag_Count"])
    out["u_syn"] = (df[col_syn].values > 0).astype(int) if col_syn else 0
    out["u_fin"] = (df[col_fin].values > 0).astype(int) if col_fin else 0
    out["u_rst"] = (df[col_rst].values > 0).astype(int) if col_rst else 0
    out["u_psh"] = (df[col_psh].values > 0).astype(int) if col_psh else 0

    # Protocol: check OHE columns first, then raw numeric Protocol column
    proto_ohe = [c for c in df.columns if c.lower().startswith("proto_")]
    out["u_is_tcp"] = 0
    out["u_is_udp"] = 0
    out["u_is_other"] = 0

    if proto_ohe:
        for c in proto_ohe:
            if "tcp" in c.lower():
                out["u_is_tcp"] = out["u_is_tcp"] | (df[c] > 0).astype(int)
            elif "udp" in c.lower():
                out["u_is_udp"] = out["u_is_udp"] | (df[c] > 0).astype(int)
            else:
                out["u_is_other"] = out["u_is_other"] | (df[c] > 0).astype(int)
    else:
        col_proto = first_available(df, ["Protocol", "protocol"])
        if col_proto:
            # CICFlowMeter numeric codes: 6=TCP, 17=UDP
            out["u_is_tcp"] = (df[col_proto] == 6).astype(int)
            out["u_is_udp"] = (df[col_proto] == 17).astype(int)
            out["u_is_other"] = ((df[col_proto] != 6) & (df[col_proto] != 17)).astype(int)

    # Rows with no proto set: only TCP OHE present → non-TCP rows default to 'other'
    none_set = out[["u_is_tcp", "u_is_udp", "u_is_other"]].sum(axis=1) == 0
    out.loc[none_set, "u_is_other"] = 1

    return out[UNIFIED_FEATURES]
