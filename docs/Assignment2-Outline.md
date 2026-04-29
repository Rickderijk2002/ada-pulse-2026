# Assignment 2 - Implementation Outline

**Group 5** | Rick de Rijk, Thom Verzantvoort, Tycho van Rooij, Jelles Duin, Gilbert Laanen

---

## Assignment Requirements


| Requirement                        | Value                                              |
| ---------------------------------- | -------------------------------------------------- |
| Min microservices / agents         | 4 (excl. external APIs/MCP)                        |
| Min operations across all services | 12                                                 |
| Domains to cover                   | At least 2 (prefer core)                           |
| Composition                        | Orchestration and/or choreography                  |
| Implementation mix                 | FaaS + RESTful; agents must use custom MCP servers |
| Deadline                           | 20 May, 11:59 PM                                   |
| Demo                               | 22 May, during lab                                 |


---

## Scope

We implement a simplified but working end-to-end version of the Pulse platform covering three domains
from our Assignment 1 design: **KPI & Analytics** (core), **Operational Intelligence** (core), and
**Reporting & Delivery** (core/supporting). Data Integration is stubbed with mock data in GCS buckets.

---

## Assumptions

- Data Integration is not implemented. Raw financial and sales/CRM data is pre-seeded as mock CSV
files in Google Cloud Storage buckets, representing the normalized output that Data Integration
would normally produce (in a real system this data would live in a SQL database owned by the
Data Integration domain).
- The API Gateway and JWT authentication are assumed but not implemented. All service endpoints are
accessible without authentication for this prototype.
- The event bus is implemented using Google Pub/Sub. Cross-domain choreography follows the
publish/subscribe pattern from the design.
- The Circuit Breaker, Distributed Tracing, and Tenant Management domain are out of scope.
- A single hardcoded tenant (`tenant_id = "pulse-demo"`) is used throughout the prototype.

---

## Technology Stack


| Component            | Technology                         |
| -------------------- | ---------------------------------- |
| Cloud platform       | Google Cloud Platform              |
| FaaS                 | Google Cloud Functions (Python)    |
| RESTful services     | Cloud Run (FastAPI, Python)        |
| Agents               | Google Agent Development Kit (ADK) |
| Event bus            | Google Pub/Sub                     |
| KPI / metric storage | Google BigQuery (Gold Layer)       |
| Mock data storage    | Google Cloud Storage               |
| Custom MCP server    | Python MCP SDK (stdio transport)   |
| LLM backend          | Gemini (via ADK)                   |


---

## Architecture Overview

```
[GCS Buckets]
   raw_financial_data/
   raw_sales_crm_data/
         |
         | (manual trigger or HTTP call)
         v
[KPI Computation Service]   <-- Cloud Function (FaaS)
   reads mock CSV data from GCS
   computes financial + sales KPIs
   writes to BigQuery (Gold Layer)
   publishes --> Pub/Sub: kpis-computed
         |
         v
[Orchestrator Agent]        <-- ADK Agent exposed via Cloud Run
   subscribes to kpis-computed
   dispatches Financial Agent and Sales/CRM Agent in parallel
   sequences Cross-Domain + Synthesis agents
   publishes --> Pub/Sub: insights-ready
         |
    [Financial Intelligence Agent]    [Sales & CRM Intelligence Agent]
    reads KPIs via MCP server         reads KPIs via MCP server
    returns structured insights       returns structured insights
         |                                   |
         +-----------------------------------+
                         |
              [Insight Synthesis Agent]
              assembles final insight payload
                         |
                         v
[Composition Service]       <-- Cloud Function (FaaS)
   subscribes to insights-ready
   assembles tenant report from insight payload
   publishes --> Pub/Sub: report-composed
                         |
                         v
[Delivery Service]          <-- Cloud Run (RESTful)
   subscribes to report-composed
   formats and delivers report (mock email / Slack webhook / log)
   publishes --> Pub/Sub: report-delivered
```

### Pub/Sub Topics


| Topic              | Published by                           | Consumed by            |
| ------------------ | -------------------------------------- | ---------------------- |
| `kpis-computed`    | KPI Computation Service                | Orchestrator Agent     |
| `insights-ready`   | Orchestrator Agent (Insight Synthesis) | Composition Service    |
| `report-composed`  | Composition Service                    | Delivery Service       |
| `report-delivered` | Delivery Service                       | (logging / monitoring) |


---

## Services, Agents, and Operations

### Domain: KPI & Analytics

**Owner: Jelles (+ Thom for architecture)**

#### 1. KPI Computation Service

- Type: Cloud Function (FaaS)
- Trigger: HTTP call (manual for demo) or Pub/Sub push
- Storage: reads CSVs from GCS, writes KPI snapshots to BigQuery table `kpi_snapshots`


| Operation                                     | Description                                                                            |
| --------------------------------------------- | -------------------------------------------------------------------------------------- |
| `compute_financial_kpis(tenant_id, period)`   | Reads raw financial data from GCS, computes burn rate, revenue growth, cash flow       |
| `compute_sales_kpis(tenant_id, period)`       | Reads raw sales/CRM data from GCS, computes conversion rate, deal velocity, churn rate |
| `store_kpi_snapshot(tenant_id, period, kpis)` | Writes computed KPI snapshot as a row to BigQuery `kpi_snapshots` table with timestamp |


#### 2. Data Serving Layer

- Type: Cloud Run (FastAPI, RESTful)
- Storage: queries BigQuery `kpi_snapshots` table (Gold Layer)


| Operation                       | Description                                                           |
| ------------------------------- | --------------------------------------------------------------------- |
| `GET /kpis/{tenant_id}/latest`  | Returns the most recent KPI snapshot for the tenant                   |
| `GET /kpis/{tenant_id}/history` | Returns historical KPI snapshots (query param: `metric`, `n_periods`) |
| `GET /kpis/{tenant_id}/trends`  | Returns a trend summary (direction + delta) per KPI metric            |


#### 3. KPI Tools MCP Server

- Type: Custom MCP server (Python MCP SDK, stdio transport)
- Consumed by: Financial Intelligence Agent and Sales & CRM Intelligence Agent
- Wraps the Data Serving Layer REST API as agent-callable tools


| MCP Tool                                       | Description                                                  |
| ---------------------------------------------- | ------------------------------------------------------------ |
| `get_financial_kpis(tenant_id, period)`        | Proxies `GET /kpis/{tenant_id}/latest` for financial metrics |
| `get_sales_kpis(tenant_id, period)`            | Proxies `GET /kpis/{tenant_id}/latest` for sales/CRM metrics |
| `get_trend_data(tenant_id, metric, n_periods)` | Proxies `GET /kpis/{tenant_id}/history` for a given metric   |


#### Why BigQuery for the Gold Layer

All KPI data is tabular and time-series in nature (a metric value per tenant per period). BigQuery is
the right fit because:

- It is optimized for analytical queries: trend lookups, historical aggregations, `ORDER BY period DESC LIMIT n`
- It is the natural "Gold Layer" / BI store in GCP, matching our design's terminology
- Agents run analytical queries (e.g. "last 12 weeks of burn rate") - these map directly to SQL over BigQuery
- Firestore is a document store and would require manual indexing and pagination for time-series queries

The Data Serving Layer wraps BigQuery with a typed REST API so agents never write SQL directly.
They call the MCP tools, which call the REST API, which queries BigQuery.

#### Which Agents Fetch from BigQuery (via MCP)


| Agent                          | MCP Tools Used                                    | Data Fetched                                                              |
| ------------------------------ | ------------------------------------------------- | ------------------------------------------------------------------------- |
| Financial Intelligence Agent   | `get_financial_kpis`, `get_trend_data`            | Burn rate, revenue growth, cash flow - latest + history                   |
| Sales & CRM Intelligence Agent | `get_sales_kpis`, `get_trend_data`                | Conversion rate, deal velocity, churn - latest + history                  |
| Insight Synthesis Agent        | none - receives outputs from the two agents above | Works on structured insight objects, not raw KPI data                     |
| Orchestrator Agent             | none - triggers sub-agents and passes `tenant_id` | Coordination only; sub-agents are responsible for their own data fetching |


---

### Domain: Operational Intelligence

**Owner: Gilbert & Rick**

All agents are implemented with the Google ADK. The Orchestrator Agent is exposed as a Cloud Run
service. Sub-agents are invoked via ADK agent-to-agent calls (A2A).

#### 4. Orchestrator Agent

- Type: ADK Agent, exposed via Cloud Run
- Trigger: Pub/Sub push subscription on `kpis-computed`


| Operation                           | Description                                                            |
| ----------------------------------- | ---------------------------------------------------------------------- |
| `run_pipeline(tenant_id, trace_id)` | Entry point: queries KPIs, dispatches sub-agents, publishes result     |
| `get_pipeline_status(run_id)`       | Returns current status and step of a running or completed pipeline run |


#### 5. Financial Intelligence Agent

- Type: ADK Agent (sub-agent, invoked by Orchestrator)
- MCP: uses KPI Tools MCP server to retrieve financial KPI data


| Operation                                         | Description                                                                                                              |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `analyze_financial_kpis(tenant_id, kpi_snapshot)` | LLM-driven analysis of burn rate, revenue growth, cash flow; returns structured insight with severity and recommendation |


#### 6. Sales & CRM Intelligence Agent

- Type: ADK Agent (sub-agent, invoked by Orchestrator)
- MCP: uses KPI Tools MCP server to retrieve sales/CRM KPI data


| Operation                                         | Description                                                                                                               |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `analyze_sales_crm_kpis(tenant_id, kpi_snapshot)` | LLM-driven analysis of conversion rate, deal velocity, churn; returns structured insight with severity and recommendation |


#### 7. Insight Synthesis Agent

- Type: ADK Agent (sub-agent, invoked by Orchestrator after Financial and Sales agents complete)


| Operation                                                 | Description                                                                                                                                  |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `synthesize_insights(financial_insights, sales_insights)` | Combines all agent outputs into a single normalized insight payload; detects cross-domain compound risks; assigns final severity per insight |


---

### Domain: Reporting & Delivery

**Owner: Tycho**

#### 8. Composition Service

- Type: Cloud Function (FaaS)
- Trigger: Pub/Sub push subscription on `insights-ready`


| Operation                                    | Description                                                                                            |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `compose_report(tenant_id, insight_payload)` | Assembles insight sections into a structured report document (Markdown or HTML)                        |
| `format_report(report_data, template)`       | Applies a report template to structure the content into sections (executive summary, financial, sales) |


#### 9. Delivery Service

- Type: Cloud Run (FastAPI, RESTful)
- Trigger: Pub/Sub push subscription on `report-composed`


| Operation                            | Description                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------ |
| `deliver_report(tenant_id, report)`  | Dispatches the report via configured channel (mock email log or Slack webhook) |
| `GET /deliveries/{tenant_id}/latest` | Returns metadata and status of the most recent report delivery                 |


---

## Operations Count Summary


| Domain                   | Service / Agent                | Operations |
| ------------------------ | ------------------------------ | ---------- |
| KPI & Analytics          | KPI Computation Service        | 3          |
| KPI & Analytics          | Data Serving Layer             | 3          |
| Operational Intelligence | Orchestrator Agent             | 2          |
| Operational Intelligence | Financial Intelligence Agent   | 1          |
| Operational Intelligence | Sales & CRM Intelligence Agent | 1          |
| Operational Intelligence | Insight Synthesis Agent        | 1          |
| Reporting & Delivery     | Composition Service            | 2          |
| Reporting & Delivery     | Delivery Service               | 2          |
| **Total**                |                                | **15**     |


Minimum required: 12. Services/agents (excl. MCP server): **8** across **3 domains**.

---

## End-to-End Demo Scenario

1. Upload mock financial and sales/CRM CSV files to GCS buckets
2. HTTP-trigger the KPI Computation Service for `tenant_id = "pulse-demo"`
3. KPI Computation Service computes and stores KPIs, publishes `kpis-computed`
4. Orchestrator Agent receives the Pub/Sub push, calls Financial + Sales agents in parallel via ADK A2A
5. Each agent fetches relevant KPI data via the KPI Tools MCP server, runs LLM reasoning, returns structured insights
6. Insight Synthesis Agent combines outputs, publishes `insights-ready`
7. Composition Service assembles the report, publishes `report-composed`
8. Delivery Service dispatches the report (mock Slack webhook or logged output), publishes `report-delivered`

---

## Repository Structure (Proposed)

```
ada-pulse-2026/
  kpi-analytics/
    kpi-computation/        # Cloud Function - FaaS
    data-serving/           # Cloud Run - FastAPI
    kpi-mcp-server/         # Custom MCP server
    mock-data/              # Seed scripts + sample CSV files for GCS
  operational-intelligence/
    orchestrator-agent/     # ADK Orchestrator, Cloud Run
    financial-agent/        # ADK sub-agent
    sales-crm-agent/        # ADK sub-agent
    insight-synthesis-agent/ # ADK sub-agent
  reporting-delivery/
    composition-service/    # Cloud Function - FaaS
    delivery-service/       # Cloud Run - FastAPI
  infra/
    pubsub-setup.sh         # Pub/Sub topic + subscription creation
    gcs-setup.sh            # GCS bucket + CSV upload
    bigquery-setup.sh       # BigQuery dataset + kpi_snapshots table schema
    deploy.sh               # Deployment script
  docs/
    ADA-Design-Report.pdf
    Assignment 2 - Implementation of the Design.pdf
    Assignment2-Outline.md
```

---

## Team Responsibilities


| Member         | Domain / Component                                                                          |
| -------------- | ------------------------------------------------------------------------------------------- |
| Thom           | Main architecture, infra setup (Pub/Sub, GCS, deployment), help Jelles with KPI & Analytics |
| Jelles         | KPI Computation Service, Data Serving Layer, KPI Tools MCP server, mock data                |
| Gilbert & Rick | All ADK agents: Orchestrator, Financial, Sales & CRM, Insight Synthesis                     |
| Tycho          | Composition Service, Delivery Service                                                       |


