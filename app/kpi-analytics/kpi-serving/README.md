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

The KPI Serving API is also exposed as an MCP server so that ADK agents can call KPI tools directly
without needing to construct HTTP requests themselves.

`fastapi-mcp` wraps the selected FastAPI route operations into MCP-callable tools using the
existing OpenAPI schema. No separate MCP server process is needed — the `/mcp` endpoint is
mounted on the same port as the REST API.

### MCP tools exposed

| Tool | Maps to REST endpoint |
|---|---|
| `list_kpi_domains` | `GET /kpis/{tenant_id}/domains` |
| `list_kpi_metrics` | `GET /kpis/{tenant_id}/metrics` |
| `get_latest_kpis` | `GET /kpis/{tenant_id}/latest` |
| `get_latest_kpi_single` | `GET /kpis/{tenant_id}/latest/{domain}/{metric_name}` |
| `get_kpi_history` | `GET /kpis/{tenant_id}/metrics/{domain}/{metric_name}/history` |

### What was added

- `fastapi-mcp>=0.3.0` added to `requirements.txt`
- MCP setup added to `main.py`: initialises `FastApiMCP` and mounts it at `/mcp`

The Operational Intelligence agents connect to this endpoint via `McpToolset` with
`StreamableHTTPConnectionParams`. The MCP URL is passed in via the `KPI_MCP_URL` environment
variable in the orchestrator service.

## Health

`GET /health` returns `{"status":"ok"}`.
