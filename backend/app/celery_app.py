from celery import Celery

from .config import get_settings


settings = get_settings()
celery_app = Celery(
    "kquant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["platform_api.tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 28,
)
