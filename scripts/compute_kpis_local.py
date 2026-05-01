from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FINANCIAL = BASE_DIR / "data" / "ingest" / "financial_clean.csv"
DEFAULT_SALES = BASE_DIR / "data" / "ingest" / "sales_marketing_clean.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "kpi"

WEEK_FREQ = "W-SUN"

GOLD_COLUMNS = [
    "tenant_id",
    "period_start",
    "period_end",
    "period_grain",
    "domain",
    "metric_name",
    "metric_value",
    "metric_unit",
    "computed_at",
    "run_id",
    "trace_id",
]


def _week_grouper() -> pd.Grouper:
    return pd.Grouper(key="date", freq=WEEK_FREQ, label="right", closed="right")


def _period_bounds(period_end: pd.Timestamp) -> tuple[date, date]:
    end = period_end.date()
    start = end - timedelta(days=6)
    return start, end


def load_financial(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {
        "date",
        "tenant_id",
        "revenue",
        "expenses",
        "cash_inflow",
        "cash_outflow",
        "outstanding_invoices",
    }
    missing = expected - set(df.columns)
    if missing:
        raise ValueError("financial CSV missing columns: %s" % sorted(missing))
    df["date"] = pd.to_datetime(df["date"], utc=False)
    return df.sort_values(["tenant_id", "date"]).reset_index(drop=True)


def load_sales(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"date", "tenant_id", "leads", "new_deals", "churn_rate"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError("sales CSV missing columns: %s" % sorted(missing))
    df["date"] = pd.to_datetime(df["date"], utc=False)
    return df.sort_values(["tenant_id", "date"]).reset_index(drop=True)


def weekly_financial_wide(df: pd.DataFrame) -> pd.DataFrame:
    g = _week_grouper()
    grouped = df.groupby(["tenant_id", g], observed=True)

    agg_kwargs = {
        "_revenue": ("revenue", "sum"),
        "_expenses": ("expenses", "sum"),
        "_cash_in": ("cash_inflow", "sum"),
        "_cash_out": ("cash_outflow", "sum"),
        "_outstanding": ("outstanding_invoices", "max"),
    }
    if "profit" in df.columns:
        agg_kwargs["_profit"] = ("profit", "sum")

    wide = grouped.agg(**agg_kwargs).reset_index()
    wide = wide.loc[pd.notna(wide["date"])]

    profit_from_ledger = "_profit" in wide.columns

    bounds = wide["date"].map(_period_bounds)
    wide["period_start"] = bounds.map(lambda x: x[0])
    wide["period_end"] = bounds.map(lambda x: x[1])
    wide = wide.drop(columns=["date"])

    wide["burn_rate"] = wide["_expenses"].astype(np.float64)
    wide["cash_flow"] = (wide["_cash_in"] - wide["_cash_out"]).astype(np.float64)
    wide["outstanding_invoices"] = wide["_outstanding"].astype(np.float64)

    wide["weekly_revenue"] = wide["_revenue"].astype(np.float64)
    revenue = wide["weekly_revenue"]
    if profit_from_ledger:
        wide["weekly_profit"] = wide["_profit"].astype(np.float64)
    else:
        wide["weekly_profit"] = (wide["_revenue"] - wide["_expenses"]).astype(np.float64)

    wide["_revenue_prev"] = wide.groupby("tenant_id")["_revenue"].shift(1)
    denom = wide["_revenue_prev"].replace({0.0: np.nan})
    wide["revenue_growth"] = (revenue - wide["_revenue_prev"]) / denom
    mask_first = wide["_revenue_prev"].isna()
    wide.loc[mask_first, "revenue_growth"] = np.nan

    wide = wide.sort_values(["tenant_id", "period_end"])
    by_tenant = wide.groupby("tenant_id", sort=False)
    wide["cumulative_revenue"] = by_tenant["weekly_revenue"].cumsum()
    wide["cumulative_expenses"] = by_tenant["burn_rate"].cumsum()
    wide["cumulative_profit"] = by_tenant["weekly_profit"].cumsum()

    drop_internal = ["_revenue", "_expenses", "_cash_in", "_cash_out", "_outstanding"]
    if profit_from_ledger:
        drop_internal.append("_profit")
    wide = wide.drop(columns=drop_internal + ["_revenue_prev"])

    return wide.reset_index(drop=True)


def financial_wide_to_long(
    df: pd.DataFrame,
    run_id: str,
    trace_id: str,
    computed_at: pd.Timestamp,
) -> pd.DataFrame:
    defs = [
        ("burn_rate", "currency"),
        ("cash_flow", "currency"),
        ("cumulative_expenses", "currency"),
        ("cumulative_profit", "currency"),
        ("cumulative_revenue", "currency"),
        ("outstanding_invoices", "currency"),
        ("revenue_growth", "ratio"),
        ("weekly_profit", "currency"),
        ("weekly_revenue", "currency"),
    ]
    metric_names = [m for m, _ in defs]
    long = df.melt(
        id_vars=["tenant_id", "period_start", "period_end"],
        value_vars=metric_names,
        var_name="metric_name",
        value_name="metric_value",
    )
    units = dict(defs)
    long["metric_unit"] = long["metric_name"].map(units)
    long["period_grain"] = "weekly"
    long["domain"] = "financial"
    long["computed_at"] = computed_at.isoformat().replace("+00:00", "Z")
    long["run_id"] = run_id
    long["trace_id"] = trace_id
    return long[GOLD_COLUMNS].sort_values(
        ["tenant_id", "period_end", "metric_name"]
    )


def weekly_sales_wide(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    churn = work["churn_rate"].astype(np.float64)
    leads_raw = work["leads"].astype(np.float64)
    work["_churn_weighted"] = churn * leads_raw

    g = _week_grouper()
    grouped = work.groupby(["tenant_id", g], observed=True)

    wide = grouped.agg(
        leads_week=("leads", "sum"),
        deals_week=("new_deals", "sum"),
        churn_weighted_week=("_churn_weighted", "sum"),
    ).reset_index()

    wide = wide.loc[pd.notna(wide["date"])]

    leads = wide["leads_week"].astype(np.float64)
    deals = wide["deals_week"].astype(np.float64)
    churn_w = wide["churn_weighted_week"].astype(np.float64)

    bounds = wide["date"].map(_period_bounds)
    wide["period_start"] = bounds.map(lambda x: x[0])
    wide["period_end"] = bounds.map(lambda x: x[1])

    wide["incoming_leads"] = leads
    wide["deal_velocity"] = deals
    wide["conversion_rate"] = np.where(leads != 0.0, deals / leads, np.nan)
    wide["churn_rate"] = np.where(leads != 0.0, churn_w / leads, np.nan)

    wide = wide.drop(
        columns=["date", "leads_week", "deals_week", "churn_weighted_week"],
    )

    return wide.sort_values(["tenant_id", "period_end"]).reset_index(drop=True)


def sales_wide_to_long(
    df: pd.DataFrame,
    run_id: str,
    trace_id: str,
    computed_at: pd.Timestamp,
) -> pd.DataFrame:
    defs = [
        ("incoming_leads", "count"),
        ("conversion_rate", "ratio"),
        ("deal_velocity", "count"),
        ("churn_rate", "ratio"),
    ]
    metric_names = [m for m, _ in defs]
    long = df.melt(
        id_vars=["tenant_id", "period_start", "period_end"],
        value_vars=metric_names,
        var_name="metric_name",
        value_name="metric_value",
    )
    units = dict(defs)
    long["metric_unit"] = long["metric_name"].map(units)
    long["period_grain"] = "weekly"
    long["domain"] = "sales_crm"
    long["computed_at"] = computed_at.isoformat().replace("+00:00", "Z")
    long["run_id"] = run_id
    long["trace_id"] = trace_id
    return long[GOLD_COLUMNS].sort_values(
        ["tenant_id", "period_end", "metric_name"]
    )


def empty_gold_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=GOLD_COLUMNS)


def build_kpi_dataframe(
    financial_path: Path,
    sales_path: Path,
    run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> pd.DataFrame:
    computed_at = pd.Timestamp.now(tz="UTC").floor("ms")
    run_id = run_id or str(uuid.uuid4())
    trace_id = trace_id or str(uuid.uuid4())

    logger.info(
        "Loading financial %s sales %s (week rollup %s, label right week-end)",
        financial_path,
        sales_path,
        WEEK_FREQ,
    )
    financial_raw = load_financial(financial_path)
    sales_raw = load_sales(sales_path)

    fin_wide = weekly_financial_wide(financial_raw)
    sal_wide = weekly_sales_wide(sales_raw)

    logger.info(
        "Weekly rows: financial=%s sales=%s tenants_fin=%s tenants_sales=%s",
        len(fin_wide),
        len(sal_wide),
        fin_wide["tenant_id"].nunique() if not fin_wide.empty else 0,
        sal_wide["tenant_id"].nunique() if not sal_wide.empty else 0,
    )

    parts = []
    if not fin_wide.empty:
        parts.append(financial_wide_to_long(fin_wide, run_id, trace_id, computed_at))
    if not sal_wide.empty:
        parts.append(sales_wide_to_long(sal_wide, run_id, trace_id, computed_at))

    if not parts:
        return empty_gold_frame()

    out = pd.concat(parts, ignore_index=True)

    duplicates = out.duplicated(
        subset=["tenant_id", "period_end", "domain", "metric_name"],
        keep=False,
    )
    if duplicates.any():
        raise ValueError("Duplicate KPI keys in output dataframe")

    return out.sort_values(
        ["domain", "tenant_id", "period_end", "metric_name"]
    ).reset_index(drop=True)


def main() -> None:
    financial = DEFAULT_FINANCIAL
    sales = DEFAULT_SALES
    output_dir = DEFAULT_OUTPUT_DIR
    output_name = "gold_kpi_snapshots_local.csv"
    run_id = "0"
    trace_id = "0"

    kpis = build_kpi_dataframe(
        financial_path=financial,
        sales_path=sales,
        run_id=run_id,
        trace_id=trace_id,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / output_name
    kpis.to_csv(out_path, index=False)
    logger.info(
        "Wrote %s rows to %s (run_id=%s trace_id=%s)",
        len(kpis),
        out_path,
        kpis.loc[0, "run_id"] if len(kpis) else run_id,
        kpis.loc[0, "trace_id"] if len(kpis) else trace_id,
    )


if __name__ == "__main__":
    main()
