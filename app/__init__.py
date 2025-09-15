from app.task.trip_tasks import process_trip_webhook
from app.celery_worker import celery_app
# Register manually
celery_app.tasks.register(process_trip_webhook)
