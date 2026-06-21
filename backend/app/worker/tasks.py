"""Celery tasks for async venue enrichment."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import uuid

import httpx
from celery.exceptions import MaxRetriesExceededError
from redis.asyncio import Redis

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.services.enrichment import enrich_venue_profile
from app.services.jobs import (
    mark_job_completed,
    mark_job_failed,
    mark_job_retry,
    mark_job_running,
    schedule_enrich_for_provider_ids,
)
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro) -> None:
    """Run an async coroutine from Celery's synchronous worker context."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        future.result()


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient provider errors worth retrying."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response else 0
        return status >= 500 or status == 429
    return False


@celery_app.task(bind=True, name="enrich_venue", max_retries=settings.enrich_max_retries)
def enrich_venue_task(self, job_id: str, provider_id: str, force: bool = False) -> None:
    """Run venue enrichment in a background worker."""
    try:
        _run_async(_execute_enrich(self, job_id, provider_id, force))
    except MaxRetriesExceededError:
        logger.error("enrich_venue_task exhausted retries for job=%s provider=%s", job_id, provider_id)


async def _execute_enrich(task, job_id: str, provider_id: str, force: bool) -> None:
    async with AsyncSessionLocal() as session:
        await mark_job_running(session, job_id)
        try:
            await enrich_venue_profile(
                provider_id,
                session,
                force_refresh=force,
            )
            await mark_job_completed(session, job_id)
        except Exception as exc:
            retryable = _is_retryable(exc)
            if retryable and task.request.retries < settings.enrich_max_retries:
                await mark_job_retry(session, job_id, str(exc))
                countdown = settings.enrich_retry_backoff_base ** task.request.retries
                raise task.retry(exc=exc, countdown=countdown) from exc

            await mark_job_failed(session, job_id, str(exc), increment_attempts=True)
            if retryable:
                raise
            logger.warning(
                "enrich_venue_task permanent failure job=%s provider=%s: %s",
                job_id,
                provider_id,
                exc,
            )


@celery_app.task(name="batch_enrich_area")
def batch_enrich_area_task(job_id: str, tile_id: str, limit: int = 50) -> None:
    """Enqueue ENRICH_VENUE jobs for venues in a geohash tile."""
    _run_async(_execute_batch_enrich(job_id, tile_id, limit))


async def _execute_batch_enrich(job_id: str, tile_id: str, limit: int) -> None:
    from app.services.jobs import (
        find_provider_ids_in_tile,
        get_job_by_id,
        mark_job_completed,
        mark_job_running,
    )

    async with AsyncSessionLocal() as session:
        await mark_job_running(session, job_id)
        redis = Redis.from_url(settings.celery_broker_url)
        try:
            provider_ids = await find_provider_ids_in_tile(session, tile_id, limit=limit)
            scheduled = await schedule_enrich_for_provider_ids(provider_ids, session, redis)
            job = await get_job_by_id(session, uuid.UUID(job_id))
            if job is not None:
                job.payload = {
                    **(job.payload or {}),
                    "tile_id": tile_id,
                    "scheduled_count": scheduled,
                    "provider_ids_found": len(provider_ids),
                }
                await session.commit()
            await mark_job_completed(session, job_id)
        finally:
            await redis.aclose()


@celery_app.task(name="refresh_stale_profiles")
def refresh_stale_profiles_task() -> None:
    """Beat-triggered sweep of expired venue profiles."""
    _run_async(_execute_refresh_stale_profiles())


async def _execute_refresh_stale_profiles() -> None:
    from app.services.jobs import find_stale_profile_provider_ids

    async with AsyncSessionLocal() as session:
        redis = Redis.from_url(settings.celery_broker_url)
        try:
            provider_ids = await find_stale_profile_provider_ids(
                session,
                limit=settings.profile_refresh_batch_size,
            )
            await schedule_enrich_for_provider_ids(provider_ids, session, redis, force=True)
            logger.info("refresh_stale_profiles scheduled %d jobs", len(provider_ids))
        finally:
            await redis.aclose()
