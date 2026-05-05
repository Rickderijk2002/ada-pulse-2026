from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from router_kpis import router as kpis_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

app = FastAPI(
    title="Pulse KPI Serving API",
    version="0.1.0",
    description=(
        "Read-only KPI snapshots from BigQuery (`gold_kpi_snapshots`). "
        "Tenant path must match the configured demo tenant. "
        "OpenAPI is available at /docs."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(kpis_router, prefix="/kpis")

# --- MCP Integration ---
# Exposes selected KPI endpoints as agent-callable MCP tools.
# Available at: /mcp  (same port as the REST API)
mcp = FastApiMCP(
    app,
    name="Pulse KPI Tools",
    description=(
        "MCP tools for retrieving KPI snapshots from the Pulse gold layer. "
        "Use get_latest_kpis to get the most recent values and "
        "get_kpi_history for trend data over multiple weeks."
    ),
    include_operations=[
        "list_kpi_domains",
        "list_kpi_metrics",
        "get_latest_kpis",
        "get_latest_kpi_single",
        "get_kpi_history",
    ],
)
mcp.mount_http(app, mount_path="/mcp")
