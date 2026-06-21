"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("modemap")

celery_config: dict = {
    "broker_url": settings.celery_broker_url,
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "worker_prefetch_multiplier": 1,
    "task_default_queue": "enrichment",
    "task_routes": {
        "enrich_venue": {"queue": "enrichment"},
        "batch_enrich_area": {"queue": "enrichment"},
        "refresh_stale_profiles": {"queue": "enrichment"},
    },
    "beat_schedule": {
        "refresh-stale-profiles": {
            "task": "refresh_stale_profiles",
            "schedule": crontab(minute=0, hour=f"*/{settings.profile_refresh_interval_hours}"),
        },
    },
}

if settings.celery_result_backend:
    celery_config["result_backend"] = settings.celery_result_backend

celery_app.config_from_object(celery_config)
celery_app.autodiscover_tasks(["app.worker"])

# Import tasks so they register when the worker starts.
from app.worker import tasks as _tasks  # noqa: E402, F401
