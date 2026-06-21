"""Tests for admin job endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models.job import Job, JobStatus, JobType
from app.models.venue import Venue
from app.services.jobs import build_idempotency_key

pytestmark = pytest.mark.jobs


@pytest.fixture
def admin_client(test_session):
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_jobs(test_session):
    venue = Venue(
        provider_id="ChIJ_admin_test",
        provider_name="google",
        name="Admin Test Cafe",
        categories=["cafe"],
        lat=37.77,
        lng=-122.42,
        address="123 Admin St",
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

    now = datetime.now(UTC)
    pending = Job(
        job_type=JobType.ENRICH_VENUE.value,
        provider_id="ChIJ_admin_test",
        venue_id=venue.id,
        status=JobStatus.PENDING.value,
        attempts=0,
        idempotency_key=build_idempotency_key(JobType.ENRICH_VENUE, "ChIJ_admin_test"),
        created_at=now,
        updated_at=now,
    )
    completed = Job(
        job_type=JobType.ENRICH_VENUE.value,
        provider_id="ChIJ_admin_done",
        status=JobStatus.COMPLETED.value,
        attempts=1,
        idempotency_key=build_idempotency_key(JobType.ENRICH_VENUE, "ChIJ_admin_done"),
        created_at=now,
        updated_at=now,
        finished_at=now,
    )
    test_session.add_all([pending, completed])
    await test_session.commit()
    await test_session.refresh(pending)
    return pending, completed


def test_admin_jobs_summary(seeded_jobs, admin_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_enabled", True)
    resp = admin_client.get("/admin/jobs/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert body["counts"]["PENDING"] >= 1
    assert body["counts"]["COMPLETED"] >= 1


def test_admin_list_jobs_filtered_by_status(seeded_jobs, admin_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_enabled", True)
    resp = admin_client.get("/admin/jobs", params={"status": "PENDING"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(job["status"] == "PENDING" for job in body["jobs"])


def test_admin_get_job_by_id(seeded_jobs, admin_client, monkeypatch):
    pending, _ = seeded_jobs
    monkeypatch.setattr(settings, "admin_api_enabled", True)
    resp = admin_client.get(f"/admin/jobs/{pending.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(pending.id)
    assert body["provider_id"] == "ChIJ_admin_test"


def test_admin_disabled_returns_404(admin_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_enabled", False)
    resp = admin_client.get("/admin/jobs")
    assert resp.status_code == 404
