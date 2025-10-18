from app.task.trip_tasks import *
from app.celery_worker import celery_app
# Register manually
# celery_app.tasks.register(*)