import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("upload", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_default_queue = "predictions"