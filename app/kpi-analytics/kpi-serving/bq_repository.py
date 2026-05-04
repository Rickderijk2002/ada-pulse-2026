from __future__ import annotations

import logging
from typing import Any

from google.cloud import bigquery

from config import Settings, get_settings

logger = logging.getLogger(__name__)

_PERIOD_GRAIN = "weekly"


class BQRepositoryError(Exception):
    pass


def _sql_table_ref(table_id: str) -> str:
    parts = [p.strip() for p in table_id.split(".")]
    if len(parts) != 3 or any(not p for p in parts):
        raise BQRepositoryError(
            "Configured bq_table_id must be fully qualified project.dataset.table",
        )
    for segment in parts:
        if any(c in segment for c in " `\n;'\"\t"):
            raise BQRepositoryError("Invalid characters in table id segment")
    return "`" + ".".join(parts) + "`"


def _rows(job: bigquery.QueryJob) -> list[dict[str, Any]]:
    return [dict(row) for row in job.result()]


class BigQueryRepository:
    def __init__(self, client: bigquery.Client, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._table_sql = _sql_table_ref(settings.bq_table_id)

    def query_domains(self, tenant_id: str) -> list[str]:
        sql = """
        SELECT DISTINCT domain AS domain
        FROM TABLE_REF_PLACEHOLDER
        WHERE tenant_id = @tenant_id AND period_grain = @period_grain
        ORDER BY domain
        """.replace(
            "TABLE_REF_PLACEHOLDER",
            self._table_sql,
        )
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
            bigquery.ScalarQueryParameter("period_grain", "STRING", _PERIOD_GRAIN),
        ]
        rows = self._run(sql, params)
        return [str(r["domain"]) for r in rows]

    def query_metric_names(self, tenant_id: str, domain: str | None) -> list[str]:
        sql = """
        SELECT DISTINCT metric_name AS metric_name
        FROM TABLE_REF_PLACEHOLDER
        WHERE tenant_id = @tenant_id
          AND period_grain = @period_grain
          AND (@domain IS NULL OR domain = @domain)
        ORDER BY metric_name
        """.replace(
            "TABLE_REF_PLACEHOLDER",
            self._table_sql,
        )
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
            bigquery.ScalarQueryParameter("period_grain", "STRING", _PERIOD_GRAIN),
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
        ]
        rows = self._run(sql, params)
        return [str(r["metric_name"]) for r in rows]

    def query_latest_all(
        self,
        tenant_id: str,
        domain: str | None,
    ) -> list[dict[str, Any]]:
        sql = """
        WITH ranked AS (
          SELECT
            tenant_id,
            period_start,
            period_end,
            period_grain,
            domain,
            metric_name,
            metric_value,
            metric_unit,
            computed_at,
            run_id,
            trace_id,
            ROW_NUMBER() OVER (
              PARTITION BY tenant_id, domain, metric_name
              ORDER BY period_end DESC, computed_at DESC
            ) AS rn
          FROM TABLE_REF_PLACEHOLDER
          WHERE tenant_id = @tenant_id
            AND period_grain = @period_grain
            AND (@domain IS NULL OR domain = @domain)
        )
        SELECT
          tenant_id,
          period_start,
          period_end,
          period_grain,
          domain,
          metric_name,
          metric_value,
          metric_unit,
          computed_at,
          run_id,
          trace_id
        FROM ranked
        WHERE rn = 1
        ORDER BY domain, metric_name
        """.replace(
            "TABLE_REF_PLACEHOLDER",
            self._table_sql,
        )
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
            bigquery.ScalarQueryParameter("period_grain", "STRING", _PERIOD_GRAIN),
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
        ]
        return self._run(sql, params)

    def query_latest_single(
        self,
        tenant_id: str,
        domain: str,
        metric_name: str,
    ) -> dict[str, Any] | None:
        sql = """
        WITH ranked AS (
          SELECT
            tenant_id,
            period_start,
            period_end,
            period_grain,
            domain,
            metric_name,
            metric_value,
            metric_unit,
            computed_at,
            run_id,
            trace_id,
            ROW_NUMBER() OVER (
              PARTITION BY tenant_id, domain, metric_name
              ORDER BY period_end DESC, computed_at DESC
            ) AS rn
          FROM TABLE_REF_PLACEHOLDER
          WHERE tenant_id = @tenant_id
            AND period_grain = @period_grain
            AND domain = @domain
            AND metric_name = @metric_name
        )
        SELECT
          tenant_id,
          period_start,
          period_end,
          period_grain,
          domain,
          metric_name,
          metric_value,
          metric_unit,
          computed_at,
          run_id,
          trace_id
        FROM ranked
        WHERE rn = 1
        """.replace(
            "TABLE_REF_PLACEHOLDER",
            self._table_sql,
        )
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
            bigquery.ScalarQueryParameter("period_grain", "STRING", _PERIOD_GRAIN),
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
            bigquery.ScalarQueryParameter("metric_name", "STRING", metric_name),
        ]
        rows = self._run(sql, params)
        if not rows:
            return None
        return rows[0]

    def query_history(
        self,
        tenant_id: str,
        domain: str,
        metric_name: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
          period_start,
          period_end,
          metric_value,
          metric_unit,
          computed_at
        FROM TABLE_REF_PLACEHOLDER
        WHERE tenant_id = @tenant_id
          AND period_grain = @period_grain
          AND domain = @domain
          AND metric_name = @metric_name
        ORDER BY period_end DESC
        LIMIT @lim
        """.replace(
            "TABLE_REF_PLACEHOLDER",
            self._table_sql,
        )
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
            bigquery.ScalarQueryParameter("period_grain", "STRING", _PERIOD_GRAIN),
            bigquery.ScalarQueryParameter("domain", "STRING", domain),
            bigquery.ScalarQueryParameter("metric_name", "STRING", metric_name),
            bigquery.ScalarQueryParameter("lim", "INT64", limit),
        ]
        return self._run(sql, params)

    def _run(self, sql: str, params: list[bigquery.ScalarQueryParameter]) -> list[dict[str, Any]]:
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        try:
            job = self.client.query(sql, job_config=job_config)
            return _rows(job)
        except BQRepositoryError:
            raise
        except Exception as exc:
            logger.exception("BigQuery query failed")
            raise BQRepositoryError("BigQuery request failed") from exc


_repository: BigQueryRepository | None = None
_client: bigquery.Client | None = None


def get_repository() -> BigQueryRepository:
    global _repository, _client
    settings = get_settings()
    if _repository is None:
        _client = bigquery.Client()
        _repository = BigQueryRepository(_client, settings)
    return _repository
