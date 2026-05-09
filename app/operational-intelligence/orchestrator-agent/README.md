# Operational Intelligence Orchestrator

FastAPI service that runs the Pulse Operational Intelligence pipeline using Google ADK agents.
Triggered automatically via a Pub/Sub push subscription on `kpis-computed`, or manually via REST.

## What is in this folder

```
orchestrator-agent/
  app.py                   - FastAPI app with pipeline runner and Pub/Sub handler
  Dockerfile               - Container definition for Cloud Run
  requirements.txt         - Python dependencies
  .env.example             - Environment variable template

  pulse_oi/
    agent.py               - Root agent definition (SequentialAgent + ParallelAgent)
    financial_agent.py     - Financial Intelligence Agent
    sales_crm_agent.py     - Sales and CRM Intelligence Agent
    synthesis_agent.py     - Insight Synthesis Agent
```

## Architecture

```
kpis-computed (Pub/Sub)
        |
        v
POST /pubsub/kpis-computed
        |
        v
SequentialAgent: OperationalIntelligencePipeline
        |
        |-- ParallelAgent: ParallelKpiAnalysis
        |       |-- FinancialIntelligenceAgent
        |       └-- SalesCrmIntelligenceAgent
        |
        └-- InsightSynthesisAgent
                |
                v
        insights-ready (Pub/Sub)
```

Both domain agents run concurrently via `ParallelAgent`. Each writes its result to session state.
`InsightSynthesisAgent` reads both results and produces the final consolidated report.

## Agents

### FinancialIntelligenceAgent

Retrieves financial KPIs via MCP and applies severity rules across trend and absolute value checks.

Metrics monitored: `burn_rate`, `cash_flow`, `revenue_growth`, `outstanding_invoices`, `weekly_profit`

Output stored in session state as `financial_insights`.

### SalesCrmIntelligenceAgent

Retrieves sales and CRM KPIs via MCP and applies severity rules across trend and absolute value checks.

Metrics monitored: `churn_rate`, `conversion_rate`, `deal_velocity`, `incoming_leads`

Output stored in session state as `sales_crm_insights`.

### InsightSynthesisAgent

Reads `financial_insights` and `sales_crm_insights` from session state. Applies cross-domain
compound risk rules and produces a single consolidated intelligence report with `final_severity`.

Output stored in session state as `synthesized_insights` and published to `insights-ready`.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/pipeline/run` | Manually trigger the full pipeline |
| `POST` | `/pubsub/kpis-computed` | Pub/Sub push handler (automatic trigger) |

## Configuration

Copy `.env.example` to `.env` and fill in the values before running locally.

| Variable | Description |
|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | Use Vertex AI as the Gemini backend |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `KPI_MCP_URL` | URL of the KPI MCP server (`/mcp` endpoint) |
| `INSIGHTS_READY_TOPIC` | Pub/Sub topic name for publishing results |

## Local development

Prerequisites: Python 3.11+, active GCP authentication, KPI serving running locally.

```bash
cd app/operational-intelligence/orchestrator-agent
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --host 0.0.0.0 --port 8081
```

ADK web UI for local inspection: `http://localhost:8081/dev-ui`

## Dependencies

- `google-adk` - ADK agents, ParallelAgent, SequentialAgent, Runner
- `google-genai` - Gemini model client
- `google-cloud-pubsub` - Pub/Sub publishing
- `fastapi` + `uvicorn` - HTTP server
- `python-dotenv` - local `.env` loading
