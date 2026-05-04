from typing import Dict, List

import functions_framework
import pandas as pd
from cloudevents.http import CloudEvent
from google.cloud import storage, bigquery, pubsub_v1
import uuid
from datetime import datetime

# Run in kpi-compute folder:
# gcloud functions deploy compute_kpis --runtime python311 --region=us-central1 --gen2 --entry-point=compute_kpis --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" --trigger-event-filters="bucket=pulse-demo-bronze" --trigger-location=us --allow-unauthenticated

storage_client = storage.Client()
bq_client = bigquery.Client()
publisher = pubsub_v1.PublisherClient()

PROJECT_ID = "ada26-pulse-project"
TOPIC_PATH = publisher.topic_path(PROJECT_ID, "kpis-computed")
BQ_TABLE_ID = f"{PROJECT_ID}.kpi_analytics_gold.gold_kpi_snapshots"
TENANT_ID = "pulse-demo"
FINANCIAL_CSV = "financial_clean.csv"
SALES_MARKETING_CSV = "sales_marketing_clean.csv"


def delete_all_rows_from_bigquery():
    query = f"DELETE FROM `{BQ_TABLE_ID}` WHERE tenant_id = '{TENANT_ID}'"
    try:
        bq_client.query(query).result()
        print(f"Deleted existing rows for tenant_id={TENANT_ID} from BigQuery")
        return True
    except Exception as e:
        print(f"Error deleting rows from BigQuery: {e}")
        return False


def insert_to_bigquery(rows: List[Dict]) -> bool:
    try:
        errors = bq_client.insert_rows_json(BQ_TABLE_ID, rows)
        if errors:
            print(f"BigQuery insert errors: {errors}")
            return False
        print(f"Successfully inserted {len(rows)} rows to BigQuery")
        return True
    except Exception as e:
        print(f"Error inserting to BigQuery: {e}")
        return False


def load_csv_from_gcs(bucket_name: str, object_path: str) -> pd.DataFrame:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_path)
    return pd.read_csv(blob.open("r"))


def format_to_gold(res, freq_code, freq_label, domain, unit_map):
    # Define Periods
    res = res.reset_index()
    res.rename(columns={"date": "period_end"}, inplace=True)

    if freq_code == "W":
        res["period_start"] = res["period_end"] - pd.Timedelta(days=6)
    else:
        res["period_start"] = res["period_end"].dt.to_period("M").dt.start_time

    # Melt to Long Format
    long_df = res.melt(
        id_vars=["period_start", "period_end"],
        var_name="metric_name",
        value_name="metric_value",
    )

    # Replace inf and NaN with zero
    long_df["metric_value"] = (
        long_df["metric_value"].replace([float("inf"), float("-inf")], 0).fillna(0)
    )

    # Add Metadata
    long_df["tenant_id"] = "pulse-demo"
    long_df["period_grain"] = freq_label
    long_df["domain"] = domain
    long_df["computed_at"] = datetime.now()
    long_df["run_id"] = str(uuid.uuid4())
    long_df["metric_unit"] = long_df["metric_name"].map(unit_map)

    # Clean dates for BigQuery
    for col in ["period_start", "period_end"]:
        long_df[col] = long_df[col].dt.strftime("%Y-%m-%d")
    long_df["computed_at"] = long_df["computed_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return long_df


def get_financial_kpis(df, freq_code, freq_label):
    df["date"] = pd.to_datetime(df["date"])

    kpis = df.resample(freq_code, on="date").agg(
        {
            "expenses": "sum",
            "revenue": "sum",
            "cash_inflow": "sum",
            "cash_outflow": "sum",
            "outstanding_invoices": "max",
        }
    )

    res = pd.DataFrame(index=kpis.index)
    res["burn_rate"] = kpis["expenses"]
    res["cash_flow"] = kpis["cash_inflow"] - kpis["cash_outflow"]
    res["revenue_growth"] = kpis["revenue"].pct_change().fillna(0)
    res["outstanding_invoices"] = kpis["outstanding_invoices"]

    unit_map = {
        "revenue_growth": "ratio",
        "burn_rate": "currency",
        "cash_flow": "currency",
        "outstanding_invoices": "currency",
    }

    return format_to_gold(res, freq_code, freq_label, "financial", unit_map)


def get_sales_marketing_kpis(df, freq_code, freq_label):
    df["date"] = pd.to_datetime(df["date"])
    df["churn_volume"] = df["churn_rate"] * df.get("leads", 0)

    kpis = df.resample(freq_code, on="date").agg(
        {"leads": "sum", "new_deals": "sum", "churn_volume": "sum"}
    )

    res = pd.DataFrame(index=kpis.index)
    res["incoming_leads"] = kpis["leads"]
    res["conversion_rate"] = (kpis["new_deals"] / kpis["leads"]).fillna(0)
    res["deal_velocity"] = kpis["new_deals"]
    res["churn_rate"] = (kpis["churn_volume"] / kpis["leads"]).fillna(0)

    unit_map = {
        "incoming_leads": "count",
        "conversion_rate": "ratio",
        "deal_velocity": "count",
        "churn_rate": "ratio",
    }

    return format_to_gold(res, freq_code, freq_label, "sales_crm", unit_map)


@functions_framework.cloud_event
def compute_kpis(cloud_event: CloudEvent):
    # Load data from GCS
    bucket_name = cloud_event.data["bucket"]
    object_path = cloud_event.data["name"]

    if not object_path.endswith("ready.json"):
        print(f"Ignoring non-ready file: {object_path}")
        return "Ignored non-ready file", 200

    print("Loading CSV data from GCS...")
    try:
        financial_data = load_csv_from_gcs(
            bucket_name, object_path.replace("ready.json", FINANCIAL_CSV)
        )
        sales_marketing_data = load_csv_from_gcs(
            bucket_name, object_path.replace("ready.json", SALES_MARKETING_CSV)
        )
        print(f"Loaded data with {len(financial_data)} rows from GCS")
    except Exception as e:
        print(f"Error loading CSV from GCS: {e}")
        return "Error loading data", 500

    # Compute financial KPIs
    print("Computing financial KPIs...")
    try:
        # Generate and combine
        weekly_financial = get_financial_kpis(financial_data, "W", "weekly")
        monthly_financial = get_financial_kpis(financial_data, "ME", "monthly")
        weekly_sales_marketing = get_sales_marketing_kpis(
            sales_marketing_data, "W", "weekly"
        )
        monthly_sales_marketing = get_sales_marketing_kpis(
            sales_marketing_data, "ME", "monthly"
        )
        gold_kpi_snapshots = pd.concat(
            [
                weekly_financial,
                monthly_financial,
                weekly_sales_marketing,
                monthly_sales_marketing,
            ],
            ignore_index=True,
        )
        print(f"Computed {len(gold_kpi_snapshots)} KPI rows")
    except Exception as e:
        print(f"Error computing KPIs: {e}")
        return "Error computing KPIs", 500

    # Delete existing rows
    print("Deleting existing KPI rows from BigQuery...")
    if not delete_all_rows_from_bigquery():
        print("Failed to delete existing KPI rows from BigQuery")
        return "Error deleting existing KPIs from BigQuery", 500

    # Insert KPIs into BigQuery
    print("Inserting KPIs into BigQuery...")
    if not insert_to_bigquery(gold_kpi_snapshots.to_dict(orient="records")):
        print("Failed to insert KPIs into BigQuery")
        return "Error inserting KPIs into BigQuery", 500

    print("Successfully inserted KPIs into BigQuery")

    # Publish message to Pub/Sub
    try:
        publisher.publish(TOPIC_PATH, b"KPI computation completed", tenant_id=TENANT_ID)
        print("Published KPI computation completion message to Pub/Sub")
    except Exception as e:
        print(f"Error publishing to Pub/Sub: {e}")
        return "Error publishing to Pub/Sub", 500

    return "KPI computation completed", 200
