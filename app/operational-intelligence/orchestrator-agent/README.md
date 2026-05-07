# Operational Intelligence Orchestrator (`orchestrator-agent`)

FastAPI service that runs the Pulse Operational Intelligence pipeline using Google ADK agents.
Triggered automatically via a Pub/Sub push subscription on `kpis-computed`, or manually via REST.

## Architecture

```
kpis-computed (Pub/Sub)
        |
        | push subscription
        v
POST /pubsub/kpis-computed   ← Cloud Run entry point
        |
        v
OperationalIntelligencePipeline (SequentialAgent)
        |
        |── ParallelKpiAnalysis (ParallelAgent)
        |       |── FinancialIntelligenceAgent    → session["financial_insights"]
        |       └── SalesCrmIntelligenceAgent     → session["sales_crm_insights"]
        |
        └── InsightSynthesisAgent                 → session["synthesized_insights"]
                |
                v
        insights-ready (Pub/Sub)
```

Each agent connects to the KPI MCP server (`pulse-kpi-serving-mcp`) via `McpToolset` to retrieve
live KPI data from the BigQuery gold layer.

## Agents

### FinancialIntelligenceAgent (`pulse_oi/financial_agent.py`)

Retrieves financial KPIs and applies severity rules.

MCP calls made:
- `get_latest_kpis(tenant_id, domain="financial")`
- `get_kpi_history(...)` for: `burn_rate`, `cash_flow`, `revenue_growth`, `outstanding_invoices`, `weekly_profit`

Severity rules:
| Rule | Severity |
|---|---|
| `cash_flow` latest < 0 | high |
| `revenue_growth` latest < -20% | high |
| `cash_flow` negative AND `outstanding_invoices` rising | high (compound) |
| `burn_rate` increasing 3+ periods | medium |
| `revenue_growth` negative | medium |
| `outstanding_invoices` increasing 2+ periods | medium |
| `weekly_profit` latest < 0 | medium |

Output stored in session state as `financial_insights`.

---

### SalesCrmIntelligenceAgent (`pulse_oi/sales_crm_agent.py`)

Retrieves sales and CRM KPIs and applies severity rules.

MCP calls made:
- `get_latest_kpis(tenant_id, domain="sales_crm")`
- `get_kpi_history(...)` for: `churn_rate`, `conversion_rate`, `deal_velocity`, `incoming_leads`

Severity rules:
| Rule | Severity |
|---|---|
| `churn_rate` latest > 5% | high |
| `churn_rate` increasing 2+ periods | high |
| `incoming_leads` decreasing AND `conversion_rate` decreasing | high (compound) |
| `churn_rate` increasing AND `deal_velocity` decreasing | high (compound) |
| `conversion_rate` latest < 10% | medium |
| `conversion_rate` decreasing 3+ periods | medium |
| `deal_velocity` latest < 10 deals/week | medium |
| `deal_velocity` decreasing 2+ periods | medium |
| `incoming_leads` latest < 50 leads/week | medium |

Output stored in session state as `sales_crm_insights`.

---

### InsightSynthesisAgent (`pulse_oi/synthesis_agent.py`)

Reads `financial_insights` and `sales_crm_insights` from session state and produces a consolidated
cross-domain intelligence report.

Cross-domain compound rules:
| Rule | Risk type | Severity |
|---|---|---|
| `revenue_growth` flagged AND `churn_rate` flagged | `compound_revenue_pressure` | high |
| `cash_flow` flagged AND `deal_velocity` flagged | `cash_flow_pipeline_risk` | high |
| `burn_rate` flagged AND `conversion_rate` flagged | `cost_pressure_weak_pipeline` | high |
| `outstanding_invoices` flagged AND `incoming_leads` flagged | `receivables_pipeline_risk` | medium |

Output stored in session state as `synthesized_insights` and published to `insights-ready`.

## Pipeline composition (`pulse_oi/agent.py`)

```python
parallel_analysis = ParallelAgent(
    name="ParallelKpiAnalysis",
    sub_agents=[financial_agent, sales_crm_agent],
)

root_agent = SequentialAgent(
    name="OperationalIntelligencePipeline",
    sub_agents=[parallel_analysis, synthesis_agent],
)
```

ADK's `ParallelAgent` runs both domain agents concurrently. `SequentialAgent` ensures synthesis
only runs after both domain agents have completed and written their results to session state.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/pipeline/run` | Manually trigger the full pipeline |
| `POST` | `/pubsub/kpis-computed` | Pub/Sub push handler (automatic trigger) |

### POST /pipeline/run

Request body:
```json
{
  "tenant_id": "pulse-demo",
  "run_id": "manual-run-001"
}
```

Response (synchronous — waits for full pipeline):
```json
{
  "run_id": "manual-run-001",
  "status": "completed",
  "result": {
    "agent": "insight_synthesis_agent",
    "status": "success",
    "tenant_id": "pulse-demo",
    "final_severity": "high",
    "summary": "...",
    "domain_insights": { "financial": [...], "sales_crm": [...] },
    "cross_domain_insights": [...]
  }
}
```

### POST /pubsub/kpis-computed

Accepts a Pub/Sub push envelope. Returns `200` immediately and runs the pipeline in the background
via `asyncio.create_task` so Pub/Sub does not retry.

```json
{
  "message": {
    "data": "<base64-encoded JSON>",
    "messageId": "123456"
  },
  "subscription": "projects/ada26-pulse-project/subscriptions/kpis-computed-push-orchestrator"
}
```

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` | Use Vertex AI as the Gemini backend |
| `GOOGLE_CLOUD_PROJECT` | | GCP project ID |
| `KPI_MCP_URL` | `http://localhost:8080/mcp` | URL of the KPI MCP server |
| `INSIGHTS_READY_TOPIC` | `insights-ready` | Pub/Sub topic for publishing results |

Copy `.env.example` to `.env` and fill in the values for local development.

## Local development

Prerequisites:
- Python 3.11+
- `gcloud auth application-default login` (for Vertex AI access)
- KPI serving running locally on port 8080 (see `app/kpi-analytics/kpi-serving`)

```bash
cd app/operational-intelligence/orchestrator-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
uvicorn app:app --reload --host 0.0.0.0 --port 8081
```

ADK web UI available at: http://localhost:8081/dev-ui

Trigger the pipeline manually:
```bash
# PowerShell
$body = @{tenant_id="pulse-demo"; run_id="local-001"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8081/pipeline/run -ContentType "application/json" -Body $body
```

## Cloud Run deployment

Both the KPI MCP server and the orchestrator must be deployed before the push subscription is created.

```bash
# 1. Deploy KPI MCP server (from kpi-analytics/kpi-serving)
gcloud run deploy pulse-kpi-serving-mcp \
  --source app/kpi-analytics/kpi-serving \
  --region europe-west4 \
  --project ada26-pulse-project \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=ada26-pulse-project,BQ_DATASET=kpi_analytics_gold,BQ_TABLE=gold_kpi_snapshots"

# 2. Deploy orchestrator
gcloud run deploy pulse-orchestrator \
  --source app/operational-intelligence/orchestrator-agent \
  --region europe-west4 \
  --project ada26-pulse-project \
  --allow-unauthenticated \
  --timeout 300 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=ada26-pulse-project,GOOGLE_GENAI_USE_VERTEXAI=true,INSIGHTS_READY_TOPIC=insights-ready,KPI_MCP_URL=https://pulse-kpi-serving-mcp-266532618671.europe-west4.run.app/mcp"

# 3. Create Pub/Sub push subscription
gcloud pubsub subscriptions create kpis-computed-push-orchestrator \
  --topic kpis-computed \
  --push-endpoint https://pulse-orchestrator-266532618671.europe-west4.run.app/pubsub/kpis-computed \
  --project ada26-pulse-project \
  --ack-deadline 300
```

## End-to-end test

Simulate a `kpis-computed` Pub/Sub event:

```bash
# PowerShell
gcloud pubsub topics publish kpis-computed `
  --message="KPI computation completed" `
  --attribute=tenant_id=pulse-demo,run_id=kpi-run-e2e-001,trace_id=trace-e2e-001 `
  --project ada26-pulse-project
```

Check logs:
```bash
gcloud run services logs read pulse-orchestrator \
  --region europe-west4 \
  --project ada26-pulse-project \
  --limit 80
```

Pull results from insights-ready:
```bash
gcloud pubsub subscriptions create insights-ready-debug \
  --topic insights-ready \
  --project ada26-pulse-project

gcloud pubsub subscriptions pull insights-ready-debug \
  --auto-ack \
  --limit 5 \
  --project ada26-pulse-project
```

## Dependencies

See `requirements.txt`:
- `google-adk` - ADK agents, ParallelAgent, SequentialAgent, Runner
- `google-genai` - Gemini model client
- `google-cloud-pubsub` - Pub/Sub publishing
- `fastapi` + `uvicorn` - HTTP server
- `python-dotenv` - local `.env` loading
