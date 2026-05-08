# ADA Pulse 2026

Working repository for Assignment 2 implementation of the Pulse architecture.

This README describes the local development flow for the Operational Intelligence layer. The goal is that every team member can start the same services, on the same ports, in the same order.

## Project Structure

```text
ada-pulse-2026/
  app/
    infra/                         # GCS upload and ingest helpers
    kpi-analytics/
      kpi-compute/                 # KPI Cloud Function
      kpi-serving/                 # FastAPI read API over BigQuery Gold Layer + MCP endpoint at /mcp (main.py)
    operational-intelligence/
      orchestrator-agent/          # FastAPI orchestrator + ADK agents
        app.py                     # FastAPI app and pipeline runner
        Dockerfile
        requirements.txt
        .env.example
        pulse_oi/
          __init__.py
          agent.py                 # root_agent: SequentialAgent wrapping ParallelAgent + synthesis
          financial_agent.py       # FinancialIntelligenceAgent
          sales_crm_agent.py       # SalesCrmIntelligenceAgent
          synthesis_agent.py       # InsightSynthesisAgent
    reporting-delivery/
  data/
    ingest/
    kpi/
  docs/
  scripts/
  pyproject.toml
```

## Local Architecture

The local Operational Intelligence flow is:

```text
KPI Serving API + MCP endpoint (/mcp), port 8080
-> Financial Intelligence Agent + Sales CRM Intelligence Agent (parallel)
-> Insight Synthesis Agent
-> Orchestrator, port 8081
```

The pipeline uses the ADK Parallel Fan-Out/Gather pattern followed by synthesis:

```text
ParallelAgent: Financial Intelligence Agent + Sales CRM Intelligence Agent
-> SequentialAgent: Insight Synthesis Agent
```

The MCP endpoint is embedded directly in the KPI Serving API (`kpi-serving/main.py`).
There is no separate MCP server process.

## Prerequisites

Required local tools:

```text
PowerShell
Git
uv
gcloud CLI
Node.js and npx, for MCP Inspector
```

Create or sync the Python environment from the repository root:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026"
uv sync
```

Check Google Cloud configuration:

```powershell
gcloud auth list
gcloud config get-value project
gcloud config list
```

Set the expected project:

```powershell
gcloud config set project ada26-pulse-project
```

Configure Application Default Credentials for BigQuery and Vertex AI:

```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project ada26-pulse-project
```

Expected project value:

```text
ada26-pulse-project
```

Google Cloud may warn that the project has no `environment` tag. That warning does not block local development.

## Git Branch Workflow

Operational Intelligence work should be developed on a separate branch.

Check the current working tree:

```powershell
git status
```

Create and switch to a new branch:

```powershell
git switch -c feature/operational-intelligence-local
```

Confirm the active branch:

```powershell
git branch
```

The active branch is marked with `*`.

Existing local changes move to the new branch when `git switch -c` is used. Before committing, only stage files that belong to the work.

Example:

```powershell
git add README.md docs/Operational-Intelligence-plan.md app/kpi-analytics/kpi-mcp-server app/operational-intelligence/orchestrator-agent
git commit -m "Add local operational intelligence workflow"
```

Data files, `pyproject.toml`, and `uv.lock` should only be staged when those changes are intentional.

## Environment Files

Do not commit `.env` files.

The Operational Intelligence orchestrator uses:

```text
app/operational-intelligence/orchestrator-agent/.env
```

Copy from `.env.example` and fill in your values. Expected local content:

```text
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=<your-project-id>
KPI_MCP_URL=http://127.0.0.1:8080/mcp
INSIGHTS_READY_TOPIC=insights-ready
```

`KPI_MCP_URL` points to the MCP endpoint embedded in the KPI Serving API — same port (8080), path `/mcp`.

## Terminal Layout

Use separate terminals for each long-running service.

```text
Terminal 1: KPI Serving API + MCP, port 8080
Terminal 2: ADK web UI or orchestrator, port 8081
Terminal 3: curl or Invoke-RestMethod tests
```

## 1. Start KPI Serving API

The KPI Serving API validates the read layer over the BigQuery Gold table.

Install service requirements without changing `pyproject.toml`:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026"
uv pip install -r app\kpi-analytics\kpi-serving\requirements.txt
```

Start the service:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026\app\kpi-analytics\kpi-serving"
uv run python -m uvicorn main:app --reload --port 8080
```

Local URLs:

```text
API:  http://127.0.0.1:8080
Docs: http://127.0.0.1:8080/docs
```

Health check, from another terminal:

```powershell
curl http://127.0.0.1:8080/health
```

Expected response:

```json
{"status":"ok"}
```

KPI data checks:

```powershell
curl http://127.0.0.1:8080/kpis/pulse-demo/domains
curl "http://127.0.0.1:8080/kpis/pulse-demo/metrics?domain=financial"
curl "http://127.0.0.1:8080/kpis/pulse-demo/latest?domain=financial"
curl "http://127.0.0.1:8080/kpis/pulse-demo/latest?domain=sales_crm"
curl "http://127.0.0.1:8080/kpis/pulse-demo/metrics/financial/burn_rate/history?limit=6"
```

The tenant path must be `pulse-demo`. Other tenant values return `404`.

## 2. Validate MCP endpoint

The MCP endpoint is embedded in the KPI Serving API (`kpi-serving/main.py`) using `fastapi-mcp`.
No separate MCP server process is needed. Once the KPI Serving API is running, the MCP endpoint
is available at the same port under `/mcp`.

MCP tools exposed:

```text
list_kpi_domains
list_kpi_metrics
get_latest_kpis
get_latest_kpi_single
get_kpi_history
```

Validate with MCP Inspector:

```powershell
npx @modelcontextprotocol/inspector
```

Connect the Inspector to:

```text
http://127.0.0.1:8080/mcp
```

Test tool calls:

```text
get_latest_kpis tenant_id=pulse-demo domain=financial
get_kpi_history tenant_id=pulse-demo domain=financial metric_name=burn_rate limit=6
```

Continue only after the MCP tools return KPI data.

## 3. Validate ADK Agents

The agents are all defined inside the `pulse_oi` package:

```text
app/operational-intelligence/orchestrator-agent/
  app.py                        - FastAPI app and pipeline runner
  Dockerfile
  requirements.txt
  .env.example
  pulse_oi/
    __init__.py
    agent.py                    - root_agent: SequentialAgent (ParallelAgent + synthesis)
    financial_agent.py          - FinancialIntelligenceAgent
    sales_crm_agent.py          - SalesCrmIntelligenceAgent
    synthesis_agent.py          - InsightSynthesisAgent
```

### Agent overview

**FinancialIntelligenceAgent** (`financial_agent.py`)
Retrieves financial KPIs via MCP and applies severity rules across trend and absolute value checks.
Metrics monitored: `burn_rate`, `cash_flow`, `revenue_growth`, `outstanding_invoices`, `weekly_profit`
Output stored in session state as `financial_insights`.

**SalesCrmIntelligenceAgent** (`sales_crm_agent.py`)
Retrieves sales and CRM KPIs via MCP and applies severity rules across trend and absolute value checks.
Metrics monitored: `churn_rate`, `conversion_rate`, `deal_velocity`, `incoming_leads`
Output stored in session state as `sales_crm_insights`.

**InsightSynthesisAgent** (`synthesis_agent.py`)
Reads `financial_insights` and `sales_crm_insights` from session state. Applies cross-domain
compound risk rules and produces a single consolidated report with `final_severity`.
Output stored in session state as `synthesized_insights`.

**Agent composition** (`agent.py`)

```text
SequentialAgent: OperationalIntelligencePipeline
  |-- ParallelAgent: ParallelKpiAnalysis
  |       |-- FinancialIntelligenceAgent
  |       └-- SalesCrmIntelligenceAgent
  └-- InsightSynthesisAgent
```

Start the ADK web UI to inspect and test the agents interactively:

```powershell
cd "app\operational-intelligence\orchestrator-agent"
uvicorn app:app --host 0.0.0.0 --port 8081
```

Open the ADK web UI at `http://127.0.0.1:8081/dev-ui`

The ADK app name is `pulse_oi`. The root agent runs the full pipeline:
`ParallelAgent` (financial + sales) followed by `InsightSynthesisAgent`.

## 4. Run the Pipeline

The orchestrator is `app.py` in `orchestrator-agent/`. The pipeline logic is implemented directly
in `app.py` using the ADK `Runner` with `InMemorySessionService` — there is no separate
`orchestrator/` subfolder.

Endpoints:

```text
GET  /health
POST /pipeline/run
POST /pubsub/kpis-computed
```

Before starting, verify:

```text
1. KPI Serving API is running on port 8080.
2. MCP Inspector can call the KPI tools on port 8080 /mcp.
3. orchestrator-agent/.env contains GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, and KPI_MCP_URL.
```

The orchestrator runs as part of `app.py` — the same process also serves the ADK web UI.
Start it with:

```powershell
cd "app\operational-intelligence\orchestrator-agent"
uvicorn app:app --host 0.0.0.0 --port 8081
```

Manual pipeline run:

```powershell
$body = @{ tenant_id = "pulse-demo"; run_id = "manual-run-001" } | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8081/pipeline/run" `
  -ContentType "application/json" `
  -Body $body
```

Expected pipeline behavior:

```text
1. FinancialIntelligenceAgent and SalesCrmIntelligenceAgent run in parallel.
2. Both agents call get_latest_kpis and get_kpi_history via MCP.
3. InsightSynthesisAgent combines both outputs into a consolidated report.
4. Result is returned as JSON with final_severity and cross-domain insights.
```

## Cloud Deployment

The Operational Intelligence layer is deployed to GCP Cloud Run. The following describes
what was built and how the full cloud flow works.

### Deployed Cloud Run services

| Service | Description |
|---|---|
| `pulse-kpi-serving-mcp` | KPI Serving API with MCP endpoint at `/mcp` — reads from BigQuery Gold Layer |
| `pulse-orchestrator` | Operational Intelligence Orchestrator — runs the ADK agent pipeline |

Both services are deployed in the same GCP region.

### Pub/Sub topics

| Topic | Purpose |
|---|---|
| `kpis-computed` | Published by the KPI Cloud Function when a KPI computation completes |
| `insights-ready` | Published by the Orchestrator when the full agent pipeline completes |

### Pub/Sub push subscription

A push subscription named `kpis-computed-push-orchestrator` connects the `kpis-computed` topic
to the Orchestrator's `/pubsub/kpis-computed` endpoint. When the KPI Cloud Function publishes
to `kpis-computed`, GCP automatically POSTs the message to the Orchestrator on Cloud Run.

### Full cloud flow

```text
GCS upload (financial_clean.csv + sales_marketing_clean.csv + ready.json)
        |
        v
KPI Computation Cloud Function (triggered by GCS object finalized)
        |  writes
        v
BigQuery Gold Layer: kpi_analytics_gold.gold_kpi_snapshots
        |  publishes
        v
Pub/Sub topic: kpis-computed
        |  push subscription
        v
Cloud Run: pulse-orchestrator  POST /pubsub/kpis-computed
        |
        v
ParallelAgent: FinancialIntelligenceAgent + SalesCrmIntelligenceAgent
        |  both call MCP tools
        v
Cloud Run: pulse-kpi-serving-mcp  /mcp
        |  queries
        v
BigQuery Gold Layer
        |
        v
InsightSynthesisAgent
        |  publishes
        v
Pub/Sub topic: insights-ready
```

### Triggering the pipeline manually on Cloud Run

Trigger via REST (synchronous — waits for full result):

```powershell
$body = @{ tenant_id = "pulse-demo"; run_id = "manual-001" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "<orchestrator-cloud-run-url>/pipeline/run" `
  -ContentType "application/json" `
  -Body $body
```

Trigger via Pub/Sub (simulates the KPI Cloud Function firing):

```powershell
gcloud pubsub topics publish kpis-computed `
  --message="KPI computation completed" `
  --attribute=tenant_id=pulse-demo,run_id=kpi-run-001,trace_id=trace-001 `
  --project <your-project-id>
```

### Checking results on Cloud Run

Pull results from `insights-ready` (create a debug subscription first):

```powershell
gcloud pubsub subscriptions create insights-ready-debug `
  --topic insights-ready --project <your-project-id>

gcloud pubsub subscriptions pull insights-ready-debug `
  --auto-ack --limit 5 --project <your-project-id>
```

Check orchestrator logs:

```powershell
gcloud run services logs read pulse-orchestrator `
  --region <your-region> --project <your-project-id> --limit 80
```

## Troubleshooting

`uvicorn` returns `Could not import module "app"`:

```text
Cause: command started from the wrong folder, or app.py is missing.
Fix: run from app/operational-intelligence/orchestrator-agent.
```

ADK web shows `No agents found in current folder`:

```text
Cause: ADK web was started from orchestrator/ or another subfolder.
Fix: run from app/operational-intelligence/orchestrator-agent.
```

`uv run adk run financial_agent` returns an unrecognized argument error:

```text
Cause: the plain adk command points to another CLI.
Fix: use uv run python -m google.adk.cli run financial_agent.
```

PowerShell `curl -d` returns invalid JSON:

```text
Cause: quoting differences in PowerShell.
Fix: use Invoke-RestMethod with ConvertTo-Json.
```

Pipeline returns `Agent ... returned invalid JSON`:

```text
Cause: an agent returned text that is not JSON.
Fix: tighten the agent prompt or inspect the agent response in the error detail.
```

## Local Validation Checklist

Use this order before committing local Operational Intelligence work:

```text
1. git status reviewed.
2. gcloud project is set correctly.
3. ADC quota project is set correctly.
4. KPI Serving API /health works on port 8080.
5. KPI Serving API returns financial and sales_crm data.
6. MCP Inspector connects to /mcp on port 8080 and executes get_latest_kpis and get_kpi_history.
7. orchestrator-agent/.env has correct GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, KPI_MCP_URL.
8. Orchestrator /health works on port 8081.
9. Orchestrator /pipeline/run returns a consolidated synthesis payload.
10. Only intentional files are staged.
```

## Notes

- Pipeline status for teammates: [CURRENT_STATE.md](CURRENT_STATE.md) (ingest, KPI function, serving API).
- Operational Intelligence plan: [docs/Operational-Intelligence-plan.md](docs/Operational-Intelligence-plan.md).
