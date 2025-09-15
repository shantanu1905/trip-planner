from celery import Celery

# Create Celery app with Redis broker & backend
celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",   # Redis broker
    backend="redis://localhost:6379/0"  # Optional: For task results
)


# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_concurrency=4,  # Adjust based on CPU cores
    task_track_started=True,
    task_time_limit=300,   # Timeout in seconds
)


# Auto-discover tasks from your app.tasks folder
celery_app.autodiscover_tasks(["app.task"])
