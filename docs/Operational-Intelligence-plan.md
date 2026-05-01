# Operational Intelligence GCP Build Plan

## 1. Purpose

This document defines the implementation plan for the Operational Intelligence domain of the Pulse platform, based on the current repository state in `ada-pulse-2026.zip`.

The implementation up to KPI & Analytics is already partly available in the project. Therefore, this plan does not assume a greenfield setup. It extends the existing GCS to BigQuery to Pub/Sub pipeline with the missing Operational Intelligence layer.

The target flow is:

```text
GCS ingest files
→ KPI Computation Cloud Function
→ BigQuery Gold Layer
→ kpis-computed Pub/Sub topic
→ Operational Intelligence Orchestrator on Cloud Run
→ Financial Intelligence Agent
→ Sales & CRM Intelligence Agent
→ Insight Synthesis Agent
→ insights-ready Pub/Sub topic
→ Reporting & Delivery
```

Operational Intelligence consumes KPI data. It does not compute KPIs, ingest source data, or write directly to the KPI Gold Layer.

## 2. Current Repository State

The uploaded project ZIP contains the following relevant implementation state.

### 2.1 Existing project structure

```text
ada-pulse-2026/
  app/
    infra/
      data-ingest-uploader/
        upload_ingest_to_gcs.py

    kpi-analytics/
      kpi-compute/
        main.py
        requirements.txt
      mock_data.py

    operational-intelligence/
      test.py

    reporting-delivery/
      test.py

  data/
    ingest/
      financial_clean.csv
      sales_marketing_clean.csv

    kpi/
      gold_kpi_snapshots_local.csv
      plots/
        trends_financial.png
        trends_sales_crm.png

  scripts/
    compute_kpis_local.py
    create_mock_data.py
    plot_kpi_trends.py

  docs/
    KPI-Analytics-plan.md
    Assignment2-Outline.md
    assignment2-Gilbert.md
```

### 2.2 Existing GCS ingest uploader

The file below already uploads the ingest-ready CSV files to GCS and writes a `ready.json` marker:

```text
app/infra/data-ingest-uploader/upload_ingest_to_gcs.py
```

Current behavior:

```text
project_id = ada26-pulse-project
bucket_name = pulse-demo-bronze
remote prefix = ingest/{timestamp}/
uploaded files:
  financial_clean.csv
  sales_marketing_clean.csv
  ready.json
```

The marker file is important because the KPI Cloud Function only starts the KPI computation when the finalized GCS object path ends with:

```text
ready.json
```

### 2.3 Existing KPI Computation Cloud Function

The file below contains the KPI computation implementation:

```text
app/kpi-analytics/kpi-compute/main.py
```

Current behavior:

```text
1. Triggered by GCS object finalized event.
2. Ignores files that are not ready.json.
3. Reads financial_clean.csv and sales_marketing_clean.csv from the same run prefix.
4. Computes weekly KPI values.
5. Writes the Gold Layer table to BigQuery.
6. Publishes a kpis-computed event to Pub/Sub.
```

Current constants in the implementation:

```text
PROJECT_ID = ada26-pulse-project
BQ_TABLE_ID = ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots
TOPIC = kpis-computed
TENANT_ID = pulse-demo
FINANCIAL_CSV = financial_clean.csv
SALES_MARKETING_CSV = sales_marketing_clean.csv
READY_MARKER = ready.json
```

### 2.4 Existing BigQuery Gold Layer schema

The KPI Function writes to:

```text
ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots
```

Columns:

```text
tenant_id
period_start
period_end
period_grain
domain
metric_name
metric_value
metric_unit
computed_at
run_id
trace_id
```

The table is partitioned by:

```text
period_end
```

The table is clustered by:

```text
tenant_id
metric_name
```

### 2.5 Existing KPI metrics

Financial metrics currently produced by the implementation:

```text
burn_rate
cash_flow
cumulative_expenses
cumulative_profit
cumulative_revenue
outstanding_invoices
revenue_growth
weekly_profit
weekly_revenue
```

Sales and CRM metrics currently produced by the implementation:

```text
incoming_leads
conversion_rate
deal_velocity
churn_rate
```

For Operational Intelligence, the primary MVP metrics are:

```text
Financial:
  burn_rate
  cash_flow
  revenue_growth
  outstanding_invoices

Sales and CRM:
  incoming_leads
  conversion_rate
  deal_velocity
  churn_rate
```

The additional financial metrics can be used as supporting evidence in the Financial Intelligence Agent.

### 2.6 Existing kpis-computed event behavior

The current KPI Function publishes the Pub/Sub event as a plain message with attributes:

```python
publisher.publish(
    TOPIC_PATH,
    b"KPI computation completed",
    tenant_id=TENANT_ID,
    run_id=run_id,
    trace_id=trace_id,
)
```

This means the Operational Intelligence Pub/Sub handler must support this input format:

```text
message.data = "KPI computation completed"
message.attributes.tenant_id = pulse-demo
message.attributes.run_id = <kpi-run-id>
message.attributes.trace_id = <trace-id>
```

Recommended improvement:

```text
Publish JSON payload in message.data as well as attributes.
```

However, the Orchestrator should first support the current implementation to avoid breaking the existing pipeline.


## 3. Lab 6 Implementation References

The implementation should explicitly reuse the patterns from the Lab 6 ZIP. The lab examples are not copied blindly, but used as technical templates for the Operational Intelligence implementation.

### 3.1 Reference mapping

```text
Operational Intelligence component          Lab 6 reference
--------------------------------------------------------------------------------
Basic ADK agent structure                    lab6/agent1/agent1/agent.py
FastAPI wrapper for agent/API exposure       lab6/agent1/app.py
Agent with MCP tools                         lab6/agent1_with_mcp/agent1/agent.py
Standalone FastMCP server                    lab6/mcpserver1/weather_mcp_server.py
REST API exposed as MCP                      lab6/deliveryservice_mcpserver/app.py
Agent consuming an MCP-enabled service       lab6/deliveryservice_agents/deliveryserviceagent1/agent.py
ADK runtime and event-loop behavior          lab6/agent2/weather_agent2/weather_agent2.py
```

### 3.2 How each lab example is used

#### `lab6/agent1/agent1/agent.py`

Used as the base template for the Financial Intelligence Agent, Sales & CRM Intelligence Agent, and Insight Synthesis Agent.

Relevant pattern:

```text
LlmAgent(
  name=...,
  model=...,
  description=...,
  instruction=...,
  tools=[...]
)
```

Operational Intelligence adaptation:

```text
weather/time tools
→ KPI retrieval and analysis tools

general assistant instruction
→ strict business-insight instruction with JSON output contract
```

#### `lab6/agent1/app.py`

Used as the reference for exposing an agent through FastAPI.

Operational Intelligence adaptation:

```text
generic agent API
→ Cloud Run Orchestrator API

Required endpoints:
GET  /health
POST /pipeline/run
GET  /pipeline/{run_id}/status
POST /pubsub/kpis-computed
```

This example is especially relevant because the Orchestrator Agent must run as a Cloud Run service and receive HTTP requests from Pub/Sub push.

#### `lab6/agent1_with_mcp/agent1/agent.py`

Used as the reference for connecting ADK agents to an MCP server.

Operational Intelligence adaptation:

```text
MCP weather tools
→ KPI MCP tools

McpToolset(...)
→ KPI_MCP_URL based toolset

http://localhost:8000/mcp
→ https://YOUR_KPI_MCP_SERVICE_URL/mcp
```

This pattern is used by:

```text
Financial Intelligence Agent
Sales & CRM Intelligence Agent
```

#### `lab6/mcpserver1/weather_mcp_server.py`

Used as a reference for manually defining MCP tools with FastMCP.

Operational Intelligence adaptation:

```text
get_weather(...)
→ get_latest_kpis(...)

get_current_time(...)
→ get_kpi_history(...)
```

This approach is useful if the KPI MCP server is implemented manually as explicit Python tool functions.

#### `lab6/deliveryservice_mcpserver/app.py`

Used as the preferred reference for the KPI MCP server because the KPI Data Serving API is a REST service that should be exposed as MCP.

Operational Intelligence adaptation:

```text
Delivery REST API
→ KPI Data Serving API

delivery service MCP wrapper
→ KPI MCP server wrapper

REST endpoint
→ MCP tool
```

Target pattern:

```text
BigQuery Gold Layer
→ KPI Data Serving API
→ KPI MCP Server
→ ADK Agents
```

#### `lab6/deliveryservice_agents/deliveryserviceagent1/agent.py`

Used as the reference for an ADK agent consuming a domain-specific MCP-enabled service.

Operational Intelligence adaptation:

```text
delivery record management agent
→ KPI reasoning agent

delivery tools
→ KPI data tools
```

This example is relevant for verifying that the Financial and Sales agents correctly discover and call MCP tools.

#### `lab6/agent2/weather_agent2/weather_agent2.py`

Used as a conceptual reference for ADK runtime behavior.

Operational Intelligence adaptation:

```text
Runner → Agent → Event → Runner
→ Orchestrator → Sub-agent → Result → Synthesis → Pub/Sub output
```

This reference supports the explanation of how ADK executes the reasoning loop internally.

### 3.3 Lab-based implementation decisions

The Operational Intelligence implementation should follow these decisions based on Lab 6:

```text
1. Use ADK LlmAgent as the base structure for each reasoning agent.
2. Use FastAPI for Cloud Run exposure of the Orchestrator.
3. Use MCP tools for KPI data access rather than direct BigQuery access.
4. Use the REST-to-MCP pattern for wrapping the KPI Data Serving API.
5. Use MCP Inspector to test the KPI MCP server before connecting agents.
6. Run agents locally with `adk run` before deploying the Orchestrator to Cloud Run.
7. Keep strict JSON output instructions in each agent prompt.
```

### 3.4 Commands inherited from Lab 6

Local ADK agent run:

```bash
adk run agent_name
```

ADK web UI for local inspection:

```bash
adk web --port 8000
```

MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

FastAPI local run:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

## 4. Implementation Gap

The current repository contains a working basis for:

```text
GCS upload
KPI Cloud Function
BigQuery Gold Layer write
kpis-computed Pub/Sub publish
local KPI computation
```

The following parts are still missing or need to be built:

```text
1. KPI Data Serving API
2. KPI MCP server
3. Operational Intelligence Orchestrator
4. Financial Intelligence Agent
5. Sales & CRM Intelligence Agent
6. Insight Synthesis Agent
7. insights-ready Pub/Sub publisher
8. Cloud Run deployment for Operational Intelligence
9. end-to-end trace-aware logging
```

The Operational Intelligence plan should therefore start from the actual existing pipeline:

```text
GCS ready.json triggers KPI compute
KPI compute publishes kpis-computed
Operational Intelligence consumes kpis-computed
```

## 5. Target Architecture

```text
[pulse-demo-bronze GCS bucket]
        |
        | object finalized: ingest/{run_id}/ready.json
        v
[KPI Computation Cloud Function]
        |
        | writes
        v
[BigQuery: kpi_analytics_gold.gold_kpi_snapshots]
        |
        | publishes attributes tenant_id, run_id, trace_id
        v
[Pub/Sub topic: kpis-computed]
        |
        | push subscription
        v
[Cloud Run: operational-intelligence-orchestrator]
        |
        | calls
        v
[KPI MCP Server]
        |
        | wraps
        v
[KPI Data Serving API]
        |
        | queries
        v
[BigQuery Gold Layer]
        |
        v
[Financial Agent + Sales CRM Agent + Synthesis Agent]
        |
        | publishes JSON payload
        v
[Pub/Sub topic: insights-ready]
```

## 6. Required GCP Resources

### 5.1 Core variables

```bash
export PROJECT_ID="ada26-pulse-project"
export REGION="europe-west1"
export FUNCTION_REGION="us-central1"
export TRIGGER_LOCATION="us"

export TENANT_ID="pulse-demo"
export GCS_BUCKET="pulse-demo-bronze"

export KPI_GOLD_DATASET="kpi_analytics_gold"
export KPI_GOLD_TABLE="gold_kpi_snapshots"

export KPIS_COMPUTED_TOPIC="kpis-computed"
export INSIGHTS_READY_TOPIC="insights-ready"

export KPI_DATA_SERVICE="kpi-data-serving"
export KPI_MCP_SERVICE="kpi-mcp-server"
export OI_SERVICE="operational-intelligence-orchestrator"

export OI_SA="operational-intelligence-sa"
export OI_SUBSCRIPTION="orchestrator-kpis-computed-sub"
```

### 5.2 Required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable eventarc.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable generativelanguage.googleapis.com
```

## 7. Existing KPI Cloud Function Deployment

The existing file includes the following deployment comment:

```bash
gcloud functions deploy compute_kpis   --runtime python311   --region=us-central1   --gen2   --entry-point=compute_kpis   --trigger-event-filters="type=google.cloud.storage.object.v1.finalized"   --trigger-event-filters="bucket=pulse-demo-bronze"   --trigger-location=us   --allow-unauthenticated
```

Recommended refined version:

```bash
gcloud functions deploy compute_kpis   --runtime python311   --region "$FUNCTION_REGION"   --gen2   --source app/kpi-analytics/kpi-compute   --entry-point compute_kpis   --trigger-event-filters="type=google.cloud.storage.object.v1.finalized"   --trigger-event-filters="bucket=${GCS_BUCKET}"   --trigger-location "$TRIGGER_LOCATION"   --set-env-vars PROJECT_ID="$PROJECT_ID",TENANT_ID="$TENANT_ID",KPIS_COMPUTED_TOPIC="$KPIS_COMPUTED_TOPIC"   --project "$PROJECT_ID"
```

Important note:

The current code uses hardcoded constants. Environment variables are recommended, but not strictly required for the current project state. If environment variables are added, `main.py` should be adjusted to read from `os.environ`.

## 8. KPI Data Serving API

Operational Intelligence needs a stable read interface for the Gold Layer. The current repository does not yet contain this service. It should be added before or alongside the MCP server.

### 7.1 Location

```text
app/kpi-analytics/kpi-data-serving/
  app.py
  requirements.txt
  Dockerfile
```

### 7.2 Responsibilities

```text
1. Query BigQuery Gold Layer.
2. Return latest KPI values by tenant and domain.
3. Return metric history by tenant, domain, and metric.
4. Return a full period snapshot if needed.
5. Hide BigQuery SQL from downstream agents.
```

### 7.3 Required endpoints

```text
GET /health
GET /kpis/{tenant_id}/domains
GET /kpis/{tenant_id}/latest?domain={domain}
GET /kpis/{tenant_id}/history?domain={domain}&metric_name={metric_name}&periods={periods}
GET /kpis/{tenant_id}/snapshot?period_end={YYYY-MM-DD}
GET /kpis/{tenant_id}/trends?domain={domain}&periods={periods}
```

### 7.4 Query behavior

Latest KPI endpoint:

```sql
SELECT
  tenant_id,
  period_start,
  period_end,
  period_grain,
  domain,
  metric_name,
  metric_value,
  metric_unit,
  computed_at,
  run_id,
  trace_id
FROM `ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots`
WHERE tenant_id = @tenant_id
  AND domain = @domain
  AND period_end = (
    SELECT MAX(period_end)
    FROM `ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots`
    WHERE tenant_id = @tenant_id
      AND domain = @domain
  )
ORDER BY metric_name;
```

History endpoint:

```sql
SELECT
  tenant_id,
  period_start,
  period_end,
  period_grain,
  domain,
  metric_name,
  metric_value,
  metric_unit,
  computed_at,
  run_id,
  trace_id
FROM `ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots`
WHERE tenant_id = @tenant_id
  AND domain = @domain
  AND metric_name = @metric_name
ORDER BY period_end DESC
LIMIT @periods;
```

### 7.5 Data Serving API dependencies

```text
fastapi
uvicorn[standard]
google-cloud-bigquery
pydantic
python-dotenv
```

### 7.6 Cloud Run deployment

```bash
gcloud run deploy "$KPI_DATA_SERVICE"   --source app/kpi-analytics/kpi-data-serving   --region "$REGION"   --set-env-vars PROJECT_ID="$PROJECT_ID",KPI_GOLD_TABLE="${PROJECT_ID}.${KPI_GOLD_DATASET}.${KPI_GOLD_TABLE}"   --allow-unauthenticated   --project "$PROJECT_ID"
```

## 9. KPI MCP Server

The KPI MCP server exposes the Data Serving API as agent-callable tools.

Primary Lab 6 references:

```text
lab6/mcpserver1/weather_mcp_server.py
lab6/deliveryservice_mcpserver/app.py
```

The first example shows how to define explicit FastMCP tools. The second example is the preferred pattern for this project because it demonstrates how a REST service can be exposed as MCP tools.

### 8.1 Location

```text
app/kpi-analytics/kpi-mcp-server/
  app.py
  requirements.txt
  Dockerfile
```

### 8.2 Lab example alignment

Use these examples from Lab 6:

```text
lab6/mcpserver1/weather_mcp_server.py
```

Useful for explicit FastMCP tool definitions.

```text
lab6/deliveryservice_mcpserver/app.py
```

Useful for wrapping REST functionality into MCP.

The KPI MCP server is closest to the REST to MCP conversion pattern:

```text
KPI Data Serving API
→ KPI MCP Server
→ ADK agents
```

### 8.3 Required MCP tools

```text
list_kpi_domains(tenant_id)
list_kpis_in_domain(tenant_id, domain)
get_latest_kpis(tenant_id, domain)
get_kpi_history(tenant_id, domain, metric_name, periods)
get_period_snapshot(tenant_id, period_end)
```

### 8.4 Tool implementation behavior

Each MCP tool should call the KPI Data Serving API.

Example mapping:

```text
get_latest_kpis(tenant_id, "financial")
→ GET /kpis/{tenant_id}/latest?domain=financial

get_kpi_history(tenant_id, "financial", "burn_rate", 6)
→ GET /kpis/{tenant_id}/history?domain=financial&metric_name=burn_rate&periods=6
```

### 8.5 MCP endpoint

Recommended HTTP endpoint:

```text
/mcp
```

### 8.6 Cloud Run deployment

```bash
gcloud run deploy "$KPI_MCP_SERVICE"   --source app/kpi-analytics/kpi-mcp-server   --region "$REGION"   --set-env-vars KPI_DATA_API_URL="https://YOUR_KPI_DATA_SERVICE_URL"   --allow-unauthenticated   --project "$PROJECT_ID"
```

## 10. Operational Intelligence Repository Structure

The current folder exists but only contains `test.py`. Extend it as follows:

```text
app/operational-intelligence/
  orchestrator-agent/
    app.py
    Dockerfile
    requirements.txt
    .env.example

    orchestrator/
      __init__.py
      pipeline.py
      pubsub_handler.py
      status_store.py

    agents/
      __init__.py

      financial_agent.py
      sales_crm_agent.py
      synthesis_agent.py

    shared/
      __init__.py
      schemas.py
      logging_utils.py
      pubsub.py
      tracing.py
      mcp_tools.py

    tests/
      test_pubsub_handler.py
      test_pipeline_mock.py
      test_synthesis.py
```

## 11. Operational Intelligence Cloud Run Service

### 10.1 Responsibilities

```text
1. Expose HTTP endpoints for health, manual run, status, and Pub/Sub push.
2. Decode the current kpis-computed Pub/Sub message format.
3. Run the Operational Intelligence pipeline.
4. Call Financial and Sales agents.
5. Call Synthesis agent.
6. Publish insights-ready to Pub/Sub.
7. Log every step with trace_id.
```

### 10.2 Required endpoints

```text
GET /health
POST /pipeline/run
GET /pipeline/{run_id}/status
POST /pubsub/kpis-computed
```

### 10.3 Manual run payload

```json
{
  "tenant_id": "pulse-demo",
  "trace_id": "trace-local-001",
  "run_id": "manual-run-001",
  "source_kpi_run_id": "kpi-run-local-001",
  "period_end": "2026-05-01"
}
```

### 10.4 Pub/Sub push input support

The current KPI Function publishes a non-JSON message with attributes. Therefore, the handler must support:

```json
{
  "message": {
    "data": "S1BJIGNvbXB1dGF0aW9uIGNvbXBsZXRlZA==",
    "attributes": {
      "tenant_id": "pulse-demo",
      "run_id": "kpi-run-123",
      "trace_id": "trace-123"
    },
    "messageId": "123456"
  },
  "subscription": "projects/ada26-pulse-project/subscriptions/orchestrator-kpis-computed-sub"
}
```

Required extraction logic:

```text
tenant_id = message.attributes.tenant_id
source_kpi_run_id = message.attributes.run_id
trace_id = message.attributes.trace_id
```

Fallback behavior:

```text
If attributes are absent, try to parse JSON from message.data.
If both formats fail, return HTTP 400 and log validation error.
```

## 12. Agent Design

Primary Lab 6 references:

```text
lab6/agent1/agent1/agent.py
lab6/agent1_with_mcp/agent1/agent.py
lab6/deliveryservice_agents/deliveryserviceagent1/agent.py
lab6/agent2/weather_agent2/weather_agent2.py
```

These examples should be used as implementation templates for the ADK agent structure, MCP tool connection, and local validation workflow.

### 12.1 Lab example alignment

Use these Lab 6 examples:

```text
lab6/agent1/agent1/agent.py
```

Reference for the basic ADK `LlmAgent` structure.

```text
lab6/agent1_with_mcp/agent1/agent.py
```

Reference for using an MCP server with an ADK agent.

```text
lab6/agent1/app.py
```

Reference for exposing an agent through FastAPI.

```text
lab6/agent2/weather_agent2/weather_agent2.py
```

Reference for understanding the ADK runtime event loop.

### 12.2 Financial Intelligence Agent

Purpose:

```text
Analyze financial KPI values and trends.
```

MCP calls:

```text
get_latest_kpis(tenant_id, domain="financial")
get_kpi_history(tenant_id, domain="financial", metric_name="burn_rate", periods=6)
get_kpi_history(tenant_id, domain="financial", metric_name="cash_flow", periods=6)
get_kpi_history(tenant_id, domain="financial", metric_name="revenue_growth", periods=6)
get_kpi_history(tenant_id, domain="financial", metric_name="outstanding_invoices", periods=6)
```

MVP rules:

```text
cash_flow < 0 → high severity
burn_rate increasing for at least 3 periods → medium severity
revenue_growth < 0 → medium severity
outstanding_invoices increasing → medium severity
cash_flow < 0 and outstanding_invoices increasing → high severity
```

Output contract:

```json
{
  "agent": "financial_intelligence_agent",
  "domain": "financial",
  "status": "success",
  "insights": [
    {
      "metric_name": "cash_flow",
      "severity": "high",
      "trend": "decreasing",
      "insight": "Cash flow has deteriorated compared with previous periods.",
      "recommendation": "Review short-term expenses and prioritize invoice collection.",
      "evidence": {
        "latest_value": -12000,
        "previous_value": 5000,
        "periods_observed": 6
      }
    }
  ]
}
```

### 12.3 Sales & CRM Intelligence Agent

Purpose:

```text
Analyze sales and CRM KPI values and trends.
```

MCP calls:

```text
get_latest_kpis(tenant_id, domain="sales_crm")
get_kpi_history(tenant_id, domain="sales_crm", metric_name="incoming_leads", periods=6)
get_kpi_history(tenant_id, domain="sales_crm", metric_name="conversion_rate", periods=6)
get_kpi_history(tenant_id, domain="sales_crm", metric_name="deal_velocity", periods=6)
get_kpi_history(tenant_id, domain="sales_crm", metric_name="churn_rate", periods=6)
```

MVP rules:

```text
conversion_rate decreasing for at least 3 periods → medium severity
deal_velocity decreasing → medium severity
churn_rate increasing → high severity
incoming_leads decreasing and conversion_rate decreasing → high severity
churn_rate increasing and deal_velocity decreasing → high severity
```

Output contract:

```json
{
  "agent": "sales_crm_intelligence_agent",
  "domain": "sales_crm",
  "status": "success",
  "insights": [
    {
      "metric_name": "conversion_rate",
      "severity": "medium",
      "trend": "decreasing",
      "insight": "Conversion rate decreased while lead volume remained stable.",
      "recommendation": "Review lead qualification and follow-up quality.",
      "evidence": {
        "latest_value": 0.14,
        "previous_value": 0.22,
        "periods_observed": 6
      }
    }
  ]
}
```

### 12.4 Insight Synthesis Agent

Purpose:

```text
Combine financial and sales insights into one normalized cross-domain insight payload.
```

Cross-domain rules:

```text
revenue_growth negative + churn_rate increasing → high severity
cash_flow negative + deal_velocity decreasing → high severity
burn_rate increasing + conversion_rate decreasing → high severity
outstanding_invoices increasing + incoming_leads decreasing → medium severity
```

Output contract:

```json
{
  "agent": "insight_synthesis_agent",
  "status": "success",
  "synthesized_insights": [
    {
      "domain": "cross_domain",
      "severity": "high",
      "risk_type": "compound_revenue_pressure",
      "insight": "Revenue growth is declining while churn is increasing, indicating a compound operational risk.",
      "recommendation": "Prioritize retention actions and short-term revenue protection measures.",
      "related_metrics": [
        "revenue_growth",
        "churn_rate"
      ]
    }
  ],
  "final_severity": "high"
}
```

## 13. insights-ready Output Event

The Orchestrator publishes this message to:

```text
insights-ready
```

Recommended payload:

```json
{
  "tenant_id": "pulse-demo",
  "trace_id": "trace-123",
  "run_id": "oi-run-123",
  "source_kpi_run_id": "kpi-run-123",
  "status": "completed",
  "financial_insights": [],
  "sales_crm_insights": [],
  "synthesized_insights": [],
  "final_severity": "high",
  "published_at": "2026-05-01T12:00:00Z"
}
```

Unlike the current `kpis-computed` event, this output should be published as JSON in `message.data`. Attributes may be added as well:

```text
tenant_id
run_id
trace_id
status
```

## 14. Service Account and IAM

### 14.1 Create service account

```bash
gcloud iam service-accounts create "$OI_SA"   --display-name="Operational Intelligence Orchestrator"   --project "$PROJECT_ID"
```

```bash
export OI_SA_EMAIL="${OI_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 14.2 Required roles

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="serviceAccount:${OI_SA_EMAIL}"   --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="serviceAccount:${OI_SA_EMAIL}"   --role="roles/pubsub.subscriber"

gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="serviceAccount:${OI_SA_EMAIL}"   --role="roles/run.invoker"

gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="serviceAccount:${OI_SA_EMAIL}"   --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="serviceAccount:${OI_SA_EMAIL}"   --role="roles/secretmanager.secretAccessor"
```

If Operational Intelligence never queries BigQuery directly, no BigQuery role is needed for this service account.

## 15. Operational Intelligence Deployment

### 15.1 requirements.txt

```text
fastapi
uvicorn[standard]
python-dotenv
google-cloud-pubsub
google-adk
google-genai
fastmcp
requests
pydantic
```

The existing root `pyproject.toml` currently only includes `google-cloud-storage` and `pandas`. Operational Intelligence needs additional dependencies.

### 15.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 15.3 Deploy Cloud Run

```bash
gcloud run deploy "$OI_SERVICE"   --source app/operational-intelligence/orchestrator-agent   --region "$REGION"   --service-account "$OI_SA_EMAIL"   --set-env-vars PROJECT_ID="$PROJECT_ID",REGION="$REGION",INSIGHTS_READY_TOPIC="$INSIGHTS_READY_TOPIC",KPI_MCP_URL="https://YOUR_KPI_MCP_SERVICE_URL/mcp",MODEL_NAME="gemini-2.5-flash-lite",LOG_LEVEL="INFO"   --allow-unauthenticated   --project "$PROJECT_ID"
```

For the prototype, `--allow-unauthenticated` is acceptable to simplify Pub/Sub push testing. For a stricter version, use authenticated Pub/Sub push.

### 15.4 Retrieve Cloud Run URL

```bash
export OI_URL=$(gcloud run services describe "$OI_SERVICE"   --region "$REGION"   --project "$PROJECT_ID"   --format="value(status.url)")

echo "$OI_URL"
```

## 16. Pub/Sub Push Subscription

### 16.1 Create subscription

```bash
gcloud pubsub subscriptions create "$OI_SUBSCRIPTION"   --topic "$KPIS_COMPUTED_TOPIC"   --push-endpoint "${OI_URL}/pubsub/kpis-computed"   --push-auth-service-account "$OI_SA_EMAIL"   --ack-deadline 60   --project "$PROJECT_ID"
```

### 16.2 Pub/Sub service agent permission

If authenticated push is used:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

gcloud iam service-accounts add-iam-policy-binding "$OI_SA_EMAIL"   --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"   --role="roles/iam.serviceAccountTokenCreator"   --project "$PROJECT_ID"
```

## 17. Observability and Trace Propagation

The existing KPI Function creates a `trace_id` from the CloudEvent ID when available:

```text
trace_id = cloud_event["id"] if "id" in cloud_event else uuid
```

This trace_id is written into BigQuery and published as a Pub/Sub attribute.

Operational Intelligence should preserve this trace_id.

Required log fields:

```text
trace_id
run_id
source_kpi_run_id
tenant_id
service_name
agent_name
operation
status
duration_ms
error_message
```

Example log:

```json
{
  "trace_id": "trace-123",
  "run_id": "oi-run-123",
  "source_kpi_run_id": "kpi-run-123",
  "tenant_id": "pulse-demo",
  "service_name": "operational-intelligence-orchestrator",
  "agent_name": "financial_intelligence_agent",
  "operation": "analyze_financial_kpis",
  "status": "success",
  "duration_ms": 842,
  "error_message": null
}
```

Trace path:

```text
GCS CloudEvent
→ KPI Function
→ BigQuery Gold Layer
→ kpis-computed attributes
→ Operational Intelligence
→ insights-ready JSON event
→ Reporting & Delivery
```

## 18. Error Handling

### 18.1 Missing Pub/Sub attributes

If `tenant_id`, `run_id`, or `trace_id` are missing:

```text
1. Try JSON decoding from message.data.
2. If still missing, return HTTP 400.
3. Log status = validation_failed.
4. Do not publish insights-ready.
```

### 18.2 KPI MCP unavailable

If KPI MCP is unavailable:

```text
1. Mark pipeline status as failed.
2. Log failure_stage = kpi_mcp_access.
3. For demo continuity, optionally use local fallback KPI data.
4. If fallback is used, set status = completed_with_fallback.
```

### 18.3 One agent fails

If only one domain agent fails:

```text
1. Continue with the successful agent output.
2. Mark failed output with status = failed.
3. Synthesis may still run with partial data.
4. Publish insights-ready with status = completed_with_warnings.
```

### 18.4 Synthesis fails

If synthesis fails:

```text
1. Store run status = failed.
2. Log error with trace_id.
3. Do not publish insights-ready unless a failure event format is agreed with Reporting.
```

## 19. Local Development and Testing

### 19.1 Run existing KPI computation locally

```bash
uv run python scripts/compute_kpis_local.py
```

Expected output:

```text
data/kpi/gold_kpi_snapshots_local.csv
```

This file can be used for local testing before BigQuery and MCP are connected.

### 19.2 Upload ingest files to GCS

From:

```text
app/infra/data-ingest-uploader/
```

Run:

```bash
uv run python upload_ingest_to_gcs.py
```

Expected GCS paths:

```text
ingest/{timestamp}/financial_clean.csv
ingest/{timestamp}/sales_marketing_clean.csv
ingest/{timestamp}/ready.json
```

The upload of `ready.json` should trigger the KPI Cloud Function.

### 19.3 Test Orchestrator locally

```bash
cd app/operational-intelligence/orchestrator-agent

uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

Manual pipeline test:

```bash
curl -X POST http://localhost:8080/pipeline/run   -H "Content-Type: application/json"   -d '{
    "tenant_id": "pulse-demo",
    "trace_id": "trace-local-001",
    "run_id": "manual-run-001",
    "source_kpi_run_id": "kpi-run-local-001",
    "period_end": "2026-05-01"
  }'
```

### 19.4 Simulate current KPI Pub/Sub event locally

```bash
python - <<'PY'
import base64
import json
import requests

data = base64.b64encode(b"KPI computation completed").decode()

body = {
    "message": {
        "data": data,
        "attributes": {
            "tenant_id": "pulse-demo",
            "run_id": "kpi-run-local-001",
            "trace_id": "trace-local-001"
        },
        "messageId": "local-message-001"
    },
    "subscription": "local-test"
}

response = requests.post(
    "http://localhost:8080/pubsub/kpis-computed",
    json=body,
    timeout=30
)

print(response.status_code)
print(response.text)
PY
```

This simulation matches the current behavior of `app/kpi-analytics/kpi-compute/main.py`.

## 20. Cloud End-to-End Test

### 20.1 Health check

```bash
curl "${OI_URL}/health"
```

Expected:

```json
{
  "status": "ok",
  "service": "operational-intelligence-orchestrator"
}
```

### 20.2 Publish manual kpis-computed test event with attributes

The current KPI Function publishes attributes. A manual test should do the same:

```bash
gcloud pubsub topics publish "$KPIS_COMPUTED_TOPIC"   --message="KPI computation completed"   --attribute=tenant_id="$TENANT_ID",run_id="kpi-run-manual-001",trace_id="trace-manual-001"   --project "$PROJECT_ID"
```

### 20.3 Check Orchestrator logs

```bash
gcloud logging read   'resource.type="cloud_run_revision" AND resource.labels.service_name="operational-intelligence-orchestrator"'   --limit 50   --project "$PROJECT_ID"
```

Search for:

```text
trace-manual-001
run_pipeline
financial_intelligence_agent
sales_crm_intelligence_agent
insight_synthesis_agent
publish_insights_ready
```

### 20.4 Verify insights-ready output

Create temporary debug subscription:

```bash
gcloud pubsub subscriptions create insights-ready-debug-sub   --topic "$INSIGHTS_READY_TOPIC"   --project "$PROJECT_ID"
```

Pull output:

```bash
gcloud pubsub subscriptions pull insights-ready-debug-sub   --auto-ack   --limit 5   --project "$PROJECT_ID"
```

## 21. Build Sequence Based on Current Repository

Recommended order:

```text
1. Keep existing GCS uploader and KPI Function as the upstream implementation.
2. Validate that uploading ready.json triggers KPI computation.
3. Validate that gold_kpi_snapshots is populated in BigQuery.
4. Validate that kpis-computed is published with tenant_id, run_id, and trace_id attributes.
5. Add KPI Data Serving API.
6. Add KPI MCP server wrapping the Data Serving API.
7. Add Operational Intelligence Orchestrator skeleton with /health and /pipeline/run.
8. Add Pub/Sub handler that supports the current attribute-based kpis-computed event.
9. Add mock Financial, Sales, and Synthesis agents.
10. Deploy Orchestrator to Cloud Run.
11. Add Pub/Sub push subscription from kpis-computed to Orchestrator.
12. Replace mock KPI data with MCP calls.
13. Publish insights-ready as JSON.
14. Validate logs and trace propagation.
```

This order prevents debugging the full stack at once and builds directly on the existing implementation.

## 22. Definition of Done

Operational Intelligence is complete when:

```text
1. Existing GCS upload still triggers KPI computation.
2. Existing KPI Function writes BigQuery Gold Layer rows.
3. Existing KPI Function publishes kpis-computed.
4. Orchestrator receives kpis-computed via Pub/Sub push.
5. Orchestrator extracts tenant_id, source KPI run_id, and trace_id from attributes.
6. Financial Agent produces financial insights.
7. Sales & CRM Agent produces sales insights.
8. Synthesis Agent produces cross-domain insights.
9. Orchestrator publishes insights-ready as JSON.
10. Logs show the same trace_id through the full Operational Intelligence flow.
11. The output payload is usable by Reporting & Delivery.
```

## 23. Demo Script

```text
1. Show GCS bucket pulse-demo-bronze with ingest files and ready.json.
2. Show existing KPI Cloud Function.
3. Show BigQuery table kpi_analytics_gold.gold_kpi_snapshots.
4. Show kpis-computed topic.
5. Trigger the pipeline by uploading ready.json or publishing a manual message.
6. Show Cloud Run logs for operational-intelligence-orchestrator.
7. Show Financial and Sales agent outputs.
8. Show synthesized cross-domain insight.
9. Pull the insights-ready message.
10. Explain that Reporting & Delivery consumes this message next.
```

## 24. Key Technical Notes

### 24.1 Current KPI write mode

The existing KPI Function uses:

```text
WRITE_TRUNCATE
```

This means each KPI computation replaces the full Gold table. For the MVP this is acceptable. For a more realistic historical implementation, this should later become an upsert or append strategy.

### 24.2 Current Pub/Sub event shape

The existing KPI Function does not publish a full JSON payload in message data. Operational Intelligence should support the current attribute-based event first.

### 24.3 Current regions

The existing KPI Function deployment comment uses:

```text
us-central1
trigger-location us
```

The Operational Intelligence Cloud Run service can run in:

```text
europe-west1
```

This is acceptable for a prototype, but using one region consistently is cleaner.

### 24.4 Current Operational Intelligence folder

The existing folder is effectively empty. The new implementation should be added under:

```text
app/operational-intelligence/orchestrator-agent/
```

## 25. Final Summary

The project already contains the upstream KPI implementation needed to trigger Operational Intelligence. The most important adjustment is that the Operational Intelligence build must consume the actual current `kpis-computed` event format, where `tenant_id`, `run_id`, and `trace_id` are Pub/Sub attributes. The missing middle layer consists of a KPI Data Serving API and KPI MCP server, after which ADK agents can retrieve KPI values and generate insights. The final implementation should preserve the existing GCS and KPI Cloud Function setup, add Cloud Run based Operational Intelligence, and publish a normalized `insights-ready` event for the next domain.
