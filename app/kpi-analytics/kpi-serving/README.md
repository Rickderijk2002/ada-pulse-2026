# KPI Serving API (`kpi-serving`)

Read-only FastAPI service over the BigQuery gold KPI table produced by [`kpi-compute`](../kpi-compute/main.py).

## Prerequisites

- Python 3.11+
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) with permission to query the gold table (`gcloud auth application-default login`)

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `BQ_TABLE_ID` | `ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots` | Fully qualified BigQuery table `project.dataset.table` |
| `ALLOWED_TENANT_ID` | `pulse-demo` | Only path `tenant_id` equal to this value is accepted |
| `HISTORY_DEFAULT_LIMIT` | `12` | Default `limit` for history endpoint |
| `HISTORY_MAX_LIMIT` | `52` | Maximum `limit` for history (cap) |

Variable names match Pydantic field names (`history_default_limit`) or use uppercase env style as supported by `pydantic-settings` (`HISTORY_DEFAULT_LIMIT`).

## Local run

```bash
cd app/kpi-analytics/kpi-serving
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BQ_TABLE_ID=ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots
uvicorn main:app --reload --port 8080
```

Interactive OpenAPI: <http://127.0.0.1:8080/docs>

Example calls (tenant must match `ALLOWED_TENANT_ID`):

```bash
curl -s http://127.0.0.1:8080/kpis/pulse-demo/domains | jq .
curl -s "http://127.0.0.1:8080/kpis/pulse-demo/metrics?domain=financial" | jq .
curl -s "http://127.0.0.1:8080/kpis/pulse-demo/latest?domain=sales_crm" | jq .
curl -s "http://127.0.0.1:8080/kpis/pulse-demo/latest/financial/weekly_revenue" | jq .
curl -s "http://127.0.0.1:8080/kpis/pulse-demo/metrics/financial/weekly_revenue/history?limit=8" | jq .
```

Wrong tenant returns `404 Tenant not found`.

## Docker

```bash
cd app/kpi-analytics/kpi-serving
docker build -t kpi-serving:local .
docker run --rm -p 8080:8080 \
  -e BQ_TABLE_ID=ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots \
  -e GOOGLE_APPLICATION_CREDENTIALS=/key.json \
  -v ~/.config/gcloud/application_default_credentials.json:/key.json:ro \
  kpi-serving:local
```

Adjust credentials mounting to match your setup; Cloud Run normally uses the service account instead of mounting ADC.

## Deploy to Cloud Run (outline)

Example (replace region, repo, image):

```bash
gcloud run deploy pulse-kpi-serving \
  --source . \
  --region europe-west4 \
  --allow-unauthenticated \
  --service-account YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com \
  --set-env-vars BQ_TABLE_ID=ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots \
  --set-env-vars ALLOWED_TENANT_ID=pulse-demo
```

IAM for the runtime service account:

- `roles/bigquery.jobUser` on the project (or appropriate scope where jobs run)
- `roles/bigquery.dataViewer` on dataset `kpi_analytics_gold` (or the `gold_kpi_snapshots` table)

## MCP integration

Agents should call HTTP only; MCP tools wrap these routes. Responses are typed in OpenAPI for stable JSON shapes.

## Health

`GET /health` returns `{"status":"ok"}`.
