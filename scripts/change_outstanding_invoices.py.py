from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_CSV = REPO_ROOT / "data" / "ingest" / "financial_clean.csv"

EWM_SPAN = 21
MAX_ROW_TO_ROW_PCT = 0.12
CLIP_LOW_Q = 0.03
CLIP_HIGH_Q = 0.97

OUTSTANDING_TARGET_MIN = 5.0
OUTSTANDING_TARGET_MAX = 100.0


def capped_ewma(series: pd.Series, span: int, max_pct_step: float) -> pd.Series:
    base = pd.to_numeric(series, errors="coerce").ffill().bfill()
    smoothed = base.ewm(span=span, adjust=False).mean()
    out = smoothed.astype(float).copy()
    for i in range(1, len(out)):
        prev = out.iat[i - 1]
        lo = prev * (1.0 - max_pct_step)
        hi = prev * (1.0 + max_pct_step)
        out.iat[i] = float(np.clip(smoothed.iat[i], lo, hi))
    return out


def scale_unit_range(series: pd.Series, low: float, high: float) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").to_numpy(dtype=np.float64, copy=False)
    smin = float(np.nanmin(s))
    smax = float(np.nanmax(s))
    if smax <= smin or not np.isfinite(smin):
        mid = int(round((low + high) / 2.0))
        return pd.Series(mid, index=series.index, dtype=np.int64)
    span_req = high - low
    scaled = low + (s - smin) / (smax - smin) * span_req
    ints = np.rint(scaled).astype(np.int64)
    lo_i = int(round(low))
    hi_i = int(round(high))
    ints = np.clip(ints, lo_i, hi_i)
    return pd.Series(ints, index=series.index)


def main() -> None:
    path = FINANCIAL_CSV
    df = pd.read_csv(path, parse_dates=["date"])
    bak = path.with_suffix(".csv.bak")
    shutil.copy2(path, bak)

    raw = pd.to_numeric(df["outstanding_invoices"], errors="coerce")
    floor = float(raw.quantile(CLIP_LOW_Q))
    ceil_ = float(raw.quantile(CLIP_HIGH_Q))

    df["_rid"] = np.arange(len(df), dtype=np.int64)
    by_date = df.sort_values(["tenant_id", "date"], kind="mergesort")
    parts = []
    for _, group in by_date.groupby("tenant_id", sort=False):
        g = capped_ewma(group["outstanding_invoices"], EWM_SPAN, MAX_ROW_TO_ROW_PCT)
        g = g.clip(floor * 0.95, ceil_ * 1.05)
        g = scale_unit_range(g, OUTSTANDING_TARGET_MIN, OUTSTANDING_TARGET_MAX)
        parts.append(pd.Series(g.values, index=group.index))
    smoothed_sorted = pd.concat(parts)
    by_date.loc[smoothed_sorted.index, "outstanding_invoices"] = smoothed_sorted.values

    out_df = by_date.sort_values("_rid").drop(columns=["_rid"])

    inv = pd.to_numeric(out_df["outstanding_invoices"], errors="coerce")
    inv = np.rint(inv).astype(np.int64)
    inv = np.clip(
        inv,
        int(round(OUTSTANDING_TARGET_MIN)),
        int(round(OUTSTANDING_TARGET_MAX)),
    )
    out_df = out_df.copy()
    out_df["outstanding_invoices"] = inv

    out_df.to_csv(path, index=False)
    print("Copied prior ingest to {}".format(bak))
    print("Rewrote smoothed outstanding_invoices in {}".format(path))


if __name__ == "__main__":
    main()
