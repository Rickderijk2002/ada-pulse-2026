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
      kpi-serving/                 # FastAPI read API over BigQuery Gold Layer
      kpi-mcp-server/              # Local MCP wrapper around kpi-serving
    operational-intelligence/
      orchestrator-agent/          # Local ADK agents and FastAPI orchestrator
    reporting-delivery/
  data/
    mockaroo/
    ingest/
    kpi/
  docs/
  scripts/
  pyproject.toml
```

## Local Architecture

The local Operational Intelligence flow is:

```text
KPI Serving API, port 8080
-> KPI MCP Server, port 8091
-> Financial Intelligence Agent
-> Sales CRM Intelligence Agent
-> Insight Synthesis Agent
-> Local Orchestrator, port 8090
```

The MVP follows the Lab 8 Sequential Pipeline Pattern:

```text
Financial Intelligence Agent
-> Sales CRM Intelligence Agent
-> Insight Synthesis Agent
```

A later version can use the Lab 8 Parallel Fan-Out/Gather Pattern:

```text
Financial Intelligence Agent + Sales CRM Intelligence Agent
-> Insight Synthesis Agent
```

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

The KPI MCP server uses:

```text
app/kpi-analytics/kpi-mcp-server/.env
```

Expected local content:

```text
KPI_DATA_API_URL=http://127.0.0.1:8080
MCP_HOST=0.0.0.0
MCP_PORT=8091
```

The Operational Intelligence orchestrator and agents use:

```text
app/operational-intelligence/orchestrator-agent/.env
```

Expected local content:

```text
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=ada26-pulse-project
GOOGLE_CLOUD_LOCATION=europe-west1
MODEL_NAME=gemini-2.5-flash-lite
KPI_MCP_URL=http://127.0.0.1:8091/mcp
```

Access-token based configuration, for example `GCP_ACCESS_TOKEN`, is lab/demo style only. Access tokens expire and should not be committed.

## Terminal Layout

Use separate terminals for each long-running service.

```text
Terminal 1: KPI Serving API, port 8080
Terminal 2: KPI MCP Server, port 8091
Terminal 3: ADK web or individual agent test
Terminal 4: Local orchestrator, port 8090
Terminal 5: curl or Invoke-RestMethod tests
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

## 2. Start KPI MCP Server

The KPI MCP server follows the Lab 6 REST-to-MCP pattern:

```text
KPI Serving API
-> REST wrapper endpoints
-> MCP tools
-> ADK agents
```

Location:

```text
app/kpi-analytics/kpi-mcp-server/
  app.py
  requirements.txt
  .env
  .gitignore
```

Install service requirements without changing `pyproject.toml`:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026"
uv pip install -r app\kpi-analytics\kpi-mcp-server\requirements.txt
```

Start the service:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026\app\kpi-analytics\kpi-mcp-server"
$env:KPI_DATA_API_URL="http://127.0.0.1:8080"
uv run python -m uvicorn app:app --reload --port 8091
```

Local URLs:

```text
API:          http://127.0.0.1:8091
MCP endpoint: http://127.0.0.1:8091/mcp
```

REST wrapper checks:

```powershell
curl http://127.0.0.1:8091/health
curl http://127.0.0.1:8091/tools/kpi/domains/pulse-demo
curl "http://127.0.0.1:8091/tools/kpi/metrics/pulse-demo?domain=financial"
curl "http://127.0.0.1:8091/tools/kpi/latest/pulse-demo?domain=financial"
curl "http://127.0.0.1:8091/tools/kpi/history/pulse-demo/financial/burn_rate?periods=6"
```

MCP tools exposed through `operation_id`:

```text
list_kpi_domains
list_kpis_in_domain
get_latest_kpis
get_kpi_history
```

Validate MCP with MCP Inspector:

```powershell
npx @modelcontextprotocol/inspector
```

Use this MCP endpoint in the Inspector:

```text
http://127.0.0.1:8091/mcp
```

Test these MCP tool calls:

```text
list_kpi_domains tenant_id=pulse-demo
list_kpis_in_domain tenant_id=pulse-demo domain=financial
get_latest_kpis tenant_id=pulse-demo domain=financial
get_kpi_history tenant_id=pulse-demo domain=financial metric_name=burn_rate periods=6
```

Continue only after the MCP tools return KPI data.

## 3. Validate ADK Agents

Location:

```text
app/operational-intelligence/orchestrator-agent/
  financial_agent/
    agent.py
  sales_crm_agent/
    agent.py
  synthesis_agent/
    agent.py
  mcp_tools.py
  orchestrator/
    __init__.py
    pipeline.py
  app.py
```

The plain `adk` command may point to a different CLI in this environment. Use the Google ADK Python module entrypoint.

Run each agent directly:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026\app\operational-intelligence\orchestrator-agent"
uv run python -m google.adk.cli run financial_agent
uv run python -m google.adk.cli run sales_crm_agent
uv run python -m google.adk.cli run synthesis_agent
```

When prompted for a user name, use a simple local value:

```text
local-user
```

Example financial prompt:

```text
Use tenant_id pulse-demo. Retrieve latest financial KPIs and 6 periods of history for burn_rate, cash_flow, revenue_growth, and outstanding_invoices. Return strict JSON only.
```

Start ADK web:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026\app\operational-intelligence\orchestrator-agent"
uv run python -m google.adk.cli web --port 8000 .
```

Open:

```text
http://127.0.0.1:8000
```

The ADK web UI should list:

```text
financial_agent
sales_crm_agent
synthesis_agent
```

If ADK web shows `No agents found in current folder`, the command was started from the wrong folder. Stop the server, move to `app/operational-intelligence/orchestrator-agent`, and start it again.

The `orchestrator/` folder is not an ADK app. It contains pipeline code for the FastAPI orchestrator.

## 4. Start Local Orchestrator

The local orchestrator is exposed by:

```text
app/operational-intelligence/orchestrator-agent/app.py
```

It calls:

```text
orchestrator/pipeline.py
```

Endpoints:

```text
GET /health
POST /pipeline/run
GET /pipeline/{run_id}/status
POST /pubsub/kpis-computed
```

The local `/pubsub/kpis-computed` endpoint is currently a placeholder. Use `/pipeline/run` for local manual testing.

Before starting the orchestrator, verify:

```text
1. KPI Serving API runs on http://127.0.0.1:8080.
2. KPI MCP Server runs on http://127.0.0.1:8091.
3. MCP Inspector can call the KPI tools.
4. orchestrator-agent/.env contains Vertex/Gemini and KPI_MCP_URL settings.
```

Start the orchestrator:

```powershell
cd "C:\Projects\Advanced Data Architectures\ada-pulse-2026\app\operational-intelligence\orchestrator-agent"
uv run python -m uvicorn app:app --reload --port 8090
```

Health check:

```powershell
curl http://127.0.0.1:8090/health
```

Expected response:

```json
{"status":"ok","service":"operational-intelligence-orchestrator"}
```

Manual pipeline run, PowerShell safe version:

```powershell
$body = @{
  tenant_id = "pulse-demo"
  trace_id = "trace-local-001"
  run_id = "manual-run-001"
  source_kpi_run_id = "kpi-run-local-001"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8090/pipeline/run" `
  -ContentType "application/json" `
  -Body $body
```

Check run status:

```powershell
curl http://127.0.0.1:8090/pipeline/manual-run-001/status
```

Expected pipeline behavior:

```text
1. Financial agent returns strict JSON.
2. Sales CRM agent returns strict JSON.
3. Synthesis agent combines both outputs.
4. Orchestrator returns one combined insight payload.
```

The pipeline strips markdown JSON code fences from agent output before JSON parsing. This handles common LLM responses that wrap JSON in triple backticks with a `json` label.

Example pattern:

```text
triple-backtick json
{ ... }
triple-backtick
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
2. gcloud project is ada26-pulse-project.
3. ADC quota project is ada26-pulse-project.
4. KPI Serving API /health works.
5. KPI Serving API returns financial and sales_crm data.
6. KPI MCP Server /health works.
7. MCP REST wrapper endpoints return KPI data.
8. MCP Inspector lists and executes the KPI tools.
9. ADK run works for financial_agent.
10. ADK run works for sales_crm_agent.
11. ADK run works for synthesis_agent.
12. Local orchestrator /health works.
13. Local orchestrator /pipeline/run returns a combined payload.
14. Only intentional files are staged.
```

## Notes

- Pipeline status for teammates: [CURRENT_STATE.md](CURRENT_STATE.md) (ingest, KPI function, serving API).
- Operational Intelligence plan: [docs/Operational-Intelligence-plan.md](docs/Operational-Intelligence-plan.md).
