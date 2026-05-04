from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DomainsResponse(BaseModel):
    tenant_id: str
    domains: list[str]


class MetricNameItem(BaseModel):
    metric_name: str


class MetricsResponse(BaseModel):
    tenant_id: str
    metrics: list[MetricNameItem]


class KpiSnapshotItem(BaseModel):
    tenant_id: str
    period_start: date
    period_end: date
    period_grain: str
    domain: str
    metric_name: str
    metric_value: float | None
    metric_unit: str
    computed_at: datetime
    run_id: str
    trace_id: str


class LatestListResponse(BaseModel):
    tenant_id: str
    items: list[KpiSnapshotItem]


class HistoryItem(BaseModel):
    period_start: date
    period_end: date
    metric_value: float | None
    metric_unit: str
    computed_at: datetime


class HistoryResponse(BaseModel):
    tenant_id: str
    domain: str
    metric_name: str
    limit: int
    items: list[HistoryItem]
