# 1. Summary of Assignment 2

Assignment 2 requires the team to implement a simplified but working version of the architecture from Assignment 1.

The goal is to deliver a credible end-to-end slice that demonstrates how key components collaborate in practice.

## Requirements

The implementation should demonstrate:

- At least 4 microservices and or agents, excluding external APIs and MCP servers  
- At least 12 operations across all services and or agents  
- Components from at least 2 domains in the DDD design  
- Composition through orchestration and or choreography  
- A mix of RESTful services and FaaS components  
- Clearly stated assumptions  
- A working system for demonstration  

## Recommended scope

Generate a weekly operational report for a tenant.

This scenario links KPI retrieval, operational analysis, and report generation into one workflow.

# 2. Recommended System Scope

- KPI and Analytics, provide KPI snapshots and KPI history  
- Operational Intelligence, analyse KPIs and produce insights  
- Reporting and Delivery, generate report preview and output  
- Cross-cutting concerns, security, resilience, observability  

# 3. Build Allocation

| Team member        | Ownership                        | Responsibility |
|------------------|--------------------------------|----------------|
| Jelles Duin      | KPI and Analytics              | KPI service and endpoints |
| Thom Verzantvoort| Operational Intelligence       | Analysis flow and reasoning |
| Rick de Rijk     | Reporting and Delivery         | Report generation and delivery |
| Tycho van Rooij  | Circuit Breaker                | Resilience layer |
| Gilbert Laanen   | Observability                  | Tracing and logging |

## Design patterns

- Pattern 1, API Gateway for security  
- Pattern 2, Circuit Breaker for resilience  
- Pattern 3, Observability with distributed tracing  

# 4. End-to-End Scenario

- Workflow request starts report generation  
- KPI service returns snapshot  
- Operational Intelligence analyses KPIs  
- Reporting service generates report  
- Observability tracks full flow  

# 5. Component-Level Build Plan

## 5.1 KPI and Analytics service

### Purpose
Provide KPI data

### Files
- services/kpi_service/app.py  
- routes.py  
- models.py  
- data/mock_kpis.json  
- utils/tracing.py  

### Operations
- health_check  
- get_financial_kpis  
- get_sales_kpis  
- get_kpi_history  
- get_tenant_kpi_snapshot  

### Endpoints
- GET /health  
- GET /kpis/financial/{tenant_id}  
- GET /kpis/sales/{tenant_id}  
- GET /kpis/history/{tenant_id}  
- GET /kpis/snapshot/{tenant_id}  

### Tracing
Accept and log X-Trace-Id  

## 5.2 Operational Intelligence service

### Purpose
Convert KPIs into insights  

### Files
- services/operational_intelligence/app.py  
- routes.py  
- logic.py  
- models.py  
- utils/tracing.py  

### Operations
- run_operational_analysis  
- analyze_financial_signals  
- analyze_sales_signals  
- analyze_cross_domain_risks  
- synthesize_insights  

### Endpoints
- POST /analysis/run  
- POST /analysis/financial  
- POST /analysis/sales  
- POST /analysis/cross-domain  
- POST /analysis/synthesize  

### Tracing
Propagate trace ID  

## 5.3 Reporting and Delivery service

### Purpose
Generate reports  

### Files
- services/report_service/app.py  
- routes.py  
- formatter.py  
- models.py  
- templates/report_template.txt  
- utils/tracing.py  

### Operations
- generate_report  
- preview_report  
- deliver_report  

### Endpoints
- POST /reports/generate  
- POST /reports/preview  
- POST /reports/deliver  

## 5.4 Resilience layer

### Files
- shared/resilience/circuit_breaker.py  
- shared/resilience/http_client.py  

### Capabilities
- Timeout handling  
- Retry logic  
- Circuit breaker states  
- Fallback responses  

## 5.5 Observability layer

### Files
- shared/observability/tracing.py  
- shared/observability/logging.py  
- shared/observability/models.py  

### Logging fields
- trace_id  
- service_name  
- operation  
- tenant_id  
- timestamp  
- duration_ms  
- status  
- error_message  

# 6. Minimum Viable Operations

## KPI and Analytics
- health_check  
- get_financial_kpis  
- get_sales_kpis  
- get_kpi_history  
- get_tenant_kpi_snapshot  

## Operational Intelligence
- run_operational_analysis  
- analyze_financial_signals  
- analyze_sales_signals  
- analyze_cross_domain_risks  
- synthesize_insights  

## Reporting
- generate_report  
- preview_report  
- deliver_report  

# 7. Focus for Pattern 3

### Responsibilities

- Define trace propagation via X-Trace-Id  
- Create shared logging helper  
- Ensure trace flows across services  
- Enable full workflow reconstruction  

### Goal

One workflow must be fully traceable end-to-end  

# 8. Assumptions

- KPI data may be mock data  
- Analysis may be rule-based  
- Authentication may be simplified  
- Report delivery may be simulated  
- MCP only if feasible  

# 9. Final Recommendation

Keep the implementation:

- Narrow  
- Coherent  
- Demonstrable  

Deliver one strong vertical slice with clear service boundaries and observable behaviour.