from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bq_table_id: str = Field(
        default="ada26-pulse-project.kpi_analytics_gold.gold_kpi_snapshots",
        description="Fully qualified BigQuery table (project.dataset.table).",
    )
    allowed_tenant_id: str = Field(
        default="pulse-demo",
        description="Only this tenant_id may call the API path parameter.",
    )
    history_default_limit: int = Field(default=12, ge=1)
    history_max_limit: int = Field(default=52, ge=1, le=52)

    @model_validator(mode="after")
    def limits_consistent(self) -> Self:
        if self.history_default_limit > self.history_max_limit:
            raise ValueError("history_default_limit cannot exceed history_max_limit")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
