from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ekh",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_default_queue="ekh",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
