from typing import Dict, List

import functions_framework
import pandas as pd
from cloudevents.http import CloudEvent
from google.cloud import storage, bigquery, pubsub_v1
import uuid

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

def insert_to_bigquery(rows: List[Dict]) -> bool:
    """Insert KPI rows into BigQuery."""
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

def compute_financial_kpis(df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    burn_rate = df["expenses"].mean()
    cash_flow = df["cash_inflow"].sum() - df["cash_outflow"].sum()
    revenue_growth = df["revenue"].pct_change().mean() if not df["revenue"].empty else 0.0
    outstanding_invoices = df["outstanding_invoices"].max()

    kpi_rows = [
        {"metric_name": "burn_rate", "metric_value": burn_rate, "metric_unit": "currency"},
        {"metric_name": "cash_flow", "metric_value": cash_flow, "metric_unit": "currency"},
        {"metric_name": "revenue_growth", "metric_value": revenue_growth, "metric_unit": "ratio"},
        {"metric_name": "outstanding_invoices", "metric_value": outstanding_invoices, "metric_unit": "currency"}
    ]

    result_df = pd.DataFrame(kpi_rows)

    result_df["metric_value"] = result_df["metric_value"].round(9)
    
    result_df["tenant_id"] = TENANT_ID
    result_df["domain"] = "financial"
    result_df["period_start"] = "2026-04-01"  # Placeholder
    result_df["period_end"] = "2026-04-30"    # Placeholder
    result_df["period_grain"] = "monthly"     # Placeholder
    result_df["computed_at"] = pd.Timestamp.now(tz='UTC').isoformat()
    result_df["run_id"] = run_id
    result_df["trace_id"] = "123"             # Placeholder

    column_order = [
        "tenant_id", "period_start", "period_end", "period_grain", 
        "domain", "metric_name", "metric_value", "metric_unit", 
        "computed_at", "run_id", "trace_id"
    ]
    
    return result_df[column_order]

@functions_framework.cloud_event
def compute_kpis(cloud_event: CloudEvent):
    # Load data from GCS
    bucket_name = cloud_event.data["bucket"]
    object_path = cloud_event.data["name"]
    run_id = str(uuid.uuid4())

    if not object_path.endswith("ready.json"):
        print(f"Ignoring non-ready file: {object_path}")
        return "Ignored non-ready file", 200

    print("Loading CSV data from GCS...")
    try:
        df = load_csv_from_gcs(bucket_name, object_path.replace("ready.json", FINANCIAL_CSV))
        print(f"Loaded data with {len(df)} rows from GCS")
    except Exception as e:
        print(f"Error loading CSV from GCS: {e}")
        return "Error loading data", 500

    # Compute financial KPIs
    print("Computing financial KPIs...")
    try:
        kpi_df = compute_financial_kpis(df, run_id)
        print(f"Computed KPIs:\n{kpi_df}")
    except Exception as e:
        print(f"Error computing KPIs: {e}")
        return "Error computing KPIs", 500
    
    # Insert KPIs into BigQuery
    print("Inserting KPIs into BigQuery...")
    if not insert_to_bigquery(kpi_df.to_dict(orient="records")):
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