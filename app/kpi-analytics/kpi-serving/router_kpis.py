from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import ValidationError

from bq_repository import BQRepositoryError, BigQueryRepository, get_repository
from config import Settings, get_settings
from schemas import (
    DomainsResponse,
    HistoryItem,
    HistoryResponse,
    KpiSnapshotItem,
    LatestListResponse,
    MetricNameItem,
    MetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/{tenant_id}", tags=["kpis"])


def require_allowed_tenant(
    tenant_id: str = Path(..., description="Tenant identifier."),
    settings: Settings = Depends(get_settings),
) -> str:
    if tenant_id != settings.allowed_tenant_id:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant_id


AllowedTenantDep = Annotated[str, Depends(require_allowed_tenant)]
RepoDep = Annotated[BigQueryRepository, Depends(get_repository)]


@router.get("/domains", response_model=DomainsResponse)
def list_domains(tenant_ok: AllowedTenantDep, repo: RepoDep) -> DomainsResponse:
    try:
        domains = repo.query_domains(tenant_ok)
    except BQRepositoryError:
        logger.exception("BigQuery failed for domains")
        raise HTTPException(status_code=502, detail="Data store unavailable") from None
    return DomainsResponse(tenant_id=tenant_ok, domains=domains)


@router.get("/metrics", response_model=MetricsResponse)
def list_metrics(
    tenant_ok: AllowedTenantDep,
    repo: RepoDep,
    domain: str | None = Query(default=None),
) -> MetricsResponse:
    try:
        names = repo.query_metric_names(tenant_ok, domain)
    except BQRepositoryError:
        logger.exception("BigQuery failed for metrics")
        raise HTTPException(status_code=502, detail="Data store unavailable") from None
    return MetricsResponse(
        tenant_id=tenant_ok,
        metrics=[MetricNameItem(metric_name=n) for n in names],
    )


@router.get("/latest", response_model=LatestListResponse)
def list_latest(
    tenant_ok: AllowedTenantDep,
    repo: RepoDep,
    domain: str | None = Query(default=None),
) -> LatestListResponse:
    try:
        rows = repo.query_latest_all(tenant_ok, domain)
    except BQRepositoryError:
        logger.exception("BigQuery failed for latest list")
        raise HTTPException(status_code=502, detail="Data store unavailable") from None
    try:
        items = [KpiSnapshotItem(**r) for r in rows]
    except ValidationError:
        logger.exception("Row shape mismatch")
        raise HTTPException(status_code=502, detail="Unexpected data shape") from None
    return LatestListResponse(tenant_id=tenant_ok, items=items)


@router.get("/latest/{domain}/{metric_name}", response_model=KpiSnapshotItem)
def get_latest_single(
    tenant_ok: AllowedTenantDep,
    repo: RepoDep,
    domain: str = Path(...),
    metric_name: str = Path(...),
) -> KpiSnapshotItem:
    try:
        row = repo.query_latest_single(tenant_ok, domain, metric_name)
    except BQRepositoryError:
        logger.exception("BigQuery failed for latest single")
        raise HTTPException(status_code=502, detail="Data store unavailable") from None
    if row is None:
        raise HTTPException(status_code=404, detail="KPI snapshot not found")
    try:
        return KpiSnapshotItem(**row)
    except ValidationError:
        logger.exception("Row shape mismatch")
        raise HTTPException(status_code=502, detail="Unexpected data shape") from None


@router.get(
    "/metrics/{domain}/{metric_name}/history",
    response_model=HistoryResponse,
)
def get_metric_history(
    tenant_ok: AllowedTenantDep,
    repo: RepoDep,
    domain: str = Path(...),
    metric_name: str = Path(...),
    limit: int | None = Query(
        default=None,
        ge=1,
        description="Number of periods (weeks); capped server-side.",
    ),
    settings: Settings = Depends(get_settings),
) -> HistoryResponse:
    cap = settings.history_max_limit
    default = settings.history_default_limit
    resolved = limit if limit is not None else default
    effective = max(1, min(resolved, cap))
    try:
        rows = repo.query_history(tenant_ok, domain, metric_name, effective)
    except BQRepositoryError:
        logger.exception("BigQuery failed for history")
        raise HTTPException(status_code=502, detail="Data store unavailable") from None
    try:
        items = [HistoryItem(**r) for r in rows]
    except ValidationError:
        logger.exception("Row shape mismatch")
        raise HTTPException(status_code=502, detail="Unexpected data shape") from None
    return HistoryResponse(
        tenant_id=tenant_ok,
        domain=domain,
        metric_name=metric_name,
        limit=effective,
        items=items,
    )
