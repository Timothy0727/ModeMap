"""Pydantic schemas for job admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus, JobType


class JobResponse(BaseModel):
    """Public representation of a background job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: JobType
    status: JobStatus
    provider_id: str | None
    venue_id: UUID | None
    attempts: int
    last_error: str | None
    idempotency_key: str
    payload: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobListResponse(BaseModel):
    """Paginated job list."""

    jobs: list[JobResponse]
    total: int
    limit: int
    offset: int


class JobSummaryResponse(BaseModel):
    """Counts grouped by job status."""

    counts: dict[str, int] = Field(default_factory=dict)
    total: int
