"""Job scheduling, deduplication, and status management."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import pygeohash
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.job import Job, JobStatus, JobType
from app.models.venue import Venue, VenueProfile
from app.services.profile_freshness import is_profile_fresh

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {JobStatus.PENDING.value, JobStatus.RUNNING.value}


def build_idempotency_key(job_type: JobType, provider_id: str) -> str:
    """Build a unique idempotency key for venue enrichment jobs."""
    if job_type in (JobType.ENRICH_VENUE, JobType.REFRESH_VENUE):
        return f"ENRICH_VENUE:{provider_id}"
    return f"{job_type.value}:{provider_id}"


def build_enqueue_lock_key(idempotency_key: str) -> str:
    """Redis key used to prevent duplicate enqueue storms."""
    return f"job:enqueue:{idempotency_key}"


async def acquire_enqueue_lock(redis: Redis, lock_key: str, ttl: int | None = None) -> bool:
    """Acquire a short-lived Redis lock (SET NX EX). Returns True if acquired."""
    ttl_seconds = ttl if ttl is not None else settings.job_lock_ttl_seconds
    acquired = await redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
    return bool(acquired)


async def get_active_job_for_provider(
    session: AsyncSession,
    provider_id: str,
    job_type: JobType = JobType.ENRICH_VENUE,
) -> Job | None:
    """Return an active job for the provider, if one exists."""
    idempotency_key = build_idempotency_key(job_type, provider_id)
    result = await session.execute(
        select(Job).where(
            Job.idempotency_key == idempotency_key,
            Job.status.in_(ACTIVE_STATUSES),
        )
    )
    return result.scalars().first()


async def mark_job_retry(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    error: str | None = None,
) -> Job:
    """Mark a job for retry — increment attempts and reset to PENDING."""
    job = await _get_job(session, job_id)
    now = datetime.now(UTC)
    job.status = JobStatus.PENDING.value
    job.attempts += 1
    job.updated_at = now
    job.started_at = None
    if error is not None:
        job.last_error = error[:2000]
    await session.commit()
    await session.refresh(job)
    return job


async def profile_is_fresh_for_provider(session: AsyncSession, provider_id: str) -> bool:
    """Return True if the venue has a fresh profile."""
    result = await session.execute(
        select(VenueProfile)
        .join(Venue, VenueProfile.venue_id == Venue.id)
        .where(Venue.provider_id == provider_id)
        .options(selectinload(VenueProfile.venue))
    )
    profile = result.scalars().first()
    return is_profile_fresh(profile)


async def create_or_get_pending_job(
    session: AsyncSession,
    *,
    job_type: JobType,
    provider_id: str,
    venue_id: uuid.UUID | None = None,
    lock_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[Job, bool]:
    """Create a PENDING job or return an existing active one.

    Returns (job, created) where created is True when a new row was inserted.
    """
    idempotency_key = build_idempotency_key(job_type, provider_id)
    existing = await get_active_job_for_provider(session, provider_id, job_type)
    if existing is not None:
        return existing, False

    now = datetime.now(UTC)
    job = Job(
        job_type=job_type.value,
        provider_id=provider_id,
        venue_id=venue_id,
        status=JobStatus.PENDING.value,
        attempts=0,
        idempotency_key=idempotency_key,
        lock_key=lock_key,
        payload=payload,
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    try:
        await session.flush()
        return job, True
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        )
        job = result.scalars().one()
        return job, False


async def mark_job_running(session: AsyncSession, job_id: uuid.UUID | str) -> Job:
    """Transition a job to RUNNING."""
    job = await _get_job(session, job_id)
    now = datetime.now(UTC)
    job.status = JobStatus.RUNNING.value
    job.started_at = now
    job.updated_at = now
    await session.commit()
    await session.refresh(job)
    return job


async def mark_job_completed(session: AsyncSession, job_id: uuid.UUID | str) -> Job:
    """Transition a job to COMPLETED."""
    job = await _get_job(session, job_id)
    now = datetime.now(UTC)
    job.status = JobStatus.COMPLETED.value
    job.finished_at = now
    job.updated_at = now
    job.last_error = None
    await session.commit()
    await session.refresh(job)
    return job


async def mark_job_failed(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    error: str | None = None,
    *,
    increment_attempts: bool = False,
) -> Job:
    """Transition a job to FAILED."""
    job = await _get_job(session, job_id)
    now = datetime.now(UTC)
    job.status = JobStatus.FAILED.value
    job.finished_at = now
    job.updated_at = now
    if increment_attempts:
        job.attempts += 1
    if error is not None:
        job.last_error = error[:2000]
    await session.commit()
    await session.refresh(job)
    return job


async def schedule_enrich_venue(
    provider_id: str,
    session: AsyncSession,
    redis: Redis,
    *,
    force: bool = False,
) -> Job | None:
    """Schedule a single ENRICH_VENUE job if not already active or fresh."""
    if not force and await profile_is_fresh_for_provider(session, provider_id):
        logger.debug("schedule_enrich_venue(%s): profile fresh, skipping", provider_id)
        return None

    job_type = JobType.REFRESH_VENUE if force else JobType.ENRICH_VENUE
    idempotency_key = build_idempotency_key(JobType.ENRICH_VENUE, provider_id)
    lock_key = build_enqueue_lock_key(idempotency_key)

    if not await acquire_enqueue_lock(redis, lock_key):
        existing = await get_active_job_for_provider(session, provider_id, job_type)
        if existing is not None:
            return existing
        # Lock held but no active job — another enqueue in progress; skip.
        return None

    venue_result = await session.execute(select(Venue).where(Venue.provider_id == provider_id))
    venue = venue_result.scalars().first()

    job, created = await create_or_get_pending_job(
        session,
        job_type=job_type,
        provider_id=provider_id,
        venue_id=venue.id if venue else None,
        lock_key=lock_key,
        payload={"force": force},
    )
    await session.commit()

    if created or job.status == JobStatus.PENDING.value:
        from app.worker.tasks import enrich_venue_task

        enrich_venue_task.delay(str(job.id), provider_id, force)
        logger.info("Scheduled %s for provider %s (job=%s)", job_type.value, provider_id, job.id)

    return job


async def schedule_enrich_for_provider_ids(
    provider_ids: list[str],
    session: AsyncSession,
    redis: Redis,
    *,
    force: bool = False,
) -> int:
    """Schedule enrichment for multiple provider IDs. Returns count scheduled."""
    scheduled = 0
    seen: set[str] = set()
    for provider_id in provider_ids:
        if provider_id in seen:
            continue
        seen.add(provider_id)
        job = await schedule_enrich_venue(provider_id, session, redis, force=force)
        if job is not None:
            scheduled += 1
    return scheduled


async def list_jobs(
    session: AsyncSession,
    *,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Job], int]:
    """List jobs with optional filters."""
    query = select(Job)
    count_query = select(func.count()).select_from(Job)

    if status is not None:
        query = query.where(Job.status == status.value)
        count_query = count_query.where(Job.status == status.value)
    if job_type is not None:
        query = query.where(Job.job_type == job_type.value)
        count_query = count_query.where(Job.job_type == job_type.value)

    query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    jobs = list(result.scalars().all())
    total_result = await session.execute(count_query)
    total = int(total_result.scalar_one())
    return jobs, total


async def get_job_by_id(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
    """Fetch a single job by ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    return result.scalars().first()


async def get_job_summary(session: AsyncSession) -> dict[str, int]:
    """Return counts grouped by job status."""
    result = await session.execute(
        select(Job.status, func.count()).group_by(Job.status)
    )
    counts = {status: count for status, count in result.all()}
    return counts


async def find_stale_profile_provider_ids(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> list[str]:
    """Return provider IDs for venues with expired or missing profiles."""
    now = datetime.now(UTC)
    result = await session.execute(
        select(Venue.provider_id)
        .outerjoin(VenueProfile, VenueProfile.venue_id == Venue.id)
        .where(
            (VenueProfile.id.is_(None))
            | (VenueProfile.expires_at.is_(None))
            | (VenueProfile.expires_at < now)
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def find_provider_ids_in_tile(
    session: AsyncSession,
    tile_id: str,
    *,
    limit: int = 50,
) -> list[str]:
    """Return provider IDs for venues in a geohash tile lacking fresh profiles."""
    prefix = tile_id[: len(tile_id)]
    result = await session.execute(
        select(Venue.provider_id, Venue.lat, Venue.lng, VenueProfile)
        .outerjoin(VenueProfile, VenueProfile.venue_id == Venue.id)
    )
    provider_ids: list[str] = []
    for provider_id, lat, lng, profile in result.all():
        venue_tile = pygeohash.encode(lat, lng, precision=len(prefix))
        if not venue_tile.startswith(prefix):
            continue
        if is_profile_fresh(profile):
            continue
        provider_ids.append(provider_id)
        if len(provider_ids) >= limit:
            break
    return provider_ids


async def _get_job(session: AsyncSession, job_id: uuid.UUID | str) -> Job:
    parsed_id = uuid.UUID(str(job_id))
    result = await session.execute(select(Job).where(Job.id == parsed_id))
    job = result.scalars().one()
    return job
