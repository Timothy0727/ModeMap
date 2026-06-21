"""Background job model for async enrichment orchestration."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobType(str, enum.Enum):
    ENRICH_VENUE = "ENRICH_VENUE"
    BATCH_ENRICH_AREA = "BATCH_ENRICH_AREA"
    REFRESH_VENUE = "REFRESH_VENUE"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(Base):
    """Tracks async enrichment and batch orchestration jobs."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_job_type_created_at", "status", "job_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default=JobStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    lock_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"
