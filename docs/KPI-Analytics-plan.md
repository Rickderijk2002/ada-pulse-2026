# KPI & Analytics - Main Plan

## Goal

Build the KPI & Analytics domain as a working data product that:
- ingests mock raw CSV data from GCS,
- computes KPI metrics in a FaaS service,
- stores KPI snapshots in BigQuery as the Gold Layer,
- exposes KPI data through a REST Data Serving Layer,
- and provides KPI access to agents through a custom MCP server.

---

## Scope

- Use mock raw financial and sales/CRM CSV files in GCS.
- Implement KPI computation for:
  - Financial: burn rate, cash flow, revenue growth, outstanding invoices
  - Sales/CRM: incoming leads, conversion rate, deal velocity, churn rate
- Store historical KPI outputs in BigQuery.
- Publish a `kpis-computed` event to Pub/Sub after successful computation.

---

## Main Components

### 1) Mock Dataset and Data Contract
- Prepare realistic financial and sales/CRM CSV datasets.
- Define and document the input schema and expected field types.
- Include enough historical periods to support trend analysis.

### 2) BigQuery Gold Layer
- Create a BigQuery dataset and `kpi_snapshots` table.
- Use a tabular schema aligned to `tenant_id`, `period`, `metric_name`, `metric_value`, and timestamps.
- Ensure data model supports history queries and trend analysis.

#### 2.1) The KPIs

All KPI values are computed from cleaned raw data in GCS, then written to BigQuery Gold table 'gold_kpi_snapshots'.

##### Financial Section

- **burn_rate**  
  `SUM(expenses)` within the week
- **cash_flow**  
  `SUM(cash_inflow) - SUM(cash_outflow)` within the week
- **revenue_growth**  
  `(revenue_this_week - revenue_previous_week) / NULLIF(revenue_previous_week, 0)`  
  where `revenue_this_week = SUM(revenue)` in current week
- **outstanding_invoices**  
  `MAX(outstanding_invoices)` in the week (end-of-period proxy)

##### Sales/CRM

- **incoming_leads**  
  `SUM(leads)` within the week
- **conversion_rate**  
  `SUM(new_deals) / NULLIF(SUM(leads), 0)` within the week  
  (recomputed from raw counts, not taken from raw conversion column)
- **deal_velocity**  
  `SUM(new_deals)` within the week (MVP proxy for velocity)
- **churn_rate**  
  `SUM(churn_rate * leads) / NULLIF(SUM(leads), 0)` within the week  
  (lead-weighted average from raw churn observations)

#### 2.2) Gold Table Design (BigQuery)

Use one Gold table for all KPI values (long format), so agents can fetch latest/history/trends with
simple filters.

**Table:** `gold_kpi_snapshots`

| Column | Type | Description |
|---|---|---|
| `tenant_id` | STRING | Tenant identifier (for now: `pulse-demo`) |
| `period_start` | DATE | Start of KPI period |
| `period_end` | DATE | End of KPI period |
| `period_grain` | STRING | Aggregation level, e.g. `weekly` |
| `domain` | STRING | `financial` or `sales_crm` |
| `metric_name` | STRING | KPI name |
| `metric_value` | NUMERIC | KPI value |
| `metric_unit` | STRING | `currency`, `ratio`, or `count` |
| `computed_at` | TIMESTAMP | Computation timestamp |
| `run_id` | STRING | KPI computation run identifier |
| `trace_id` | STRING | Correlation ID for end-to-end tracing |

**Recommended BigQuery settings**
- Partition by `period_end`
- Cluster by `tenant_id`, `metric_name`

### 3) KPI Computation Service (FaaS)
- Build a Cloud Function that:
  - reads CSV data from GCS,
  - validates input structure,
  - computes KPI values,
  - writes computed KPI rows to BigQuery,
  - publishes `kpis-computed` to Pub/Sub.
- Keep runs deterministic and safe to re-run.

### 4) Data Serving Layer (REST)
- Build a Cloud Run FastAPI service that queries BigQuery and exposes:
  - `GET /kpis/{tenant_id}/latest`
  - `GET /kpis/{tenant_id}/history`
  - `GET /kpis/{tenant_id}/trends`
- This service is the stable read interface for downstream domains.

### 5) KPI MCP Server
- Build a custom MCP server that wraps the Data Serving Layer endpoints as tools:
  - `get_financial_kpis`
  - `get_sales_kpis`
  - `get_trend_data`
- Financial and Sales/CRM agents use these tools for analysis.

---

## Integration Points

- **Upstream input:** mock raw CSV files in GCS (simulating Data Integration output).
- **Downstream event:** `kpis-computed` Pub/Sub message for Operational Intelligence.
- **Downstream data access:** REST + MCP tools used by Financial and Sales/CRM agents.

---

## Implementation Steps (Execution Order)

### Step 1 - Prepare and upload ingest data
- Generate cleaned raw datasets from Mockaroo source files.
- Upload `financial_clean.csv` and `sales_marketing_clean.csv` to the GCS ingest bucket.
- Upload `ready.json` marker in the same run prefix to signal data is complete.

### Step 2 - Configure event trigger
- Configure GCS -> Pub/Sub/Eventarc trigger for object finalize events.
- Trigger KPI compute only when uploaded object path ends with `ready.json`.
- Pass bucket name and object path to the KPI function.

### Step 3 - Create BigQuery raw and gold tables
- Create gold table: `gold_kpi_snapshots`.
- Set `gold_kpi_snapshots` partitioning on `period_end` and clustering on `tenant_id`, `metric_name`.

### Step 4 - Implement KPI Computation FaaS
- Read the run prefix from marker event and load both CSV files from GCS.
- Validate schema and apply transformations/rules.
- Load/merge cleaned records into raw BigQuery tables.
- Compute weekly KPI values for all 8 KPIs.
- Upsert results to `gold_kpi_snapshots` using key: `tenant_id`, `period_end`, `period_grain`, `metric_name`.
- Publish `kpis-computed` event with `run_id`, `trace_id`, and `tenant_id`.

### Step 5 - Build Data Serving API (Cloud Run)
- Implement read endpoints:
  - `GET /kpis/{tenant_id}/domains`
  - `GET /kpis/{tenant_id}/latest?domain={domain}`
  - `GET /kpis/{tenant_id}/history?domain={domain}&metric_name={metric_name}&periods={n}`
  - `GET /kpis/{tenant_id}/snapshot?period_end={YYYY-MM-DD}`
  - `GET /kpis/{tenant_id}/trends?domain={domain}&periods={n}` (optional helper)
- Query only from `gold_kpi_snapshots`.
- Return consistent response format for all KPI records so agents can parse domain, metric, latest values, and history uniformly.

### Step 6 - Build KPI MCP server
- Wrap API endpoints in MCP tools:
  - `list_kpi_domains(tenant_id)`
  - `list_kpis_in_domain(tenant_id, domain)`
  - `get_latest_kpis(tenant_id, domain)`
  - `get_kpi_history(tenant_id, domain, metric_name, periods)`
  - `get_period_snapshot(tenant_id, period_end)`
- Add input validation for tenant, domain, metric, and period range.
- Agent flow should be: discover KPIs for domain -> fetch latest domain KPIs -> fetch per-KPI history -> run analysis.

### Step 7 - End-to-end validation
- Upload a new ingest run to GCS.
- Verify trigger fires and KPI function completes successfully.
- Verify new KPI rows appear in `gold_kpi_snapshots`.
- Verify API returns latest/history/trend data correctly.
- Verify MCP tools return data used by Financial and Sales/CRM agents.

---

## Deliverable Checklist

- Mock CSV dataset available in GCS.
- BigQuery Gold Layer created and queryable.
- KPI Computation Cloud Function deployed and working.
- `kpis-computed` Pub/Sub event published after successful runs.
- Data Serving Layer API deployed with latest/history/trends endpoints.
- KPI MCP server running with required tools for agents.
- End-to-end KPI flow verified: CSV -> compute -> BigQuery -> API/MCP -> Pub/Sub event.

---

