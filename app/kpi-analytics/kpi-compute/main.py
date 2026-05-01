from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Optional

import functions_framework
import numpy as np
import pandas as pd
from cloudevents.http import CloudEvent
from google.cloud import bigquery, pubsub_v1, storage

# gcloud functions deploy compute_kpis --runtime python311 --region=us-central1 --gen2 --entry-point=compute_kpis --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" --trigger-event-filters="bucket=pulse-demo-bronze" --trigger-location=us --allow-unauthenticated

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

storage_client = storage.Client()
bq_client = bigquery.Client()
publisher = pubsub_v1.PublisherClient()

PROJECT_ID = "ada26-pulse-project"
TOPIC_PATH = publisher.topic_path(PROJECT_ID, "kpis-computed")
BQ_TABLE_ID = f"{PROJECT_ID}.kpi_analytics_gold.gold_kpi_snapshots"
TENANT_ID = "pulse-demo"
FINANCIAL_CSV = "financial_clean.csv"
SALES_MARKETING_CSV = "sales_marketing_clean.csv"
READY_MARKER = "ready.json"

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

BQ_SCHEMA = [
    bigquery.SchemaField("tenant_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("period_start", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("period_end", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("period_grain", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("domain", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("metric_value", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("metric_unit", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("computed_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("trace_id", "STRING", mode="REQUIRED"),
]


def read_csv_from_gcs(bucket_name: str, blob_path: str) -> pd.DataFrame:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    with blob.open("r") as fh:
        return pd.read_csv(fh)


def _week_grouper() -> pd.Grouper:
    return pd.Grouper(key="date", freq=WEEK_FREQ, label="right", closed="right")


def _period_bounds(period_end: pd.Timestamp) -> tuple[date, date]:
    end = period_end.date()
    start = end - timedelta(days=6)
    return start, end


def _validate_financial(df: pd.DataFrame) -> pd.DataFrame:
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
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], utc=False)
    return out.sort_values(["tenant_id", "date"]).reset_index(drop=True)


def _validate_sales(df: pd.DataFrame) -> pd.DataFrame:
    expected = {"date", "tenant_id", "leads", "new_deals", "churn_rate"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError("sales CSV missing columns: %s" % sorted(missing))
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], utc=False)
    return out.sort_values(["tenant_id", "date"]).reset_index(drop=True)


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
        wide["weekly_profit"] = (wide["_revenue"] - wide["_expenses"]).astype(
            np.float64
        )

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
    long["computed_at"] = computed_at
    long["run_id"] = run_id
    long["trace_id"] = trace_id
    return long[GOLD_COLUMNS].sort_values(["tenant_id", "period_end", "metric_name"])


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
    long["computed_at"] = computed_at
    long["run_id"] = run_id
    long["trace_id"] = trace_id
    return long[GOLD_COLUMNS].sort_values(["tenant_id", "period_end", "metric_name"])


def _empty_gold_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=GOLD_COLUMNS)


def build_kpi_dataframe(
    financial_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> pd.DataFrame:
    computed_at = pd.Timestamp.now(tz="UTC").floor("ms")
    run_id = run_id or str(uuid.uuid4())
    trace_id = trace_id or str(uuid.uuid4())

    financial_raw = _validate_financial(financial_df)
    sales_raw = _validate_sales(sales_df)

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
        return _empty_gold_frame()

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


def write_kpis_to_bigquery(kpis: pd.DataFrame) -> None:
    if kpis.empty:
        raise ValueError("Refusing to truncate gold table with empty KPI frame")

    payload = kpis.copy()
    payload["period_start"] = pd.to_datetime(payload["period_start"]).dt.date
    payload["period_end"] = pd.to_datetime(payload["period_end"]).dt.date
    payload["computed_at"] = pd.to_datetime(payload["computed_at"], utc=True)
    payload["metric_value"] = payload["metric_value"].astype(np.float64)

    job_config = bigquery.LoadJobConfig(
        schema=BQ_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(field="period_end"),
        clustering_fields=["tenant_id", "metric_name"],
    )

    logger.info(
        "Loading %s KPI rows into %s (WRITE_TRUNCATE)", len(payload), BQ_TABLE_ID
    )
    load_job = bq_client.load_table_from_dataframe(
        payload,
        BQ_TABLE_ID,
        job_config=job_config,
    )
    load_job.result()
    logger.info("BigQuery load job completed: %s", load_job.job_id)


def publish_kpis_computed(run_id: str, trace_id: str) -> None:
    publisher.publish(
        TOPIC_PATH,
        b"KPI computation completed",
        tenant_id=TENANT_ID,
        run_id=run_id,
        trace_id=trace_id,
    )
    logger.info("Published kpis-computed (run_id=%s trace_id=%s)", run_id, trace_id)


@functions_framework.cloud_event
def compute_kpis(cloud_event: CloudEvent):
    bucket_name = cloud_event.data["bucket"]
    object_path = cloud_event.data["name"]

    if not object_path.endswith(READY_MARKER):
        logger.info("Ignoring non-ready file: %s", object_path)
        return "Ignored non-ready file", 200

    run_prefix = object_path[: -len(READY_MARKER)]
    run_id = str(uuid.uuid4())
    trace_id = cloud_event["id"] if "id" in cloud_event else str(uuid.uuid4())

    logger.info(
        "Starting KPI run (bucket=%s prefix=%s run_id=%s trace_id=%s)",
        bucket_name,
        run_prefix,
        run_id,
        trace_id,
    )

    try:
        financial_df = read_csv_from_gcs(bucket_name, run_prefix + FINANCIAL_CSV)
        sales_df = read_csv_from_gcs(bucket_name, run_prefix + SALES_MARKETING_CSV)
        logger.info(
            "Loaded CSVs from GCS (financial_rows=%s sales_rows=%s)",
            len(financial_df),
            len(sales_df),
        )
    except Exception as exc:
        logger.exception("Error loading CSVs from GCS: %s", exc)
        return "Error loading data", 500

    try:
        kpis = build_kpi_dataframe(
            financial_df=financial_df,
            sales_df=sales_df,
            run_id=run_id,
            trace_id=trace_id,
        )
        logger.info("Built KPI frame rows=%s", len(kpis))
    except Exception as exc:
        logger.exception("Error computing KPIs: %s", exc)
        return "Error computing KPIs", 500

    try:
        write_kpis_to_bigquery(kpis)
    except Exception as exc:
        logger.exception("Error loading KPIs to BigQuery: %s", exc)
        return "Error inserting KPIs into BigQuery", 500

    try:
        publish_kpis_computed(run_id=run_id, trace_id=trace_id)
    except Exception as exc:
        logger.exception("Error publishing to Pub/Sub: %s", exc)
        return "Error publishing to Pub/Sub", 500

    return "KPI computation completed", 200
