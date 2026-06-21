"""Unit tests for job scheduling and celery tasks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.job import Job, JobStatus, JobType
from app.models.venue import Venue, VenueProfile
from app.services.jobs import (
    acquire_enqueue_lock,
    build_idempotency_key,
    mark_job_completed,
    mark_job_running,
    schedule_enrich_for_provider_ids,
    schedule_enrich_venue,
)
from app.worker.celery_app import celery_app

pytestmark = pytest.mark.jobs


class FakeRedis:
    """Minimal async Redis stub for enqueue lock tests."""

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self._keys:
            return False
        self._keys[key] = value
        return True

    async def aclose(self) -> None:
        return None


@pytest.fixture(autouse=True)
def celery_eager():
    """Run Celery tasks synchronously in tests."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest_asyncio.fixture
async def sample_venue(test_session):
    venue = Venue(
        provider_id="ChIJ_jobs_test",
        provider_name="google",
        name="Jobs Test Cafe",
        categories=["cafe"],
        lat=37.77,
        lng=-122.42,
        address="123 Jobs St",
        rating=4.0,
        price_level=2,
        hours={"open_now": True},
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_session.add(venue)
    await test_session.commit()
    await test_session.refresh(venue)
    return venue


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate_pending_jobs(test_session, sample_venue):
    redis = FakeRedis()
    with patch("app.worker.tasks.enrich_venue_task.delay") as mock_delay:
        job1 = await schedule_enrich_venue("ChIJ_jobs_test", test_session, redis)
        job2 = await schedule_enrich_venue("ChIJ_jobs_test", test_session, redis)

    assert job1 is not None
    assert job2 is not None
    assert job1.id == job2.id
    assert mock_delay.call_count == 1

    result = await test_session.execute(select(Job))
    jobs = result.scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.PENDING.value


@pytest.mark.asyncio
async def test_skips_fresh_profile(test_session, sample_venue):
    now = datetime.now(UTC)
    profile = VenueProfile(
        venue_id=sample_venue.id,
        attribute_scores={"quiet": 0.8},
        evidence_snippets={"quiet": ["Very quiet"]},
        profiled_at=now,
        expires_at=now + timedelta(days=7),
    )
    test_session.add(profile)
    await test_session.commit()

    redis = FakeRedis()
    with patch("app.worker.tasks.enrich_venue_task.delay"):
        job = await schedule_enrich_venue("ChIJ_jobs_test", test_session, redis)

    assert job is None
    result = await test_session.execute(select(Job))
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_mark_job_lifecycle(test_session, sample_venue):
    job = Job(
        job_type=JobType.ENRICH_VENUE.value,
        provider_id="ChIJ_jobs_test",
        venue_id=sample_venue.id,
        status=JobStatus.PENDING.value,
        attempts=0,
        idempotency_key=build_idempotency_key(JobType.ENRICH_VENUE, "ChIJ_jobs_test"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_session.add(job)
    await test_session.commit()
    await test_session.refresh(job)

    await mark_job_running(test_session, job.id)
    await test_session.refresh(job)
    assert job.status == JobStatus.RUNNING.value
    assert job.started_at is not None

    await mark_job_completed(test_session, job.id)
    await test_session.refresh(job)
    assert job.status == JobStatus.COMPLETED.value
    assert job.finished_at is not None


@pytest.mark.asyncio
async def test_enqueue_lock_prevents_duplicate_acquire():
    redis = FakeRedis()
    assert await acquire_enqueue_lock(redis, "lock:test", ttl=60) is True
    assert await acquire_enqueue_lock(redis, "lock:test", ttl=60) is False


@pytest.mark.asyncio
async def test_enrich_venue_task_success(test_session, sample_venue, monkeypatch):
    job = Job(
        job_type=JobType.ENRICH_VENUE.value,
        provider_id="ChIJ_jobs_test",
        venue_id=sample_venue.id,
        status=JobStatus.PENDING.value,
        attempts=0,
        idempotency_key=build_idempotency_key(JobType.ENRICH_VENUE, "ChIJ_jobs_test"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_session.add(job)
    await test_session.commit()
    job_id = job.id

    class SessionCtx:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, *args):
            return None

    class FakeTask:
        class request:
            retries = 0

        def retry(self, *args, **kwargs):
            raise AssertionError("retry should not be called")

    monkeypatch.setattr("app.worker.tasks.AsyncSessionLocal", lambda: SessionCtx(test_session))

    mock_response = AsyncMock()
    with patch("app.worker.tasks.enrich_venue_profile", new=AsyncMock(return_value=mock_response)):
        from app.worker.tasks import _execute_enrich

        await _execute_enrich(FakeTask(), str(job_id), "ChIJ_jobs_test", False)

    result = await test_session.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().one()
    assert job.status == JobStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_enrich_venue_task_permanent_failure(test_session, sample_venue, monkeypatch):
    job = Job(
        job_type=JobType.ENRICH_VENUE.value,
        provider_id="ChIJ_jobs_test",
        venue_id=sample_venue.id,
        status=JobStatus.PENDING.value,
        attempts=0,
        idempotency_key=build_idempotency_key(JobType.ENRICH_VENUE, "ChIJ_jobs_test"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_session.add(job)
    await test_session.commit()
    job_id = job.id

    class SessionCtx:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, *args):
            return None

    class FakeTask:
        class request:
            retries = 0

        def retry(self, *args, **kwargs):
            raise AssertionError("retry should not be called")

    monkeypatch.setattr("app.worker.tasks.AsyncSessionLocal", lambda: SessionCtx(test_session))

    with patch(
        "app.worker.tasks.enrich_venue_profile",
        new=AsyncMock(side_effect=ValueError("Place not found")),
    ):
        from app.worker.tasks import _execute_enrich

        await _execute_enrich(FakeTask(), str(job_id), "ChIJ_jobs_test", False)

    result = await test_session.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().one()
    assert job.status == JobStatus.FAILED.value
    assert job.attempts == 1


@pytest.mark.asyncio
async def test_schedule_enrich_for_provider_ids_deduplicates(test_session, sample_venue):
    redis = FakeRedis()
    with patch("app.worker.tasks.enrich_venue_task.delay"):
        count = await schedule_enrich_for_provider_ids(
            ["ChIJ_jobs_test", "ChIJ_jobs_test"],
            test_session,
            redis,
        )

    assert count == 1
    result = await test_session.execute(select(Job))
    assert len(result.scalars().all()) == 1
