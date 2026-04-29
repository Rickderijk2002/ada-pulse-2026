Assignment 2. Updated Summary, Corrected Build
Allocation, and Build Plan
Pulse. Operational Intelligence Platform for SMEs
Updated to reflect the confirmed Section 3 pattern distribution
1. Summary of Assignment 2
Assignment 2 requires the team to implement a simplified but working version of the architecture
from Assignment 1. The goal is not to build the entire Pulse platform, but to deliver a credible end-
to-end slice that shows how key components collaborate in practice.
In practical terms, the implementation should demonstrate the following:
 at least 4 microservices and or agents, without counting external APIs and MCP servers
 at least 12 operations across all implemented services and or agents
 components from at least 2 domains in the DDD design, preferably core domains first
 composition through orchestration and or choreography
 a mix of RESTful services and FaaS style components
 clear assumptions, because the implementation may be simplified as long as the intended
behaviour is still represented
 a demonstrable working system for the lab presentation
For Pulse, the strongest scope is a narrow vertical slice: generate a weekly operational report for a
tenant. This scenario links KPI retrieval, operational analysis, and report generation in one clear
workflow and fits the original design well.
2. Recommended System Scope for the Team
The most practical implementation scope remains:
 KPI and Analytics. provide KPI snapshots and KPI history
 Operational Intelligence. analyse the KPIs and produce structured insights
 Reporting and Delivery. generate a report preview and a delivery output
 cross-cutting concerns. add security, resilience, and observability patterns across the system
This keeps the implementation aligned with the design report while preventing the team from
trying to build the whole platform. It also gives a clean base for Section 3, because the architecture
patterns can be demonstrated on real service interactions.
3. Corrected Build Allocation
Based on the confirmed Section 3 task distribution and the earlier domain ownership from
Assignment 1, the following build allocation is the most logical and coherent for Assignment 2.
Team member Primary build ownership Main responsibility in the
implementation
Jelles Duin KPI and Analytics service
Build the KPI service and
expose financial, sales, history,
and snapshot endpoints.
Thom Verzantvoort Operational Intelligence
service or agent layer
Build the analysis flow,
including financial analysis,
sales analysis, cross-domain
reasoning, and synthesis.
Rick de Rijk
Reporting and Delivery
service, optionally workflow
entrypoint
Build report generation,
preview, delivery, and
optionally the central
workflow starter.
Tycho van Rooij Pattern 2. Circuit Breaker and
resilience layer
Add timeouts, retries, and
circuit breaker behaviour
around service interactions.
Gilbert Laanen Pattern 3. Observability with
distributed tracing
Add trace propagation,
structured logging, and end-to-
end tracing across the
implemented workflow.
This means the architecture patterns in Section 3.3 are not workflow patterns from Lab 8, but
quality attribute patterns. Pattern 1 is API Gateway for security, Pattern 2 is Circuit Breaker for
resilience, and Pattern 3 is Observability through distributed tracing.
4. End-to-End Scenario for the Demo
 A workflow request starts a weekly report run for a tenant.
 The KPI service returns a tenant KPI snapshot.
 The Operational Intelligence service analyses the KPI snapshot and produces insights.
 The Reporting service converts the insight payload into a report preview and optional delivery
output.
 Tracing and resilience features make the flow observable and robust during the demo.
5. Component-Level Build Plan
5.1 KPI and Analytics service, Jelles
Purpose. Provide the KPI data required by the rest of the system.
 Suggested files: services/kpi_service/app.py, routes.py, models.py, data/mock_kpis.json,
utils/tracing.py, requirements.txt
 Suggested operations: health_check, get_financial_kpis, get_sales_kpis, get_kpi_history,
get_tenant_kpi_snapshot
 Suggested endpoints: GET /health, GET /kpis/financial/{tenant_id}, GET /kpis/sales/{tenant_id},
GET /kpis/history/{tenant_id}, GET /kpis/snapshot/{tenant_id}
 Tracing requirement: accept and log X-Trace-Id on every request
5.2 Operational Intelligence service, Thom
Purpose. Turn KPI snapshots into structured business insights.
 Suggested files: services/operational_intelligence/app.py, routes.py, logic.py, models.py,
utils/tracing.py, requirements.txt
 Suggested operations: run_operational_analysis, analyze_financial_signals,
analyze_sales_signals, analyze_cross_domain_risks, synthesize_insights
 Suggested endpoints: POST /analysis/run, POST /analysis/financial, POST /analysis/sales, POST
/analysis/cross-domain, POST /analysis/synthesize
 Tracing requirement: preserve the incoming trace ID and include it in all internal logs and
outgoing calls
5.3 Reporting and Delivery service, Rick
Purpose. Convert structured insights into a user-facing output.
 Suggested files: services/report_service/app.py, routes.py, formatter.py, models.py,
templates/report_template.txt, utils/tracing.py, requirements.txt
 Suggested operations: generate_report, preview_report, deliver_report
 Suggested endpoints: POST /reports/generate, POST /reports/preview, POST /reports/deliver
 Optional extension: build gateway/app.py and routes.py for a central workflow starter
5.4 Resilience layer, Tycho
Purpose. Prevent one failing dependency from bringing down the entire workflow.
 Suggested files: shared/resilience/circuit_breaker.py, shared/resilience/http_client.py, optionally
services/notification_service if a failure path is shown
 Suggested operations or capabilities: timeout handling, retry wrapper, open or close circuit
logic, fallback response handling
 Main implementation point: wrap calls between workflow entrypoint, KPI service, Operational
Intelligence, and Reporting service
 Section 3.3 angle: explain how circuit breaker improves resilience and fault isolation
5.5 Observability layer, Gilbert
Purpose. Make one workflow run traceable across all implemented services.
 Suggested files: shared/observability/tracing.py, shared/observability/logging.py,
shared/observability/models.py
 Core responsibilities: generate or propagate trace IDs, enforce a shared logging format, and
correlate logs across services
 Fields to log: trace_id, service_name, operation, tenant_id, timestamp, duration_ms, status, and
error_message when relevant
 Main implementation point: ensure the same trace ID flows through gateway, KPI service,
Operational Intelligence, and Reporting service
This is a cross-cutting concern rather than a standalone domain service. The implementation
should therefore be integrated into all major services, not isolated in one place only.
6. Minimum Viable Operation Set
Component area Operations
KPI and Analytics
health_check, get_financial_kpis,
get_sales_kpis, get_kpi_history,
get_tenant_kpi_snapshot
Operational Intelligence
run_operational_analysis,
analyze_financial_signals,
analyze_sales_signals,
analyze_cross_domain_risks,
synthesize_insights
Reporting and Delivery generate_report, preview_report,
deliver_report
Workflow entrypoint, optional generate_weekly_report_workflow,
get_workflow_status
Even without the optional workflow entrypoint, the team still remains above the required
minimum of 12 operations.
7. Specific Focus for Gilbert, Pattern 3
Gilbert’s contribution should now be framed around observability, not hierarchical decomposition.
The core idea is that every report run receives a trace ID, and that this identifier is propagated
across service boundaries so that the full workflow can be reconstructed from the logs.
 define the trace propagation approach, for example through an X-Trace-Id header
 create a shared logging helper used by all services
 ensure that the main workflow produces a readable end-to-end trace in the demo
 write Section 3.3 text that explains the observability rationale and how distributed tracing
improves debugging and operational visibility
8. Assumptions
 KPI data may be based on mock data or a small test dataset.
 Analytical logic may be rule-based or lightly simulated, rather than fully intelligent.
 Authentication can be minimal or simulated if Pattern 1 is only partly implemented.
 Report delivery may be simulated as preview output or a stored result rather than a fully
integrated external email flow.
 MCP integration should only be included if it remains feasible within the available time.
9. Final Recommendation
The strongest strategy is to keep the implementation narrow, coherent, and demonstrable. The
team should avoid trying to build the entire Pulse platform. Instead, it should deliver one
convincing vertical slice with clear service boundaries, a clean end-to-end scenario, and visible
evidence that the selected architecture patterns have been applied in the implementation.
For Gilbert specifically, the main correction is clear. Pattern 3 is Observability with Distributed
Tracing, and the implementation should focus on trace propagation, structured logging, and end-
to-end visibility across the workflow.

