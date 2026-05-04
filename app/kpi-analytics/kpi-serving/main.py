from __future__ import annotations

import logging

from fastapi import FastAPI

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
